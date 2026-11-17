
import sys

from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import bcrypt
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Role, Student, Tuition, User


DEMO_PASSWORD = "Passw0rd!"

STUDENTS = [
    ("20230001", "Ayse Yilmaz", "ayse.yilmaz@student.example.edu"),
    ("20230002", "Mehmet Demir", "mehmet.demir@student.example.edu"),
    ("20230003", "Zeynep Kaya", "zeynep.kaya@student.example.edu"),
]

TUITIONS = [
    ("20230001", "2026-FALL", "3000.00", "0.00"),
    ("20230001", "2027-SPRING", "3000.00", "0.00"),
    ("20230002", "2026-FALL", "3000.00", "2800.00"),
    ("20230003", "2026-FALL", "2250.00", "2250.00"),
]


USERS = [
    ("student1", Role.student, "20230001"),
    ("student2", Role.student, "20230002"),
    ("student3", Role.student, "20230003"),
    ("bank1", Role.bank, None),
    ("admin1", Role.admin, None),
]


def main() -> None:
    pw_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()
    with SessionLocal.begin() as db:
        for no, name, email in STUDENTS:
            if db.get(Student, no) is None:
                db.add(Student(student_no=no, full_name=name, email=email))
        db.flush()


        for no, term, amount, paid in TUITIONS:
            exists = db.scalar(
                select(Tuition).where(Tuition.student_no == no, Tuition.term == term)
            )
            if exists is None:
                db.add(Tuition(student_no=no, term=term, amount=Decimal(amount),
                               paid_amount=Decimal(paid), currency="USD")) 
                # SELECT * FROM tuitions WHERE student_no = '20230001' AND term = '2026-FALL';

        
        for username, role, student_no in USERS:
            if db.scalar(select(User).where(User.username == username)) is None:
                db.add(User(username=username, password_hash=pw_hash,
                            role=role, student_no=student_no))

    print("Seed tamamlandı.")


if __name__ == "__main__":
    main()  