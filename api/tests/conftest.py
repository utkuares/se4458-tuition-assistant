"""Test settings. Tests use their own database and do not need the cloud or an LLM."""

import os
import tempfile
from decimal import Decimal
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://tuition:tuition_test_pw@localhost:5433/tuition_test",
)

# Point the app to the test database and to throw-away keys before importing it.
_keys_dir = Path(tempfile.mkdtemp())
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
(_keys_dir / "private.pem").write_bytes(
    _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
)
(_keys_dir / "public.pem").write_bytes(
    _key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_PRIVATE_KEY_PATH"] = str(_keys_dir / "private.pem")
os.environ["JWT_PUBLIC_KEY_PATH"] = str(_keys_dir / "public.pem")

import bcrypt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, Student, Tuition, User  # noqa: E402

PASSWORD = "Passw0rd!"
_PASSWORD_HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture(scope="session", autouse=True)
def create_schema():
    """Creates all tables once in the test database."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def seed_data():
    """Empties every table and inserts the same demo data before each test."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE payments, tuitions, users, students, mobile_query_usage RESTART IDENTITY CASCADE"))

    with SessionLocal.begin() as db:
        db.add_all([
            Student(student_no="20230001", full_name="Ayse Yilmaz", email="ayse@example.edu"),
            Student(student_no="20230002", full_name="Mehmet Demir", email="mehmet@example.edu"),
            Student(student_no="20230003", full_name="Zeynep Kaya", email="zeynep@example.edu"),
        ])
        db.flush()
        db.add_all([
            Tuition(student_no="20230001", term="2026-FALL", amount=Decimal("3000.00"), paid_amount=Decimal("0.00")),
            Tuition(student_no="20230001", term="2027-SPRING", amount=Decimal("3000.00"), paid_amount=Decimal("0.00")),
            Tuition(student_no="20230002", term="2026-FALL", amount=Decimal("3000.00"), paid_amount=Decimal("2800.00")),
            Tuition(student_no="20230003", term="2026-FALL", amount=Decimal("2250.00"), paid_amount=Decimal("2250.00")),
            User(username="student1", password_hash=_PASSWORD_HASH, role=Role.student, student_no="20230001"),
            User(username="student2", password_hash=_PASSWORD_HASH, role=Role.student, student_no="20230002"),
            User(username="bank1", password_hash=_PASSWORD_HASH, role=Role.bank),
            User(username="admin1", password_hash=_PASSWORD_HASH, role=Role.admin),
        ])
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def auth_header(client: TestClient, username: str) -> dict:
    """Logs in and returns the Authorization header for that user."""
    response = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def student1(client):
    return auth_header(client, "student1")


@pytest.fixture
def bank(client):
    return auth_header(client, "bank1")


@pytest.fixture
def admin(client):
    return auth_header(client, "admin1")