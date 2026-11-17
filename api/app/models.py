import enum

from datetime import date,datetime

from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

Money = Numeric(12, 2)

class Role(str, enum.Enum):
    student = "student"
    bank = "bank"
    admin = "admin"

class Student(Base):
    __tablename__ = "students"

    student_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True)

    tuitions: Mapped[list["Tuition"]] = relationship(back_populates="student")

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(role = 'student' AND student_no IS NOT NULL) OR (role <> 'student' AND student_no IS NULL)",
            name="ck_users_student_link",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"))
    student_no: Mapped[str | None] = mapped_column(ForeignKey("students.student_no"), nullable=True)


class Tuition(Base):
    __tablename__ = "tuitions"

    __table_args__ = (
        UniqueConstraint("student_no","term",name="uq_tuitions_student_term"), # Rule / Rule name
        CheckConstraint("amount >= 0", name = "ck_tuitions_amount_nonneg"),
        CheckConstraint("paid_amount >= 0", name = "ck_tuitions_paid_nonneg"),
        CheckConstraint("paid_amount <= amount", name = "ck_tuitions_paid_le_amount"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_tuitions_currency_iso"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_no: Mapped[str] = mapped_column(ForeignKey("students.student_no"), index=True)
    term: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    paid_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"), server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped[Student] = relationship(back_populates="tuitions")


@property
def balance(self) -> Decimal:
        return self.amount - self.paid_amount


class PaymentStatus(str,enum.Enum):
    completed = "COMPLETED"


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payments_amount_pos"),)
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True)
    
    student_no: Mapped[str] = mapped_column(ForeignKey("students.student_no"), index=True)
    term: Mapped[str] = mapped_column(String(20))
    
    amount: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.completed
    )
    paid_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())   


class MobileQueryUsage(Base):
    __tablename__ = "mobile_query_usage"

    student_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    query_date: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
