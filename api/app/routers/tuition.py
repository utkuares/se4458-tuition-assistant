
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import ApiError
from app.models import Role
from app.schemas import TuitionSummary
from app.services import consume_mobile_quota, get_tuition_summary

router = APIRouter(prefix="/api/v1", tags=["tuition"])


@router.get("/banking/tuition/{student_no}", response_model=TuitionSummary)
def banking_query_tuition(
    student_no: str = Path(pattern=r"^\d{1,20}$", examples=["20230001"]),
    term: str | None = Query(default=None, pattern=r"^\d{4}-(FALL|SPRING|SUMMER)$", examples=["2026-FALL"]),
    user: CurrentUser = Depends(require_roles(Role.bank, Role.student)),
    db: Session = Depends(get_db),
) -> TuitionSummary:
    """Query tuition and balance. Bank: any student. Student: only their own number."""
    if user.role == Role.student and user.student_no != student_no:
        raise ApiError(403, "FORBIDDEN_RESOURCE", "Students can only view their own tuition.")

    return get_tuition_summary(db, student_no, term)



@router.get("/mobile/tuition/{student_no}", response_model=TuitionSummary)
def mobile_query_tuition(
    student_no: str = Path(pattern=r"^\d{1,20}$", examples=["20230001"]),
    term: str | None = Query(default=None, pattern=r"^\d{4}-(FALL|SPRING|SUMMER)$", examples=["2026-FALL"]),
    db: Session = Depends(get_db),
) -> TuitionSummary:
    """Query tuition without login. Limited to 3 queries per student number per day."""
    consume_mobile_quota(db, student_no)
    return get_tuition_summary(db, student_no, term)