from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])

# Tables intentionally preserved across a reset — configuration, not test data.
PRESERVED_TABLES = {"invoice_settings"}


@router.post("/reset-all-data")
def reset_all_data(confirm: str = "", db: Session = Depends(get_db)):
    """
    Permanently deletes every row from every table (except the ones listed in
    PRESERVED_TABLES) and leaves the schema itself intact — for wiping test data
    and starting fresh. Tables are cleared in reverse of SQLAlchemy's dependency
    order, so child rows are always removed before the parent rows they
    reference, avoiding foreign-key violations without needing a hand-maintained
    table list that could go stale as new phases add tables.

    There's no authentication on this system yet, so the confirm=RESET query
    param is a safeguard against triggering this by accident (a stray request,
    a bookmark) — not real access control. Treat this endpoint as sensitive:
    anyone with the API URL and this one detail can wipe all data.
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
        "message": f"Wiped {len(cleared)} table(s). Invoice settings were preserved.",
        "cleared_tables": cleared,
    }
