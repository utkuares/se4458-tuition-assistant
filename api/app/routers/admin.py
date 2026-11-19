from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.errors import ApiError
from app.models import Role
from app.schemas import TERM_PATTERN, AddTuitionRequest, BatchResult, TuitionRecord, UnpaidPage
from app.services import add_or_update_tuition, import_tuition_csv, list_unpaid_tuition

CSV_MAX_BYTES = 1_000_000

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles(Role.admin))],
)


@router.post("/tuition", response_model=TuitionRecord)
def add_tuition(body: AddTuitionRequest, response: Response, db: Session = Depends(get_db)) -> TuitionRecord:
    """Adds a tuition record (201). If the student already has one for that term, updates it (200)."""
    record = add_or_update_tuition(db, body)
    response.status_code = 201 if record.created else 200
    return record


@router.post("/tuition/batch", response_model=BatchResult)
def add_tuition_batch(
    file: UploadFile = File(description="CSV with header: studentNo,term,amount,currency"),
    db: Session = Depends(get_db),
) -> BatchResult:
    """Adds or updates many tuition records from a CSV file and reports failed rows."""
    content = file.file.read(CSV_MAX_BYTES + 1)
    if len(content) > CSV_MAX_BYTES:
        raise ApiError(400, "INVALID_CSV", "CSV file must be at most 1 MB.")
    return import_tuition_csv(db, content)


@router.get("/tuition/unpaid", response_model=UnpaidPage)
def unpaid_tuition_status(
    term: str = Query(pattern=TERM_PATTERN, examples=["2026-FALL"]),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> UnpaidPage:
    """Lists students who still owe money for the given term (paged)."""
    return list_unpaid_tuition(db, term, page, page_size)