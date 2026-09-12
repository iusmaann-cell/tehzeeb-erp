import datetime
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, google_drive
from ..database import get_db

router = APIRouter(prefix="/expenses", tags=["Expenses"])

ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")
MAX_PHOTO_BYTES = 5 * 1024 * 1024


@router.post("/", response_model=schemas.ExpenseOut)
async def create_expense(
    data: str = Form(..., description="JSON-encoded ExpenseCreate payload"),
    bill_photo: UploadFile = File(..., description="Photo of the receipt/bill — required"),
    db: Session = Depends(get_db),
):
    """A bill photo is compulsory for every expense, uploaded to Google Drive
    (see app/google_drive.py for why not local disk or the database)."""
    try:
        expense = schemas.ExpenseCreate.model_validate_json(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid data payload: {e}")

    if bill_photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Bill photo must be a JPEG, PNG, WEBP, or HEIC image")
    photo_bytes = await bill_photo.read()
    if not photo_bytes:
        raise HTTPException(status_code=400, detail="Bill photo file is empty")
    if len(photo_bytes) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Bill photo must be under 5MB")

    payload = expense.dict()
    if not payload.get("expense_date"):
        payload["expense_date"] = datetime.datetime.utcnow()

    try:
        upload_result = google_drive.upload_bill_photo(
            photo_bytes, f"EXPENSE_{payload['category']}_{bill_photo.filename}", bill_photo.content_type,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Couldn't upload bill photo to Google Drive: {e}")

    payload["bill_photo_url"] = upload_result["view_url"]
    payload["bill_photo_drive_file_id"] = upload_result["file_id"]

    db_expense = models.Expense(**payload)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


@router.get("/", response_model=List[schemas.ExpenseOut])
def list_expenses(plant: str = None, category: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Expense)
    if plant:
        query = query.filter(models.Expense.plant == plant)
    if category:
        query = query.filter(models.Expense.category == category)
    return query.order_by(models.Expense.expense_date.desc()).all()


@router.put("/{expense_id}", response_model=schemas.ExpenseOut)
def update_expense(expense_id: int, update: schemas.ExpenseUpdate, db: Session = Depends(get_db)):
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"message": "Expense deleted", "expense_id": expense_id}
