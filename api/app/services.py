from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app.config import get_settings

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Student, Tuition
from app.schemas import TermBalance, TuitionSummary


def get_tuition_summary(db: Session, student_no: str, term: str | None = None) -> TuitionSummary:
    """Return tuition, paid amount and balance for a student (one term or all terms)."""
    if db.get(Student, student_no) is None:
        raise ApiError(404, "STUDENT_NOT_FOUND", f"Student {student_no} not found.")

    query = select(Tuition).where(Tuition.student_no == student_no).order_by(Tuition.term)
    if term is not None:
        query = query.where(Tuition.term == term)
    rows = db.scalars(query).all()

    if term is not None and not rows:
        raise ApiError(404, "TUITION_NOT_FOUND", f"No tuition record for student {student_no} in term {term}.")

    terms = [
        TermBalance(
            term=t.term,
            currency=t.currency,
            tuition=t.amount,
            paid=t.paid_amount,
            balance=t.balance,
        )
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
    """Atomically count one mobile query for today. Raises 429 when the daily limit is reached."""
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