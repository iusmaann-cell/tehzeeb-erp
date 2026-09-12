from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import io
import openpyxl
from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["Items & UOM"])

BULK_UPLOAD_HEADERS = ["code", "name", "item_type", "uom_symbol", "reorder_level", "pack_size", "units_per_case"]
VALID_ITEM_TYPES = {"crude_oil", "chemical", "packaging", "finished_good"}


# ---- Units of Measure ----
@router.post("/uom/", response_model=schemas.UOMOut)
def create_uom(uom: schemas.UOMCreate, db: Session = Depends(get_db)):
    existing = db.query(models.UnitOfMeasure).filter(models.UnitOfMeasure.symbol == uom.symbol).first()
    if existing:
        raise HTTPException(status_code=400, detail="UOM with this symbol already exists")
    db_uom = models.UnitOfMeasure(**uom.dict())
    db.add(db_uom)
    db.commit()
    db.refresh(db_uom)
    return db_uom


@router.get("/uom/", response_model=List[schemas.UOMOut])
def list_uom(db: Session = Depends(get_db)):
    return db.query(models.UnitOfMeasure).all()


# ---- Items ----
@router.post("/items/", response_model=schemas.ItemOut)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Item).filter(models.Item.code == item.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Item code already exists")
    db_item = models.Item(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/items/", response_model=List[schemas.ItemOut])
def list_items(item_type: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Item).filter(models.Item.is_active == 1)
    if item_type:
        query = query.filter(models.Item.item_type == item_type)
    return query.all()


# ---- Bulk upload (Excel) — MUST come before /items/{item_id} routes, since a
# literal path only matches correctly if registered before the {item_id} pattern ----

@router.get("/items/bulk-upload/template")
def download_bulk_upload_template(db: Session = Depends(get_db)):
    """An .xlsx template with the right headers and a couple of example rows, plus
    a sheet listing valid unit symbols so the person filling it in doesn't have to
    guess at UOM ids."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Items"
    ws.append(BULK_UPLOAD_HEADERS)
    ws.append(["CRD-002", "Crude Palm Oil", "crude_oil", "MT", "", "", ""])
    ws.append(["BOTTLE-1L", "1L Bottle", "packaging", "pc", "", "", "12"])

    uom_sheet = wb.create_sheet("Valid Units (reference)")
    uom_sheet.append(["symbol", "name"])
    for uom in db.query(models.UnitOfMeasure).all():
        uom_sheet.append([uom.symbol, uom.name])

    type_sheet = wb.create_sheet("Valid item_type values")
    type_sheet.append(["item_type"])
    for t in sorted(VALID_ITEM_TYPES):
        type_sheet.append([t])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=items_bulk_upload_template.xlsx"},
    )


@router.post("/items/bulk-upload")
async def bulk_upload_items(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Parses an .xlsx with columns: code, name, item_type, uom_symbol, reorder_level,
    pack_size, units_per_case (see /items/bulk-upload/template). Validates every
    row before creating anything — either everything in the file succeeds, or
    nothing does, so a bad row can't leave you with a half-imported sheet.
    """
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Please upload an .xlsx file")

    contents = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Couldn't read this file — is it a valid .xlsx?")

    ws = wb["Items"] if "Items" in wb.sheetnames else wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="The sheet is empty")

    header = [str(h).strip().lower() if h else "" for h in rows[0]]
    missing_cols = [h for h in ("code", "name", "item_type", "uom_symbol") if h not in header]
    if missing_cols:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required column(s): {', '.join(missing_cols)}. Download the template to see the expected format.",
        )
    col_idx = {h: i for i, h in enumerate(header)}

    uoms = {u.symbol: u for u in db.query(models.UnitOfMeasure).all()}
    existing_codes = {i.code for i in db.query(models.Item).all()}

    to_create = []
    errors = []
    seen_codes_in_file = set()

    for row_num, row in enumerate(rows[1:], start=2):
        if row is None or all(c is None for c in row):
            continue

        def cell(name):
            idx = col_idx.get(name)
            return row[idx] if idx is not None and idx < len(row) else None

        code = str(cell("code") or "").strip()
        name = str(cell("name") or "").strip()
        item_type = str(cell("item_type") or "").strip().lower()
        uom_symbol = str(cell("uom_symbol") or "").strip()

        if not code or not name or not item_type or not uom_symbol:
            errors.append(f"Row {row_num}: code, name, item_type, and uom_symbol are all required")
            continue
        if item_type not in VALID_ITEM_TYPES:
            errors.append(f"Row {row_num}: '{item_type}' isn't a valid item_type ({', '.join(sorted(VALID_ITEM_TYPES))})")
            continue
        if uom_symbol not in uoms:
            errors.append(f"Row {row_num}: unit symbol '{uom_symbol}' doesn't exist — add it under Items first")
            continue
        if code in existing_codes:
            errors.append(f"Row {row_num}: item code '{code}' already exists")
            continue
        if code in seen_codes_in_file:
            errors.append(f"Row {row_num}: item code '{code}' appears twice in this file")
            continue
        seen_codes_in_file.add(code)

        reorder_level = cell("reorder_level")
        units_per_case = cell("units_per_case")
        pack_size = cell("pack_size")

        to_create.append(models.Item(
            code=code, name=name, item_type=item_type, uom_id=uoms[uom_symbol].id,
            reorder_level=float(reorder_level) if reorder_level not in (None, "") else None,
            units_per_case=float(units_per_case) if units_per_case not in (None, "") else None,
            pack_size=str(pack_size).strip() if pack_size not in (None, "") else None,
        ))

    if errors:
        raise HTTPException(status_code=400, detail={"message": "Fixed nothing — please correct these rows and re-upload", "errors": errors})

    for item in to_create:
        db.add(item)
    db.commit()

    return {"message": f"Created {len(to_create)} item(s)", "created_count": len(to_create)}


@router.get("/items/{item_id}", response_model=schemas.ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/items/{item_id}", response_model=schemas.ItemOut)
def update_item(item_id: int, update: schemas.ItemUpdate, db: Session = Depends(get_db)):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    data = update.dict(exclude_unset=True)
    if "code" in data and data["code"] != item.code:
        existing = db.query(models.Item).filter(models.Item.code == data["code"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Item code already exists")

    for field, value in data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """Soft delete — hides the item from active lists but keeps all history (stock, POs, BOMs) intact."""
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.is_active = 0
    db.commit()
    return {"message": "Item deactivated", "item_id": item_id}
