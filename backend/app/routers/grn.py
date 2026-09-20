from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, google_drive
from ..database import get_db

router = APIRouter(prefix="/grn", tags=["GRN (Goods Received Note)"])

ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")
MAX_PHOTO_BYTES = 5 * 1024 * 1024


@router.post("/", response_model=schemas.GRNOut)
async def create_grn(
    data: str = Form(..., description="JSON-encoded GRNCreate payload"),
    bill_photo: UploadFile = File(..., description="Photo of the vendor's bill/receipt — required"),
    db: Session = Depends(get_db),
):
    """
    Recording a GRN does four things atomically:
    1. Creates the GRN + line records (with the bill photo uploaded to Google Drive)
    2. Adds stock-in entries to the stock ledger (per batch, per warehouse)
    3. Adds a debit entry to the vendor ledger for the bill value
    4. Updates received_quantity on the matching PO lines

    A bill photo is compulsory — every GRN needs a photo of the vendor's paperwork
    for audit purposes. The photo goes to Google Drive rather than local disk or the
    database (see app/google_drive.py for why), so a Drive service account must be
    configured on the server for this endpoint to work.
    """
    try:
        grn = schemas.GRNCreate.model_validate_json(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid data payload: {e}")

    if bill_photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Bill photo must be a JPEG, PNG, WEBP, or HEIC image")
    photo_bytes = await bill_photo.read()
    if not photo_bytes:
        raise HTTPException(status_code=400, detail="Bill photo file is empty")
    if len(photo_bytes) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Bill photo must be under 5MB")

    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == grn.purchase_order_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    existing = db.query(models.GRN).filter(models.GRN.grn_number == grn.grn_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="GRN number already exists")

    db_grn = models.GRN(
        grn_number=grn.grn_number,
        purchase_order_id=grn.purchase_order_id,
        vehicle_no=grn.vehicle_no,
        notes=grn.notes,
    )
    db.add(db_grn)
    db.flush()

    total_bill_value = 0.0

    for line in grn.lines:
        po_line = db.query(models.PurchaseOrderLine).filter(
            models.PurchaseOrderLine.id == line.po_line_id
        ).first()
        if not po_line:
            raise HTTPException(status_code=404, detail=f"PO line {line.po_line_id} not found")

        remaining = po_line.quantity - po_line.received_quantity
        if line.quantity > remaining + 1e-6:
            raise HTTPException(
                status_code=400,
                detail=f"Received quantity ({line.quantity}) exceeds remaining PO quantity ({remaining}) "
                       f"for item {line.item_id}",
            )

        db_line = models.GRNLine(
            grn_id=db_grn.id,
            po_line_id=line.po_line_id,
            item_id=line.item_id,
            warehouse_id=line.warehouse_id,
            batch_no=line.batch_no,
            quantity=line.quantity,
            rate=line.rate,
        )
        db.add(db_line)

        stock_entry = models.StockLedgerEntry(
            item_id=line.item_id,
            warehouse_id=line.warehouse_id,
            batch_no=line.batch_no,
            quantity=line.quantity,   # positive = in
            rate=line.rate,
            is_toll_stock=0,
            ref_type="GRN",
            ref_id=db_grn.id,
        )
        db.add(stock_entry)

        po_line.received_quantity += line.quantity
        total_bill_value += line.quantity * line.rate

    all_lines = db.query(models.PurchaseOrderLine).filter(
        models.PurchaseOrderLine.purchase_order_id == po.id
    ).all()
    if all(l.received_quantity >= l.quantity - 1e-6 for l in all_lines):
        po.status = models.POStatus.completed
    else:
        po.status = models.POStatus.partially_received

    ledger_entry = models.VendorLedgerEntry(
        vendor_id=po.vendor_id,
        direction=models.LedgerDirection.debit,
        amount=total_bill_value,
        ref_type="GRN_BILL",
        ref_id=db_grn.id,
        notes=f"Bill for GRN {grn.grn_number}",
    )
    db.add(ledger_entry)

    # Everything above is validated and staged (flushed, not committed) — only now
    # do the network call to Drive, so a failed upload doesn't leave a half-created
    # GRN and a failed validation doesn't waste an upload.
    try:
        upload_result = google_drive.upload_bill_photo(
            photo_bytes, f"{grn.grn_number}_{bill_photo.filename}", bill_photo.content_type,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Couldn't upload bill photo to Google Drive: {e}")

    db_grn.bill_photo_url = upload_result["view_url"]
    db_grn.bill_photo_drive_file_id = upload_result["file_id"]

    db.commit()
    db.refresh(db_grn)
    return db_grn


@router.get("/", response_model=List[schemas.GRNOut])
def list_grns(db: Session = Depends(get_db)):
    return db.query(models.GRN).all()


@router.get("/{grn_id}", response_model=schemas.GRNOut)
def get_grn(grn_id: int, db: Session = Depends(get_db)):
    grn = db.query(models.GRN).filter(models.GRN.id == grn_id).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    return grn
