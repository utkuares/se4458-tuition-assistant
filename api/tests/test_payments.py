import threading
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Payment, Tuition

URL = "/api/v1/banking/payments"


def payment(amount="500.00", tx="TX-1", student_no="20230001", term="2026-FALL"):
    return {"student_no": student_no, "term": term, "amount": amount, "transaction_id": tx}


def test_payment_success_reduces_balance(client, student1):
    response = client.post(URL, headers=student1, json=payment())

    assert response.status_code == 201
    assert response.json()["remaining_balance"] == "2500.00"


def test_duplicate_transaction_id_returns_409_and_charges_once(client, student1):
    client.post(URL, headers=student1, json=payment(tx="TX-DUP"))
    response = client.post(URL, headers=student1, json=payment(tx="TX-DUP"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_TRANSACTION"
    with SessionLocal() as db:
        tuition = db.scalar(select(Tuition).where(Tuition.student_no == "20230001", Tuition.term == "2026-FALL"))
        assert tuition.paid_amount == Decimal("500.00")


def test_payment_above_balance_returns_422(client, student1):
    response = client.post(URL, headers=student1, json=payment(amount="3000.01"))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AMOUNT_EXCEEDS_BALANCE"


def test_full_payment_brings_balance_to_zero(client, bank):
    response = client.post(URL, headers=bank, json=payment(amount="200.00", student_no="20230002", tx="TX-FULL"))

    assert response.status_code == 201
    assert response.json()["remaining_balance"] == "0.00"


def test_student_cannot_pay_for_another_student(client, student1):
    response = client.post(URL, headers=student1, json=payment(student_no="20230002"))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_RESOURCE"


def test_admin_cannot_pay(client, admin):
    response = client.post(URL, headers=admin, json=payment())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


def test_zero_or_too_precise_amount_returns_400(client, student1):
    assert client.post(URL, headers=student1, json=payment(amount="0")).status_code == 400
    assert client.post(URL, headers=student1, json=payment(amount="10.005")).status_code == 400


def test_payment_for_missing_term_returns_404(client, student1):
    response = client.post(URL, headers=student1, json=payment(term="2030-FALL"))

    assert response.status_code == 404


def test_parallel_payments_cannot_exceed_balance(student1):
    """Two payments of 2000 hit a 3000 balance at the same moment: only one may succeed."""
    barrier = threading.Barrier(2)
    results = []

    def pay(tx):
        local_client = TestClient(app)
        barrier.wait()
        results.append(local_client.post(URL, headers=student1, json=payment(amount="2000.00", tx=tx)).status_code)

    threads = [threading.Thread(target=pay, args=(f"TX-P{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [201, 422]
    with SessionLocal() as db:
        tuition = db.scalar(select(Tuition).where(Tuition.student_no == "20230001", Tuition.term == "2026-FALL"))
        assert tuition.paid_amount == Decimal("2000.00")
        assert len(db.scalars(select(Payment)).all()) == 1