import datetime
import json
import pathlib
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .. import models, file_storage
from ..database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])

# Tables intentionally preserved across a reset — configuration, not test data.
# Accounts, roles and the token-signing key must survive too — wiping them would
# lock everyone (including the administrator who pressed the button) out.
PRESERVED_TABLES = {"invoice_settings", "users", "roles", "auth_secret"}


@router.post("/reset-all-data")
def reset_all_data(confirm: str = "", db: Session = Depends(get_db)):
    """
    Permanently deletes every row from every table (except the ones listed in
    PRESERVED_TABLES) and leaves the schema itself intact — for wiping test data
    and starting fresh. Tables are cleared in reverse of SQLAlchemy's dependency
    order, so child rows are always removed before the parent rows they
    reference, avoiding foreign-key violations without needing a hand-maintained
    table list that could go stale as new phases add tables.

    Administrators only (enforced centrally in security.authorize). The
    confirm=RESET query param is an extra guard against triggering it by accident.
    """
    if confirm != "RESET":
        raise HTTPException(
            status_code=400,
            detail="This permanently deletes ALL data. Pass confirm=RESET as a query parameter to proceed.",
        )

    cleared = []
    for table in reversed(models.Base.metadata.sorted_tables):
        if table.name in PRESERVED_TABLES:
            continue
        db.execute(table.delete())
        cleared.append(table.name)

    db.commit()
    return {
        "message": f"Wiped {len(cleared)} table(s). Invoice settings and user accounts were preserved.",
        "cleared_tables": cleared,
    }


# ---------------------------------------------------------------------------
# Orphan vendor payments: advance / payment ledger entries whose purchase order
# has since been deleted (older versions allowed that). They still count in the
# vendor balance and the expense report but point at nothing.
# ---------------------------------------------------------------------------
_PAYMENT_REFS = ("PO_ADVANCE", "PO_PAYMENT")


def _find_orphan_payments(db: Session):
    entries = db.query(models.VendorLedgerEntry).filter(
        models.VendorLedgerEntry.ref_type.in_(_PAYMENT_REFS)).all()
    ref_ids = {e.ref_id for e in entries if e.ref_id is not None}
    existing = {row[0] for row in db.query(models.PurchaseOrder.id).filter(
        models.PurchaseOrder.id.in_(ref_ids)).all()} if ref_ids else set()
    # An entry with no PO reference at all is also an orphan; one whose PO is gone is too.
    return [e for e in entries if e.ref_id is None or e.ref_id not in existing]


def _orphan_row(e: models.VendorLedgerEntry):
    return {
        "id": e.id,
        "vendor_id": e.vendor_id,
        "vendor_name": e.vendor.name if e.vendor else None,
        "ref_type": e.ref_type,
        "deleted_po_id": e.ref_id,
        "amount": e.amount,
        "entry_date": e.entry_date.isoformat() if e.entry_date else None,
        "payment_method": getattr(e.payment_method, "value", e.payment_method),
        "notes": e.notes,
    }


def _backup_row(e: models.VendorLedgerEntry):
    out = {}
    for c in e.__table__.columns:
        v = getattr(e, c.name)
        out[c.name] = v.isoformat() if isinstance(v, (datetime.datetime, datetime.date)) else getattr(v, "value", v)
    return out


class OrphanPurgeRequest(BaseModel):
    entry_ids: List[int]


@router.get("/orphan-payments")
def list_orphan_payments(db: Session = Depends(get_db)):
    """Read-only preview: every payment/advance entry whose purchase order no longer exists."""
    rows = [_orphan_row(e) for e in _find_orphan_payments(db)]
    return {"count": len(rows), "total_amount": sum(r["amount"] for r in rows), "entries": rows}


@router.post("/orphan-payments/purge")
def purge_orphan_payments(req: OrphanPurgeRequest, db: Session = Depends(get_db)):
    """Deletes the chosen orphan entries. Only entries that are CURRENTLY orphans can be
    removed (the list is re-checked here), a JSON backup is written to the uploads volume
    first, and anything not on the orphan list is refused so a stale screen can't delete a
    real payment. Administrators only (enforced centrally in security.authorize)."""
    if not req.entry_ids:
        raise HTTPException(status_code=400, detail="Select at least one entry")
    orphans = {e.id: e for e in _find_orphan_payments(db)}
    not_orphan = [i for i in req.entry_ids if i not in orphans]
    if not_orphan:
        raise HTTPException(
            status_code=400,
            detail=f"Entries {not_orphan} are not orphan payments (or were already removed) — nothing was deleted. Refresh the list.")
    chosen = [orphans[i] for i in dict.fromkeys(req.entry_ids)]

    folder = pathlib.Path(file_storage.UPLOADS_DIR) / "purge_backups"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"orphan_payments_{datetime.datetime.utcnow():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps({"vendor_ledger": [_backup_row(e) for e in chosen]}, indent=2, default=str))

    total = sum(e.amount for e in chosen)
    for e in chosen:
        db.delete(e)
    db.commit()
    return {
        "message": f"Removed {len(chosen)} orphan payment entr{'y' if len(chosen) == 1 else 'ies'} (Rs. {total:,.2f}). Backup saved: {path.name}",
        "removed": len(chosen),
        "total_amount": total,
        "backup_file": path.name,
    }
