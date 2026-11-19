from decimal import Decimal

from pydantic import BaseModel, Field

TERM_PATTERN = r"^\d{4}-(FALL|SPRING|SUMMER)$"
STUDENT_NO_PATTERN = r"^\d{1,20}$"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60, examples=["student1"])
    password: str = Field(min_length=1, max_length=128, examples=["Passw0rd!"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class TermBalance(BaseModel):
    term: str
    currency: str
    tuition: Decimal
    paid: Decimal
    balance: Decimal


class TuitionSummary(BaseModel):
    student_no: str
    scope: str
    total_tuition: Decimal
    total_paid: Decimal
    balance: Decimal
    terms: list[TermBalance]


class PaymentRequest(BaseModel):
    student_no: str = Field(pattern=STUDENT_NO_PATTERN, examples=["20230001"])
    term: str = Field(pattern=TERM_PATTERN, examples=["2026-FALL"])
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, examples=["500.00"])
    transaction_id: str = Field(min_length=1, max_length=64, examples=["TX-0001"])


class PaymentResponse(BaseModel):
    status: str
    transaction_id: str
    student_no: str
    term: str
    amount: Decimal
    currency: str
    paid_amount: Decimal
    remaining_balance: Decimal