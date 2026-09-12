import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/vendors", tags=["Vendors"])


@router.post("/", response_model=schemas.VendorOut)
def create_vendor(vendor: schemas.VendorCreate, db: Session = Depends(get_db)):
    db_vendor = models.Vendor(**vendor.dict())
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)

    # if there's an opening balance, log it as the first ledger entry
    if vendor.opening_balance:
        entry = models.VendorLedgerEntry(
            vendor_id=db_vendor.id,
            direction=models.LedgerDirection.debit,
            amount=vendor.opening_balance,
            ref_type="OPENING_BALANCE",
            notes="Opening balance at vendor creation",
        )
        db.add(entry)
        db.commit()

    return db_vendor


@router.get("/", response_model=List[schemas.VendorOut])
def list_vendors(db: Session = Depends(get_db)):
    return db.query(models.Vendor).filter(models.Vendor.is_active == 1).all()


@router.get("/{vendor_id}", response_model=schemas.VendorOut)
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.put("/{vendor_id}", response_model=schemas.VendorOut)
def update_vendor(vendor_id: int, update: schemas.VendorUpdate, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    data = update.dict(exclude_unset=True)
    new_opening_balance = data.pop("opening_balance", None)

    for field, value in data.items():
        setattr(vendor, field, value)

    # keep the OPENING_BALANCE ledger entry in sync if it changes, rather than
    # letting vendor.opening_balance drift from the actual ledger
    if new_opening_balance is not None and new_opening_balance != vendor.opening_balance:
        vendor.opening_balance = new_opening_balance
        entry = db.query(models.VendorLedgerEntry).filter(
            models.VendorLedgerEntry.vendor_id == vendor_id,
            models.VendorLedgerEntry.ref_type == "OPENING_BALANCE",
        ).first()
        if entry:
            entry.amount = new_opening_balance
        elif new_opening_balance:
            db.add(models.VendorLedgerEntry(
                vendor_id=vendor_id,
                direction=models.LedgerDirection.debit,
                amount=new_opening_balance,
                ref_type="OPENING_BALANCE",
                notes="Opening balance (added on edit)",
            ))

    db.commit()
    db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}")
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    """Soft delete — hides the vendor from active lists but keeps all history (POs, ledger) intact."""
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.is_active = 0
    db.commit()
    return {"message": "Vendor deactivated", "vendor_id": vendor_id}


@router.get("/{vendor_id}/balance", response_model=schemas.VendorBalanceOut)
def get_vendor_balance(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    debit_total = db.query(func.coalesce(func.sum(models.VendorLedgerEntry.amount), 0.0)).filter(
        models.VendorLedgerEntry.vendor_id == vendor_id,
        models.VendorLedgerEntry.direction == models.LedgerDirection.debit,
    ).scalar()
    credit_total = db.query(func.coalesce(func.sum(models.VendorLedgerEntry.amount), 0.0)).filter(
        models.VendorLedgerEntry.vendor_id == vendor_id,
        models.VendorLedgerEntry.direction == models.LedgerDirection.credit,
    ).scalar()

    balance = debit_total - credit_total
    return schemas.VendorBalanceOut(vendor_id=vendor.id, vendor_name=vendor.name, balance=balance)


@router.post("/{vendor_id}/payment")
def record_payment(vendor_id: int, amount: float, notes: str = "", db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    entry = models.VendorLedgerEntry(
        vendor_id=vendor_id,
        direction=models.LedgerDirection.credit,
        amount=amount,
        ref_type="PAYMENT",
        notes=notes,
    )
    db.add(entry)
    db.commit()
    return {"message": "Payment recorded", "vendor_id": vendor_id, "amount": amount}


@router.get("/{vendor_id}/ledger", response_model=schemas.VendorLedgerDetailOut)
def get_vendor_ledger(
    vendor_id: int,
    start_date: Optional[datetime.datetime] = None,
    end_date: Optional[datetime.datetime] = None,
    db: Session = Depends(get_db),
):
    """Every ledger entry for this vendor (bills + payments, with full payment
    method detail), optionally filtered to a date range, plus the running balance
    owed as of the end of that range."""
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    query = db.query(models.VendorLedgerEntry).filter(models.VendorLedgerEntry.vendor_id == vendor_id)
    if start_date:
        query = query.filter(models.VendorLedgerEntry.entry_date >= start_date)
    if end_date:
        query = query.filter(models.VendorLedgerEntry.entry_date <= end_date)
    entries = query.order_by(models.VendorLedgerEntry.entry_date.desc()).all()

    period_debit = sum(e.amount for e in entries if e.direction == models.LedgerDirection.debit)
    period_credit = sum(e.amount for e in entries if e.direction == models.LedgerDirection.credit)

    balance_query = db.query(models.VendorLedgerEntry).filter(models.VendorLedgerEntry.vendor_id == vendor_id)
    if end_date:
        balance_query = balance_query.filter(models.VendorLedgerEntry.entry_date <= end_date)
    all_up_to_end = balance_query.all()
    balance_as_of_end = (
        sum(e.amount for e in all_up_to_end if e.direction == models.LedgerDirection.debit)
        - sum(e.amount for e in all_up_to_end if e.direction == models.LedgerDirection.credit)
    )

    return schemas.VendorLedgerDetailOut(
        entries=entries, period_debit=period_debit, period_credit=period_credit, balance_as_of_end=balance_as_of_end,
    )
