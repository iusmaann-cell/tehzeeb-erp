import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.post("/", response_model=schemas.PurchaseOrderOut)
def create_purchase_order(po: schemas.PurchaseOrderCreate, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.id == po.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    existing = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.po_number == po.po_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="PO number already exists")

    db_po = models.PurchaseOrder(
        po_number=po.po_number,
        vendor_id=po.vendor_id,
        notes=po.notes,
        status=models.POStatus.approved,
    )
    db.add(db_po)
    db.flush()  # get db_po.id before commit

    for line in po.lines:
        item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {line.item_id} not found")
        db_line = models.PurchaseOrderLine(
            purchase_order_id=db_po.id,
            item_id=line.item_id,
            quantity=line.quantity,
            rate=line.rate,
        )
        db.add(db_line)

    db.commit()
    db.refresh(db_po)
    return db_po


@router.get("/", response_model=List[schemas.PurchaseOrderOut])
def list_purchase_orders(db: Session = Depends(get_db)):
    return db.query(models.PurchaseOrder).all()


@router.get("/{po_id}", response_model=schemas.PurchaseOrderOut)
def get_purchase_order(po_id: int, db: Session = Depends(get_db)):
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


@router.put("/{po_id}", response_model=schemas.PurchaseOrderOut)
def update_purchase_order(po_id: int, update: schemas.PurchaseOrderUpdate, db: Session = Depends(get_db)):
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if any(line.received_quantity > 0 for line in po.lines):
        raise HTTPException(
            status_code=400,
            detail="This PO already has goods received against it and can no longer be edited. "
                   "You can still add a new PO for any correction needed.",
        )

    data = update.dict(exclude_unset=True)
    lines = data.pop("lines", None)

    if "vendor_id" in data:
        vendor = db.query(models.Vendor).filter(models.Vendor.id == data["vendor_id"]).first()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

    for field, value in data.items():
        setattr(po, field, value)

    if lines is not None:
        db.query(models.PurchaseOrderLine).filter(models.PurchaseOrderLine.purchase_order_id == po.id).delete()
        for line in lines:
            item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
            if not item:
                raise HTTPException(status_code=404, detail=f"Item {line.item_id} not found")
            db.add(models.PurchaseOrderLine(
                purchase_order_id=po.id, item_id=line.item_id, quantity=line.quantity, rate=line.rate,
            ))

    db.commit()
    db.refresh(po)
    return po


@router.delete("/{po_id}")
def delete_purchase_order(po_id: int, db: Session = Depends(get_db)):
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if any(line.received_quantity > 0 for line in po.lines):
        raise HTTPException(
            status_code=400,
            detail="This PO already has goods received against it and can't be deleted, since stock and "
                   "vendor ledger entries depend on it. Set its status to cancelled instead if it's no longer needed.",
        )

    db.delete(po)
    db.commit()
    return {"message": "Purchase order deleted", "po_id": po_id}


@router.patch("/{po_id}/cancel", response_model=schemas.PurchaseOrderOut)
def cancel_purchase_order(po_id: int, db: Session = Depends(get_db)):
    """Use this instead of delete once a PO has receipts against it — keeps history, just marks it closed."""
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    po.status = models.POStatus.cancelled
    db.commit()
    db.refresh(po)
    return po


def _validate_payment_fields(update: schemas.PaymentStatusUpdate):
    if update.payment_status != models.PaymentStatus.paid:
        return
    if update.payment_method is None:
        raise HTTPException(status_code=400, detail="payment_method is required when marking as paid")
    if update.payment_method == models.PaymentMethod.cheque:
        if not update.cheque_number or not update.cheque_bank:
            raise HTTPException(status_code=400, detail="Cheque payments need a cheque number and bank")
    elif update.payment_method == models.PaymentMethod.online:
        if not update.other_party_name or not update.other_party_bank:
            raise HTTPException(status_code=400, detail="Online transfers need the other party's name and bank")


@router.patch("/{po_id}/payment-status", response_model=schemas.PurchaseOrderOut)
def update_po_payment_status(po_id: int, update: schemas.PaymentStatusUpdate, db: Session = Depends(get_db)):
    """
    Marks a PO paid or unpaid. Marking paid posts a credit to the vendor's ledger
    (with full payment method detail) for the PO's total value — reducing what's
    owed to that vendor. Marking unpaid again reverses that same ledger entry, so
    toggling back and forth never leaves stray records behind.
    """
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    _validate_payment_fields(update)

    existing_payment = db.query(models.VendorLedgerEntry).filter(
        models.VendorLedgerEntry.ref_type == "PO_PAYMENT",
        models.VendorLedgerEntry.ref_id == po.id,
    ).first()

    if update.payment_status == models.PaymentStatus.paid:
        if existing_payment:
            raise HTTPException(status_code=400, detail="This PO is already marked paid")
        po_total = sum(l.quantity * l.rate for l in po.lines)
        db.add(models.VendorLedgerEntry(
            vendor_id=po.vendor_id,
            direction=models.LedgerDirection.credit,
            amount=po_total,
            ref_type="PO_PAYMENT",
            ref_id=po.id,
            entry_date=update.payment_date or datetime.datetime.utcnow(),
            notes=update.notes or f"Payment for {po.po_number}",
            payment_method=update.payment_method,
            cheque_number=update.cheque_number,
            cheque_bank=update.cheque_bank,
            our_bank=update.our_bank,
            other_party_name=update.other_party_name,
            other_party_bank=update.other_party_bank,
        ))
        po.payment_status = models.PaymentStatus.paid
    else:
        if existing_payment:
            db.delete(existing_payment)
        po.payment_status = models.PaymentStatus.unpaid

    db.commit()
    db.refresh(po)
    return po
