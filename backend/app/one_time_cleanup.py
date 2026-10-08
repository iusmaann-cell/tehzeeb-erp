"""
One-off data cleanup, driven by environment variables so nothing runs unless asked:

  PURGE_PO_NUMBER   the purchase order to remove completely (e.g. PO-261003-190121)
  PURGE_PO_DRY_RUN  anything except "0" only PRINTS what would be removed (default). Set "0" to delete.

Removing a PO this way also removes the goods-received notes against it, the stock those notes
added, and every vendor-ledger entry that came from the PO (bills, freight, advance, payments).
It refuses (and changes nothing) if any of that stock has since been moved, consumed or adjusted,
because deleting it would corrupt the stock ledger. A JSON backup of every removed row is written
to the uploads volume before anything is deleted. The report goes to the deploy logs ("[purge]").
"""
import os
import json
import datetime
import pathlib

from . import models, file_storage
from .database import SessionLocal


def _row(obj):
    out = {}
    for c in obj.__table__.columns:
        v = getattr(obj, c.name)
        out[c.name] = v.isoformat() if isinstance(v, (datetime.datetime, datetime.date)) else getattr(v, "value", v)
    return out


def run():
    po_number = (os.getenv("PURGE_PO_NUMBER") or "").strip()
    if not po_number:
        return
    dry = os.getenv("PURGE_PO_DRY_RUN", "1") != "0"
    db = SessionLocal()
    try:
        po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.po_number == po_number).first()
        if not po:
            print(f"[purge] {po_number}: not found — nothing to do (already removed?)")
            return
        grns = db.query(models.GRN).filter(models.GRN.purchase_order_id == po.id).all()
        grn_ids = [g.id for g in grns]
        grn_lines = db.query(models.GRNLine).filter(models.GRNLine.grn_id.in_(grn_ids)).all() if grn_ids else []
        stock = db.query(models.StockLedgerEntry).filter(
            models.StockLedgerEntry.ref_type == "GRN", models.StockLedgerEntry.ref_id.in_(grn_ids)).all() if grn_ids else []
        ledger = []
        if grn_ids:
            ledger += db.query(models.VendorLedgerEntry).filter(
                models.VendorLedgerEntry.ref_type.in_(("GRN_BILL", "GRN_FREIGHT")),
                models.VendorLedgerEntry.ref_id.in_(grn_ids)).all()
        ledger += db.query(models.VendorLedgerEntry).filter(
            models.VendorLedgerEntry.ref_type.in_(("PO_ADVANCE", "PO_PAYMENT")),
            models.VendorLedgerEntry.ref_id == po.id).all()

        # Has any of this stock been used since? Any other ledger entry on the same batch means yes.
        stock_ids = {s.id for s in stock}
        blockers = []
        for key in {(s.item_id, s.warehouse_id, s.batch_no) for s in stock}:
            others = db.query(models.StockLedgerEntry).filter(
                models.StockLedgerEntry.item_id == key[0], models.StockLedgerEntry.warehouse_id == key[1],
                models.StockLedgerEntry.batch_no == key[2]).all()
            for o in others:
                if o.id not in stock_ids:
                    blockers.append(f"item {key[0]} / warehouse {key[1]} / batch {key[2]}: {o.ref_type} #{o.ref_id} qty {o.quantity}")

        paid_in = sum(e.amount for e in ledger if e.ref_type in ("PO_ADVANCE", "PO_PAYMENT"))
        print(f"[purge] {'DRY RUN — ' if dry else ''}{po_number} (id {po.id}, status {po.status.value}, payment {po.payment_status.value})")
        print(f"[purge]   PO lines: {len(po.lines)} | GRNs: {[g.grn_number for g in grns]} | GRN lines: {len(grn_lines)}")
        print(f"[purge]   stock ledger entries to remove: {[(s.item_id, s.warehouse_id, s.batch_no, s.quantity) for s in stock]}")
        print(f"[purge]   vendor ledger entries to remove: {[(e.ref_type, e.amount) for e in ledger]}")
        print(f"[purge]   payments recorded against this PO that will disappear from the vendor ledger: Rs. {paid_in:,.2f}")
        if blockers:
            print("[purge]   ABORTED — this stock has been used/moved since receipt, nothing was changed:")
            for b in blockers:
                print(f"[purge]     {b}")
            return
        if dry:
            print("[purge]   dry run only — nothing deleted. Set PURGE_PO_DRY_RUN=0 to delete.")
            return

        backup = {
            "purchase_order": _row(po), "po_lines": [_row(l) for l in po.lines], "grns": [_row(g) for g in grns],
            "grn_lines": [_row(l) for l in grn_lines], "stock_ledger": [_row(s) for s in stock],
            "vendor_ledger": [_row(e) for e in ledger],
        }
        folder = pathlib.Path(file_storage.UPLOADS_DIR) / "purge_backups"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{po_number}_{datetime.datetime.utcnow():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(backup, indent=2, default=str))
        print(f"[purge]   backup written: {path}")

        for e in ledger:
            db.delete(e)
        for s in stock:
            db.delete(s)
        for l in grn_lines:
            db.delete(l)
        for g in grns:
            db.delete(g)
        db.flush()
        db.delete(po)   # its lines go with it
        db.commit()
        print(f"[purge]   DONE — {po_number}, its GRNs, stock and vendor-ledger entries are removed.")
    except Exception as e:
        db.rollback()
        print(f"[purge]   FAILED, nothing changed: {e}")
    finally:
        db.close()
