import csv
import io
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.models import Payment, PaymentStatus, Student, Tuition, User
from app.schemas import (
    AddTuitionRequest,
    BatchFailure,
    BatchResult,
    PaymentRequest,
    PaymentResponse,
    TermBalance,
    TuitionRecord,
    TuitionSummary,
    UnpaidItem,
    UnpaidPage,
)

CSV_HEADER = ["studentNo", "term", "amount", "currency"]
CSV_MAX_ROWS = 1000


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


def _upsert_tuition(db: Session, req: AddTuitionRequest) -> tuple[Tuition, bool]:
    """Creates the tuition row or updates its amount. Returns (row, created). Does not commit."""
    if db.get(Student, req.student_no) is None:
        raise ApiError(404, "STUDENT_NOT_FOUND", f"Student {req.student_no} not found.")

    tuition = db.scalar(
        select(Tuition)
        .where(Tuition.student_no == req.student_no, Tuition.term == req.term)
        .with_for_update()
    )
    if tuition is None:
        tuition = Tuition(
            student_no=req.student_no,
            term=req.term,
            amount=req.amount,
            currency=req.currency,
            paid_amount=Decimal("0.00"),
        )
        db.add(tuition)
        db.flush()
        return tuition, True

    if req.amount < tuition.paid_amount:
        raise ApiError(
            422,
            "AMOUNT_BELOW_PAID",
            "New tuition amount cannot be lower than the amount already paid.",
            details=[{"paid_amount": str(tuition.paid_amount), "requested": str(req.amount)}],
        )
    if req.currency != tuition.currency and tuition.paid_amount > 0:
        raise ApiError(422, "CURRENCY_CHANGE_NOT_ALLOWED", "Currency cannot change after a payment was made.")

    tuition.amount = req.amount
    tuition.currency = req.currency
    db.flush()
    return tuition, False


def add_or_update_tuition(db: Session, req: AddTuitionRequest) -> TuitionRecord:
    """Adds a tuition record, or updates it if the student already has one for that term."""
    try:
        tuition, created = _upsert_tuition(db, req)
        db.commit()
    except ApiError:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "CONCURRENT_UPDATE", "The same tuition record was changed at the same time, retry.")

    return TuitionRecord(
        student_no=tuition.student_no,
        term=tuition.term,
        currency=tuition.currency,
        amount=tuition.amount,
        paid_amount=tuition.paid_amount,
        balance=tuition.balance,
        created=created,
    )


def import_tuition_csv(db: Session, content: bytes) -> BatchResult:
    """Imports a tuition CSV row by row. Bad rows are reported, good rows are saved."""
    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError(400, "INVALID_CSV", "File must be UTF-8 encoded.")

    reader = csv.DictReader(io.StringIO(text_content))
    header = [h.strip() for h in (reader.fieldnames or [])]
    if header != CSV_HEADER:
        raise ApiError(400, "INVALID_CSV", f"CSV header must be exactly: {','.join(CSV_HEADER)}")

    rows = list(reader)
    if not rows:
        raise ApiError(400, "INVALID_CSV", "CSV file has no data rows.")
    if len(rows) > CSV_MAX_ROWS:
        raise ApiError(400, "INVALID_CSV", f"CSV file can contain at most {CSV_MAX_ROWS} rows.")

    seen: set[tuple[str, str]] = set()
    failures: list[BatchFailure] = []
    success = 0

    for line_no, row in enumerate(rows, start=2):
        student_no = (row.get("studentNo") or "").strip()
        term = (row.get("term") or "").strip()

        if (student_no, term) in seen:
            failures.append(BatchFailure(line=line_no, student_no=student_no, reason="Duplicate student/term in this file."))
            continue
        seen.add((student_no, term))

        try:
            req = AddTuitionRequest(
                student_no=student_no,
                term=term,
                amount=(row.get("amount") or "").strip(),
                currency=(row.get("currency") or "").strip(),
            )
        except ValidationError as exc:
            reason = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
            failures.append(BatchFailure(line=line_no, student_no=student_no, reason=reason))
            continue

        try:
            with db.begin_nested():
                _upsert_tuition(db, req)
            success += 1
        except ApiError as exc:
            failures.append(BatchFailure(line=line_no, student_no=student_no, reason=exc.message))
        except IntegrityError:
            failures.append(BatchFailure(line=line_no, student_no=student_no, reason="Database constraint violated."))

    db.commit()
    return BatchResult(
        total_rows=len(rows),
        success_count=success,
        failure_count=len(failures),
        failures=failures,
    )


def list_unpaid_tuition(db: Session, term: str, page: int, page_size: int) -> UnpaidPage:
    """Lists students with a positive balance for a term, with paging."""
    base = (
        select(Tuition, Student.full_name)
        .join(Student, Student.student_no == Tuition.student_no)
        .where(Tuition.term == term, Tuition.amount - Tuition.paid_amount > 0)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.execute(
        base.order_by(Tuition.student_no).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        UnpaidItem(
            student_no=t.student_no,
            full_name=name,
            currency=t.currency,
            tuition=t.amount,
            paid=t.paid_amount,
            balance=t.balance,
        )
        for t, name in rows
    ]
    return UnpaidPage(
        term=term,
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=(total + page_size - 1) // page_size,
        items=items,
    )