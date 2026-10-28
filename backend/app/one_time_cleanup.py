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


def purge_orphan_payments():
    """PURGE_ORPHAN_PO_ID=<id>: remove advance/payment ledger entries whose purchase order no longer exists.
    Refuses if a PO with that id still exists. Dry run unless PURGE_PO_DRY_RUN=0. Backs up first."""
    raw = (os.getenv("PURGE_ORPHAN_PO_ID") or "").strip()
    if not raw.isdigit():
        return
    po_id = int(raw)
    dry = os.getenv("PURGE_PO_DRY_RUN", "1") != "0"
    db = SessionLocal()
    try:
        if db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first():
            print(f"[purge] orphan check: PO id {po_id} still exists — refusing, nothing changed")
            return
        rows = db.query(models.VendorLedgerEntry).filter(
            models.VendorLedgerEntry.ref_type.in_(("PO_ADVANCE", "PO_PAYMENT")),
            models.VendorLedgerEntry.ref_id == po_id).all()
        print(f"[purge] {'DRY RUN — ' if dry else ''}orphan entries for deleted PO id {po_id}: "
              f"{[(e.id, e.ref_type, e.vendor_id, e.amount, str(e.entry_date)[:10]) for e in rows]}")
        if not rows or dry:
            print("[purge]   nothing deleted." if dry else "[purge]   nothing to delete.")
            return
        folder = pathlib.Path(file_storage.UPLOADS_DIR) / "purge_backups"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"orphan_PO{po_id}_{datetime.datetime.utcnow():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps({"vendor_ledger": [_row(e) for e in rows]}, indent=2, default=str))
        print(f"[purge]   backup written: {path}")
        for e in rows:
            db.delete(e)
        db.commit()
        print(f"[purge]   DONE — {len(rows)} orphan entr{'y' if len(rows) == 1 else 'ies'} removed.")
    except Exception as e:
        db.rollback()
        print(f"[purge]   FAILED, nothing changed: {e}")
    finally:
        db.close()


def relink_batches():
    """RELINK_ITEM_NAME + RELINK_BATCHES (comma separated): stock batches whose item was deleted are
    moved onto an active item of that name (created if it doesn't exist, copying the old item's type,
    unit and pack details). Every row that carries one of those batch numbers for the old item is moved.
    Refuses if a batch belongs to an item that is still active. Dry run unless PURGE_PO_DRY_RUN=0."""
    name = (os.getenv("RELINK_ITEM_NAME") or "").strip()
    batches = [b.strip() for b in (os.getenv("RELINK_BATCHES") or "").split(",") if b.strip()]
    if not name or not batches:
        return
    dry = os.getenv("PURGE_PO_DRY_RUN", "1") != "0"
    db = SessionLocal()
    try:
        entries = db.query(models.StockLedgerEntry).filter(models.StockLedgerEntry.batch_no.in_(batches)).all()
        print(f"[purge] {'DRY RUN — ' if dry else ''}relink batches {batches} to item '{name}'")
        if not entries:
            print("[purge]   no stock entries carry those batch numbers — nothing to do")
            return
        old_ids = sorted({e.item_id for e in entries})
        old_items = {i.id: i for i in db.query(models.Item).filter(models.Item.id.in_(old_ids)).all()}
        for oid in old_ids:
            it = old_items.get(oid)
            net = {}
            for e in entries:
                if e.item_id == oid:
                    k = (e.batch_no, e.warehouse_id)
                    net[k] = net.get(k, 0.0) + e.quantity
            print(f"[purge]   current item id {oid}: name={getattr(it, 'name', '?')!r} code={getattr(it, 'code', '?')!r} "
                  f"active={getattr(it, 'is_active', '?')} | batch/warehouse net qty: {net}")
        active_old = [oid for oid in old_ids if old_items.get(oid) and old_items[oid].is_active]
        if active_old:
            print(f"[purge]   ABORTED — these batches belong to an item that is still active (ids {active_old}); nothing changed")
            return
        target = db.query(models.Item).filter(
            models.Item.is_active == 1, models.Item.name.ilike(name)).first()
        template = old_items.get(old_ids[0])
        if target:
            print(f"[purge]   will use the existing active item id {target.id} ({target.code})")
        else:
            print(f"[purge]   will create a new item '{name}' "
                  f"(type/unit/pack copied from deleted item id {template.id if template else '?'})")
        tables = [t for t in models.Base.metadata.tables.values()
                  if "item_id" in t.columns and "batch_no" in t.columns]
        counts = {}
        for t in tables:
            n = db.execute(t.select().where(t.c.batch_no.in_(batches), t.c.item_id.in_(old_ids))).fetchall()
            if n:
                counts[t.name] = len(n)
        print(f"[purge]   rows that will move to the new item: {counts}")
        if dry:
            print("[purge]   dry run only — nothing changed. Set PURGE_PO_DRY_RUN=0 to apply.")
            return
        if not target:
            base = "".join(ch for ch in name.upper() if ch.isalnum())[:20] or "ITEM"
            code, n = base, 1
            while db.query(models.Item).filter(models.Item.code == code).first():
                n += 1
                code = f"{base}-{n}"
            target = models.Item(
                code=code, name=name,
                item_type=template.item_type if template else models.ItemType.packaging,
                uom_id=template.uom_id if template else db.query(models.UnitOfMeasure).first().id,
                reorder_level=getattr(template, "reorder_level", None), pack_size=getattr(template, "pack_size", None),
                units_per_case=getattr(template, "units_per_case", None),
                density_kg_per_liter=getattr(template, "density_kg_per_liter", None), is_active=1)
            db.add(target)
            db.flush()
        backup = {"target_item_id": target.id, "old_item_ids": old_ids, "moved": {}}
        for t in tables:
            rows = db.execute(t.select().where(t.c.batch_no.in_(batches), t.c.item_id.in_(old_ids))).fetchall()
            if rows:
                backup["moved"][t.name] = [{"id": r._mapping["id"], "old_item_id": r._mapping["item_id"]} for r in rows]
                db.execute(t.update().where(t.c.batch_no.in_(batches), t.c.item_id.in_(old_ids)).values(item_id=target.id))
        folder = pathlib.Path(file_storage.UPLOADS_DIR) / "purge_backups"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"relink_{datetime.datetime.utcnow():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(backup, indent=2, default=str))
        db.commit()
        print(f"[purge]   backup written: {path}")
        print(f"[purge]   DONE — batches {batches} now belong to item id {target.id} '{target.name}' ({target.code}).")
    except Exception as e:
        db.rollback()
        print(f"[purge]   FAILED, nothing changed: {e}")
    finally:
        db.close()


