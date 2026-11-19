from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.models import Payment, PaymentStatus, Student, Tuition, User
from app.schemas import PaymentRequest, PaymentResponse, TermBalance, TuitionSummary


def get_tuition_summary(db: Session, student_no: str, term: str | None = None) -> TuitionSummary:
    """Returns tuition, paid amount and balance for one term or all terms."""
    if db.get(Student, student_no) is None:
        raise ApiError(404, "STUDENT_NOT_FOUND", f"Student {student_no} not found.")

    query = select(Tuition).where(Tuition.student_no == student_no).order_by(Tuition.term)
    if term is not None:
        query = query.where(Tuition.term == term)
    rows = db.scalars(query).all()

    if term is not None and not rows:
        raise ApiError(404, "TUITION_NOT_FOUND", f"No tuition record for student {student_no} in term {term}.")

    terms = [
        TermBalance(term=t.term, currency=t.currency, tuition=t.amount, paid=t.paid_amount, balance=t.balance)
        for t in rows
    ]
    total_tuition = sum((t.tuition for t in terms), Decimal("0.00"))
    total_paid = sum((t.paid for t in terms), Decimal("0.00"))

    return TuitionSummary(
        student_no=student_no,
        scope="TERM" if term else "ALL_TERMS",
        total_tuition=total_tuition,
        total_paid=total_paid,
        balance=total_tuition - total_paid,
        terms=terms,
    )


def consume_mobile_quota(db: Session, student_no: str) -> int:
    """Counts one mobile query for today and raises 429 if the daily limit is reached."""
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.app_timezone)).date()

    used = db.execute(
        text("""
            INSERT INTO mobile_query_usage (student_no, query_date, count)
            VALUES (:student_no, :today, 1)
            ON CONFLICT (student_no, query_date)
            DO UPDATE SET count = mobile_query_usage.count + 1
            WHERE mobile_query_usage.count < :limit
            RETURNING count
        """),
        {"student_no": student_no, "today": today, "limit": settings.mobile_daily_query_limit},
    ).scalar()
    db.commit()

    if used is None:
        raise ApiError(
            429,
            "DAILY_LIMIT_EXCEEDED",
            f"Mobile tuition query limit of {settings.mobile_daily_query_limit} per day reached for this student.",
        )
    return used


def _duplicate_transaction(transaction_id: str) -> ApiError:
    """Builds the 409 error for a transaction id that was already used."""
    return ApiError(409, "DUPLICATE_TRANSACTION", f"Transaction {transaction_id} was already processed.")


def process_payment(db: Session, req: PaymentRequest, paid_by_username: str) -> PaymentResponse:
    """Records a payment in one transaction while the tuition row is locked."""
    try:
        if db.scalar(select(Payment.id).where(Payment.transaction_id == req.transaction_id)) is not None:
            raise _duplicate_transaction(req.transaction_id)

        tuition = db.scalar(
            select(Tuition)
            .where(Tuition.student_no == req.student_no, Tuition.term == req.term)
            .with_for_update()
        )
        if tuition is None:
            raise ApiError(404, "TUITION_NOT_FOUND", f"No tuition record for student {req.student_no} in term {req.term}.")

        if req.amount > tuition.balance:
            raise ApiError(
                422,
                "AMOUNT_EXCEEDS_BALANCE",
                "Payment amount exceeds the outstanding balance.",
                details=[{"balance": str(tuition.balance), "requested": str(req.amount)}],
            )

        payer_id = db.scalar(select(User.id).where(User.username == paid_by_username))
        tuition.paid_amount = tuition.paid_amount + req.amount
        db.add(
            Payment(
                transaction_id=req.transaction_id,
                student_no=req.student_no,
                term=req.term,
                amount=req.amount,
                status=PaymentStatus.completed,
                paid_by_user_id=payer_id,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _duplicate_transaction(req.transaction_id)
    except ApiError:
        db.rollback()
        raise

    return PaymentResponse(
        status="COMPLETED",
        transaction_id=req.transaction_id,
        student_no=req.student_no,
        term=req.term,
        amount=req.amount,
        currency=tuition.currency,
        paid_amount=tuition.paid_amount,
        remaining_balance=tuition.balance,
    )