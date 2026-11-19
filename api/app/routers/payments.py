from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import ApiError
from app.models import Role
from app.schemas import PaymentRequest, PaymentResponse
from app.services import process_payment

router = APIRouter(prefix="/api/v1/banking", tags=["payments"])


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def pay_tuition(
    body: PaymentRequest,
    user: CurrentUser = Depends(require_roles(Role.bank, Role.student)),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Pays tuition. Banks can pay for anyone, students only for themselves."""
    if user.role == Role.student and user.student_no != body.student_no:
        raise ApiError(403, "FORBIDDEN_RESOURCE", "Students can only pay their own tuition.")

    return process_payment(db, body, user.username)