def purge_sales_invoices():
    """PURGE_SALES_INVOICES=<number>,<number>: remove UNPAID sales invoices and what they posted to the
    distributor's ledger. Refuses any invoice that has a payment. Dry run unless PURGE_PO_DRY_RUN=0."""
    numbers = [n.strip() for n in (os.getenv("PURGE_SALES_INVOICES") or "").split(",") if n.strip()]
    if not numbers:
        return
    dry = os.getenv("PURGE_PO_DRY_RUN", "1") != "0"
    db = SessionLocal()
    try:
        todo = []
        for number in numbers:
            inv = db.query(models.SalesInvoice).filter(models.SalesInvoice.invoice_number == number).first()
            if not inv:
                print(f"[purge] invoice {number}: not found — nothing to do (already removed?)")
                continue
            ledger = db.query(models.DistributorLedgerEntry).filter(
                models.DistributorLedgerEntry.ref_type.in_(("SALES_INVOICE", "SALES_PAYMENT")),
                models.DistributorLedgerEntry.ref_id == inv.id).all()
            paid = inv.payment_status == models.PaymentStatus.paid or any(e.ref_type == "SALES_PAYMENT" for e in ledger)
            print(f"[purge] {'DRY RUN — ' if dry else ''}invoice {number} (id {inv.id}) distributor {inv.distributor_id} "
                  f"date {str(inv.invoice_date)[:10]} total {inv.total_amount:,.2f} status {inv.payment_status.value} "
                  f"lines {len(inv.lines)} ledger entries {[(e.ref_type, e.amount) for e in ledger]}")
            if paid:
                print(f"[purge]   SKIPPED — {number} has a payment recorded; mark it unpaid first")
                continue
            todo.append((inv, ledger))
        if dry or not todo:
            print("[purge]   dry run only — nothing deleted." if dry else "[purge]   nothing to delete.")
            return
        backup = [{"invoice": _row(i), "lines": [_row(l) for l in i.lines], "ledger": [_row(e) for e in led]} for i, led in todo]
        folder = pathlib.Path(file_storage.UPLOADS_DIR) / "purge_backups"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"sales_invoices_{datetime.datetime.utcnow():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(backup, indent=2, default=str))
        print(f"[purge]   backup written: {path}")
        for inv, led in todo:
            for e in led:
                db.delete(e)
            db.delete(inv)
        db.commit()
        print(f"[purge]   DONE — removed {[i.invoice_number for i, _ in todo]}.")
    except Exception as e:
        db.rollback()
        print(f"[purge]   FAILED, nothing changed: {e}")
    finally:
        db.close()


def run():
    purge_sales_invoices()
    relink_batches()
    purge_orphan_payments()
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
