import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/reports", tags=["Finance Reports"])


def _default_range(start_date, end_date):
    end_date = end_date or datetime.datetime.utcnow()
    start_date = start_date or (end_date - datetime.timedelta(days=30))
    return start_date, end_date


# ---------------- P&L ----------------

@router.get("/pnl", response_model=schemas.PnLOut)
def get_pnl(
    start_date: Optional[datetime.datetime] = None,
    end_date: Optional[datetime.datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Revenue and cost of goods sold, computed directly from sales invoices, commission
    invoices, dispatch cost records, and logged expenses — not a formal GL, but an
    accurate roll-up of the real transactions already in the system.
    """
    start_date, end_date = _default_range(start_date, end_date)

    sales_revenue = db.query(func.coalesce(func.sum(models.SalesInvoice.subtotal), 0.0)).filter(
        models.SalesInvoice.invoice_date >= start_date,
        models.SalesInvoice.invoice_date <= end_date,
    ).scalar()

    commission_revenue = db.query(func.coalesce(func.sum(models.CommissionInvoice.amount), 0.0)).filter(
        models.CommissionInvoice.invoice_date >= start_date,
        models.CommissionInvoice.invoice_date <= end_date,
    ).scalar()

    cogs = db.query(
        func.coalesce(func.sum(models.SalesDispatchLine.quantity * models.SalesDispatchLine.cogs_rate), 0.0)
    ).join(models.SalesDispatch).filter(
        models.SalesDispatch.dispatch_date >= start_date,
        models.SalesDispatch.dispatch_date <= end_date,
    ).scalar()

    total_expenses = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).filter(
        models.Expense.expense_date >= start_date,
        models.Expense.expense_date <= end_date,
    ).scalar()

    total_revenue = sales_revenue + commission_revenue
    gross_profit = total_revenue - cogs
    net_profit = gross_profit - total_expenses

    return schemas.PnLOut(
        start_date=start_date, end_date=end_date, plant=None,
        sales_revenue=sales_revenue, commission_revenue=commission_revenue,
        total_revenue=total_revenue, cogs=cogs, gross_profit=gross_profit,
        total_expenses=total_expenses, net_profit=net_profit,
    )


@router.get("/pnl-by-item")
def get_pnl_by_item(
    start_date: Optional[datetime.datetime] = None,
    end_date: Optional[datetime.datetime] = None,
    db: Session = Depends(get_db),
):
    """Revenue, COGS, and margin broken down per SKU — a more useful lens than
    plant-wise, since a single plant produces many SKUs and a single SKU (e.g. a
    packed bottle) passes through more than one plant."""
    start_date, end_date = _default_range(start_date, end_date)

    revenue_rows = db.query(
        models.SalesInvoiceLine.item_id,
        func.sum(models.SalesInvoiceLine.amount).label("revenue"),
        func.sum(models.SalesInvoiceLine.quantity).label("qty_sold"),
    ).join(models.SalesInvoice).filter(
        models.SalesInvoice.invoice_date >= start_date,
        models.SalesInvoice.invoice_date <= end_date,
    ).group_by(models.SalesInvoiceLine.item_id).all()

    cogs_rows = db.query(
        models.SalesDispatchLine.item_id,
        func.sum(models.SalesDispatchLine.quantity * models.SalesDispatchLine.cogs_rate).label("cogs"),
    ).join(models.SalesDispatch).filter(
        models.SalesDispatch.dispatch_date >= start_date,
        models.SalesDispatch.dispatch_date <= end_date,
    ).group_by(models.SalesDispatchLine.item_id).all()
    cogs_by_item = {r.item_id: r.cogs for r in cogs_rows}

    output = []
    for r in revenue_rows:
        item = db.query(models.Item).filter(models.Item.id == r.item_id).first()
        cogs = cogs_by_item.get(r.item_id, 0.0)
        output.append({
            "item_id": r.item_id,
            "item_name": item.name if item else "Unknown",
            "quantity_sold": r.qty_sold,
            "revenue": r.revenue,
            "cogs": cogs,
            "gross_profit": r.revenue - cogs,
            "margin_percent": ((r.revenue - cogs) / r.revenue * 100) if r.revenue else None,
        })
    output.sort(key=lambda x: x["revenue"], reverse=True)
    return output


@router.get("/expenses-by-plant")
def get_expenses_by_plant(
    start_date: Optional[datetime.datetime] = None,
    end_date: Optional[datetime.datetime] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _default_range(start_date, end_date)
    rows = db.query(
        models.Expense.plant,
        func.sum(models.Expense.amount).label("total"),
    ).filter(
        models.Expense.expense_date >= start_date,
        models.Expense.expense_date <= end_date,
    ).group_by(models.Expense.plant).all()
    return [{"plant": r.plant.value if r.plant else "general/admin", "total": r.total} for r in rows]


# ---------------- AP / AR Aging ----------------

def _compute_aging(entries, as_of):
    """
    Simplified aging: apply total payments (credits) against the oldest bills
    (debits) first — FIFO settlement — then bucket whatever's left unpaid by how
    old that specific bill is. This is the standard simplified approach when
    individual due dates per invoice aren't separately tracked.
    """
    debits = sorted([e for e in entries if e.direction == models.LedgerDirection.debit], key=lambda e: e.entry_date)
    remaining_credit = sum(e.amount for e in entries if e.direction == models.LedgerDirection.credit)

    buckets = {"current": 0.0, "days_31_60": 0.0, "days_61_90": 0.0, "over_90": 0.0}
    for d in debits:
        amt = d.amount
        if remaining_credit > 1e-9:
            applied = min(remaining_credit, amt)
            amt -= applied
            remaining_credit -= applied
        if amt > 1e-6:
            age = (as_of - d.entry_date).days
            if age <= 30:
                buckets["current"] += amt
            elif age <= 60:
                buckets["days_31_60"] += amt
            elif age <= 90:
                buckets["days_61_90"] += amt
            else:
                buckets["over_90"] += amt
    return buckets


@router.get("/ap-aging", response_model=List[schemas.AgingBucketOut])
def get_ap_aging(db: Session = Depends(get_db)):
    """What we owe vendors, aged by how long each unpaid bill has been outstanding."""
    as_of = datetime.datetime.utcnow()
    vendors = db.query(models.Vendor).filter(models.Vendor.is_active == 1).all()
    output = []
    for v in vendors:
        entries = db.query(models.VendorLedgerEntry).filter(models.VendorLedgerEntry.vendor_id == v.id).all()
        if not entries:
            continue
        buckets = _compute_aging(entries, as_of)
        total = sum(buckets.values())
        if total < 1e-6:
            continue
        output.append(schemas.AgingBucketOut(
            party_id=v.id, party_name=v.name, total_outstanding=total, **buckets,
        ))
    return output


@router.get("/ar-aging-distributors", response_model=List[schemas.AgingBucketOut])
def get_ar_aging_distributors(db: Session = Depends(get_db)):
    """What distributors owe us for goods sold, aged."""
    as_of = datetime.datetime.utcnow()
    distributors = db.query(models.Distributor).filter(models.Distributor.is_active == 1).all()
    output = []
    for d in distributors:
        entries = db.query(models.DistributorLedgerEntry).filter(models.DistributorLedgerEntry.distributor_id == d.id).all()
        if not entries:
            continue
        buckets = _compute_aging(entries, as_of)
        total = sum(buckets.values())
        if total < 1e-6:
            continue
        output.append(schemas.AgingBucketOut(
            party_id=d.id, party_name=d.name, total_outstanding=total, **buckets,
        ))
    return output


@router.get("/ar-aging-toll-customers", response_model=List[schemas.AgingBucketOut])
def get_ar_aging_toll_customers(db: Session = Depends(get_db)):
    """What toll customers owe us for processing commission, aged."""
    as_of = datetime.datetime.utcnow()
    customers = db.query(models.Customer).filter(models.Customer.is_active == 1).all()
    output = []
    for c in customers:
        entries = db.query(models.CustomerLedgerEntry).filter(models.CustomerLedgerEntry.customer_id == c.id).all()
        if not entries:
            continue
        buckets = _compute_aging(entries, as_of)
        total = sum(buckets.values())
        if total < 1e-6:
            continue
        output.append(schemas.AgingBucketOut(
            party_id=c.id, party_name=c.name, total_outstanding=total, **buckets,
        ))
    return output


# ---------------- Sales Tax ----------------

@router.get("/sales-tax-summary", response_model=schemas.SalesTaxSummaryOut)
def get_sales_tax_summary(
    start_date: Optional[datetime.datetime] = None,
    end_date: Optional[datetime.datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Output tax (sales tax you collected from distributors) for a period. This is
    informational, built from your own sales invoices — NOT a validated FBR filing
    format. Have your accountant confirm the actual return before submission; this
    is meant to save you from re-adding up invoices by hand, not to replace their
    review, especially since it doesn't yet track input tax paid on purchases.
    """
    start_date, end_date = _default_range(start_date, end_date)
    invoices = db.query(models.SalesInvoice).filter(
        models.SalesInvoice.invoice_date >= start_date,
        models.SalesInvoice.invoice_date <= end_date,
    ).all()
    taxable_sales = sum(i.subtotal for i in invoices)
    output_tax = sum(i.tax_amount for i in invoices)
    return schemas.SalesTaxSummaryOut(
        start_date=start_date, end_date=end_date,
        taxable_sales=taxable_sales, output_tax_collected=output_tax,
        invoice_count=len(invoices),
    )


# ---------------- Financial Snapshot ----------------

@router.get("/financial-snapshot", response_model=schemas.FinancialSnapshotOut)
def get_financial_snapshot(db: Session = Depends(get_db)):
    """
    A point-in-time overview pulled from the sub-ledgers already in the system —
    NOT a formal trial balance from a double-entry general ledger (this system
    doesn't maintain one). Useful for a quick pulse check; for statutory accounts,
    have an accountant prepare proper financial statements.
    """
    def net_ledger(model):
        debit = db.query(func.coalesce(func.sum(model.amount), 0.0)).filter(
            model.direction == models.LedgerDirection.debit
        ).scalar()
        credit = db.query(func.coalesce(func.sum(model.amount), 0.0)).filter(
            model.direction == models.LedgerDirection.credit
        ).scalar()
        return debit - credit

    total_ap = net_ledger(models.VendorLedgerEntry)
    total_ar_distributors = net_ledger(models.DistributorLedgerEntry)
    total_ar_toll = net_ledger(models.CustomerLedgerEntry)

    inventory_value = db.query(
        func.coalesce(func.sum(models.StockLedgerEntry.quantity * models.StockLedgerEntry.rate), 0.0)
    ).filter(models.StockLedgerEntry.is_toll_stock == 0).scalar()

    total_sales_revenue = db.query(func.coalesce(func.sum(models.SalesInvoice.subtotal), 0.0)).scalar()
    total_commission_revenue = db.query(func.coalesce(func.sum(models.CommissionInvoice.amount), 0.0)).scalar()
    total_cogs = db.query(
        func.coalesce(func.sum(models.SalesDispatchLine.quantity * models.SalesDispatchLine.cogs_rate), 0.0)
    ).scalar()
    total_expenses = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).scalar()

    return schemas.FinancialSnapshotOut(
        as_of=datetime.datetime.utcnow(),
        total_accounts_payable=total_ap,
        total_accounts_receivable_distributors=total_ar_distributors,
        total_accounts_receivable_toll=total_ar_toll,
        total_inventory_value=inventory_value,
        total_sales_revenue_to_date=total_sales_revenue,
        total_commission_revenue_to_date=total_commission_revenue,
        total_cogs_to_date=total_cogs,
        total_expenses_to_date=total_expenses,
    )
