import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["Sales & Distribution"])


# ---------------- Sales Orders ----------------

@router.post("/sales-orders/", response_model=schemas.SalesOrderOut)
def create_sales_order(so: schemas.SalesOrderCreate, db: Session = Depends(get_db)):
    distributor = db.query(models.Distributor).filter(models.Distributor.id == so.distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    existing = db.query(models.SalesOrder).filter(models.SalesOrder.so_number == so.so_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="SO number already exists")

    db_so = models.SalesOrder(so_number=so.so_number, distributor_id=so.distributor_id, notes=so.notes)
    db.add(db_so)
    db.flush()

    for line in so.lines:
        item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {line.item_id} not found")
        db.add(models.SalesOrderLine(sales_order_id=db_so.id, item_id=line.item_id, quantity=line.quantity, rate=line.rate))

    db.commit()
    db.refresh(db_so)
    return db_so


@router.get("/sales-orders/", response_model=List[schemas.SalesOrderOut])
def list_sales_orders(db: Session = Depends(get_db)):
    return db.query(models.SalesOrder).order_by(models.SalesOrder.id.desc()).all()


@router.get("/sales-orders/{so_id}", response_model=schemas.SalesOrderOut)
def get_sales_order(so_id: int, db: Session = Depends(get_db)):
    so = db.query(models.SalesOrder).filter(models.SalesOrder.id == so_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return so


@router.put("/sales-orders/{so_id}", response_model=schemas.SalesOrderOut)
def update_sales_order(so_id: int, update: schemas.SalesOrderUpdate, db: Session = Depends(get_db)):
    so = db.query(models.SalesOrder).filter(models.SalesOrder.id == so_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if any(line.dispatched_quantity > 0 for line in so.lines):
        raise HTTPException(
            status_code=400,
            detail="This sales order already has dispatches against it and can no longer be edited.",
        )

    data = update.dict(exclude_unset=True)
    lines = data.pop("lines", None)

    if "distributor_id" in data:
        distributor = db.query(models.Distributor).filter(models.Distributor.id == data["distributor_id"]).first()
        if not distributor:
            raise HTTPException(status_code=404, detail="Distributor not found")

    for field, value in data.items():
        setattr(so, field, value)

    if lines is not None:
        db.query(models.SalesOrderLine).filter(models.SalesOrderLine.sales_order_id == so.id).delete()
        for line in lines:
            item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
            if not item:
                raise HTTPException(status_code=404, detail=f"Item {line.item_id} not found")
            db.add(models.SalesOrderLine(sales_order_id=so.id, item_id=line.item_id, quantity=line.quantity, rate=line.rate))

    db.commit()
    db.refresh(so)
    return so


@router.delete("/sales-orders/{so_id}")
def delete_sales_order(so_id: int, db: Session = Depends(get_db)):
    so = db.query(models.SalesOrder).filter(models.SalesOrder.id == so_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if any(line.dispatched_quantity > 0 for line in so.lines):
        raise HTTPException(
            status_code=400,
            detail="This sales order already has dispatches against it and can't be deleted. "
                   "Cancel it instead if it's no longer needed.",
        )
    db.delete(so)
    db.commit()
    return {"message": "Sales order deleted", "so_id": so_id}


@router.patch("/sales-orders/{so_id}/cancel", response_model=schemas.SalesOrderOut)
def cancel_sales_order(so_id: int, db: Session = Depends(get_db)):
    so = db.query(models.SalesOrder).filter(models.SalesOrder.id == so_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    so.status = models.SalesOrderStatus.cancelled
    db.commit()
    db.refresh(so)
    return so


# ---------------- Dispatch (Delivery Challan) ----------------

def _get_fifo_ordered_own_batches(db: Session, item_id: int, warehouse_id: int):
    """Own stock only (never toll stock) — oldest batch first."""
    rows = db.query(models.StockLedgerEntry).filter(
        models.StockLedgerEntry.item_id == item_id,
        models.StockLedgerEntry.warehouse_id == warehouse_id,
        models.StockLedgerEntry.is_toll_stock == 0,
        models.StockLedgerEntry.batch_no.isnot(None),
    ).all()

    by_batch = {}
    for r in rows:
        b = by_batch.setdefault(r.batch_no, {"balance": 0.0, "in_qty": 0.0, "in_value": 0.0, "received_at": None})
        b["balance"] += r.quantity
        if r.quantity > 0:
            b["in_qty"] += r.quantity
            b["in_value"] += r.quantity * (r.rate or 0)
            if b["received_at"] is None or r.entry_date < b["received_at"]:
                b["received_at"] = r.entry_date

    batches = [
        {
            "batch_no": batch_no,
            "balance": b["balance"],
            "rate": (b["in_value"] / b["in_qty"]) if b["in_qty"] else 0.0,
            "received_at": b["received_at"],
        }
        for batch_no, b in by_batch.items() if b["balance"] > 1e-6
    ]
    batches.sort(key=lambda b: b["received_at"])
    return batches


def _get_own_batch_balance_and_rate(db: Session, item_id: int, warehouse_id: int, batch_no: str):
    rows = db.query(models.StockLedgerEntry).filter(
        models.StockLedgerEntry.item_id == item_id,
        models.StockLedgerEntry.warehouse_id == warehouse_id,
        models.StockLedgerEntry.batch_no == batch_no,
        models.StockLedgerEntry.is_toll_stock == 0,
    ).all()
    balance = sum(r.quantity for r in rows)
    in_rows = [r for r in rows if r.quantity > 0]
    total_in_qty = sum(r.quantity for r in in_rows)
    weighted_rate = (sum(r.quantity * (r.rate or 0) for r in in_rows) / total_in_qty) if total_in_qty else 0.0
    return balance, weighted_rate


@router.post("/sales-dispatches/", response_model=schemas.SalesDispatchOut)
def create_sales_dispatch(dispatch: schemas.SalesDispatchCreate, db: Session = Depends(get_db)):
    """
    Goods actually leaving the mill. FIFO by default from your own finished-goods
    stock (never toll stock — that leaves via Toll Delivery instead). Updates the
    sales order line's dispatched_quantity and rolls up its status.
    """
    so = db.query(models.SalesOrder).filter(models.SalesOrder.id == dispatch.sales_order_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")

    existing = db.query(models.SalesDispatch).filter(
        models.SalesDispatch.dispatch_number == dispatch.dispatch_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dispatch number already exists")

    db_dispatch = models.SalesDispatch(
        dispatch_number=dispatch.dispatch_number,
        sales_order_id=dispatch.sales_order_id,
        vehicle_no=dispatch.vehicle_no,
        notes=dispatch.notes,
    )
    db.add(db_dispatch)
    db.flush()

    for line in dispatch.lines:
        so_line = db.query(models.SalesOrderLine).filter(models.SalesOrderLine.id == line.sales_order_line_id).first()
        if not so_line:
            raise HTTPException(status_code=404, detail=f"Sales order line {line.sales_order_line_id} not found")

        remaining_on_line = so_line.quantity - so_line.dispatched_quantity
        if line.quantity > remaining_on_line + 1e-6:
            raise HTTPException(
                status_code=400,
                detail=f"Dispatch quantity ({line.quantity}) exceeds remaining SO quantity ({remaining_on_line}) "
                       f"for item {line.item_id}",
            )

        if line.batch_no:
            balance, rate = _get_own_batch_balance_and_rate(db, line.item_id, line.warehouse_id, line.batch_no)
            if line.quantity > balance + 1e-6:
                raise HTTPException(
                    status_code=400,
                    detail=f"Batch '{line.batch_no}' only has {balance} available, requested {line.quantity}",
                )
            draws = [(line.batch_no, line.quantity, rate)]
        else:
            fifo_batches = _get_fifo_ordered_own_batches(db, line.item_id, line.warehouse_id)
            available = sum(b["balance"] for b in fifo_batches)
            if line.quantity > available + 1e-6:
                raise HTTPException(
                    status_code=400,
                    detail=f"Only {available} available in stock for this item/warehouse, requested {line.quantity}",
                )
            draws = []
            remaining = line.quantity
            for b in fifo_batches:
                if remaining <= 1e-9:
                    break
                take = min(b["balance"], remaining)
                draws.append((b["batch_no"], take, b["rate"]))
                remaining -= take

        for batch_no, qty, rate in draws:
            db.add(models.SalesDispatchLine(
                dispatch_id=db_dispatch.id,
                sales_order_line_id=line.sales_order_line_id,
                item_id=line.item_id,
                warehouse_id=line.warehouse_id,
                batch_no=batch_no,
                quantity=qty,
                cogs_rate=rate,
            ))
            db.add(models.StockLedgerEntry(
                item_id=line.item_id,
                warehouse_id=line.warehouse_id,
                batch_no=batch_no,
                quantity=-qty,
                rate=rate,
                is_toll_stock=0,
                ref_type="SALES_DISPATCH",
                ref_id=db_dispatch.id,
            ))

        so_line.dispatched_quantity += line.quantity

    all_lines = db.query(models.SalesOrderLine).filter(models.SalesOrderLine.sales_order_id == so.id).all()
    if all(l.dispatched_quantity >= l.quantity - 1e-6 for l in all_lines):
        so.status = models.SalesOrderStatus.completed
    else:
        so.status = models.SalesOrderStatus.partially_dispatched

    db.commit()
    db.refresh(db_dispatch)
    return db_dispatch


@router.get("/sales-dispatches/", response_model=List[schemas.SalesDispatchOut])
def list_sales_dispatches(db: Session = Depends(get_db)):
    return db.query(models.SalesDispatch).order_by(models.SalesDispatch.id.desc()).all()


# ---------------- Sales Invoices ----------------

@router.post("/sales-invoices/", response_model=schemas.SalesInvoiceOut)
def create_sales_invoice(invoice: schemas.SalesInvoiceCreate, db: Session = Depends(get_db)):
    """Posts the revenue event: subtotal + tax, debited to the distributor's ledger."""
    distributor = db.query(models.Distributor).filter(models.Distributor.id == invoice.distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    existing = db.query(models.SalesInvoice).filter(
        models.SalesInvoice.invoice_number == invoice.invoice_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Invoice number already exists")

    if not invoice.lines:
        raise HTTPException(status_code=400, detail="At least one invoice line is required")

    subtotal = sum(l.quantity * l.rate for l in invoice.lines)
    tax_amount = subtotal * (invoice.tax_rate / 100.0)
    total_amount = subtotal + tax_amount

    db_invoice = models.SalesInvoice(
        invoice_number=invoice.invoice_number,
        distributor_id=invoice.distributor_id,
        sales_order_id=invoice.sales_order_id,
        tax_rate=invoice.tax_rate,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        notes=invoice.notes,
    )
    db.add(db_invoice)
    db.flush()

    for line in invoice.lines:
        item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {line.item_id} not found")
        db.add(models.SalesInvoiceLine(
            invoice_id=db_invoice.id, item_id=line.item_id, quantity=line.quantity,
            rate=line.rate, amount=line.quantity * line.rate,
        ))

    db.add(models.DistributorLedgerEntry(
        distributor_id=invoice.distributor_id,
        direction=models.LedgerDirection.debit,
        amount=total_amount,
        ref_type="SALES_INVOICE",
        ref_id=db_invoice.id,
        notes=f"Invoice {invoice.invoice_number}",
    ))

    db.commit()
    db.refresh(db_invoice)
    return db_invoice


@router.get("/sales-invoices/", response_model=List[schemas.SalesInvoiceOut])
def list_sales_invoices(distributor_id: int = None, db: Session = Depends(get_db)):
    query = db.query(models.SalesInvoice)
    if distributor_id:
        query = query.filter(models.SalesInvoice.distributor_id == distributor_id)
    return query.order_by(models.SalesInvoice.id.desc()).all()


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


@router.patch("/sales-invoices/{invoice_id}/payment-status", response_model=schemas.SalesInvoiceOut)
def update_sales_invoice_payment_status(invoice_id: int, update: schemas.PaymentStatusUpdate, db: Session = Depends(get_db)):
    """
    Marks a sales invoice paid or unpaid. Marking paid posts a credit to the
    distributor's ledger (with full payment method detail) — reducing what they
    owe. Marking unpaid again reverses that same ledger entry.
    """
    invoice = db.query(models.SalesInvoice).filter(models.SalesInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Sales invoice not found")

    _validate_payment_fields(update)

    existing_payment = db.query(models.DistributorLedgerEntry).filter(
        models.DistributorLedgerEntry.ref_type == "SALES_PAYMENT",
        models.DistributorLedgerEntry.ref_id == invoice.id,
    ).first()

    if update.payment_status == models.PaymentStatus.paid:
        if existing_payment:
            raise HTTPException(status_code=400, detail="This invoice is already marked paid")
        db.add(models.DistributorLedgerEntry(
            distributor_id=invoice.distributor_id,
            direction=models.LedgerDirection.credit,
            amount=invoice.total_amount,
            ref_type="SALES_PAYMENT",
            ref_id=invoice.id,
            entry_date=update.payment_date or datetime.datetime.utcnow(),
            notes=update.notes or f"Payment received for {invoice.invoice_number}",
            payment_method=update.payment_method,
            cheque_number=update.cheque_number,
            cheque_bank=update.cheque_bank,
            our_bank=update.our_bank,
            other_party_name=update.other_party_name,
            other_party_bank=update.other_party_bank,
        ))
        invoice.payment_status = models.PaymentStatus.paid
    else:
        if existing_payment:
            db.delete(existing_payment)
        invoice.payment_status = models.PaymentStatus.unpaid

    db.commit()
    db.refresh(invoice)
    return invoice
