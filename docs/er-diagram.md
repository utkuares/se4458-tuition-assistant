# ER Diagram

![ER Diagram](er-diagram.png)

```mermaid
erDiagram
    %% A student may have more than one tuition record.
    STUDENTS ||--o{ TUITIONS : "has"
    %% A student may receive more than one payment.
    STUDENTS ||--o{ PAYMENTS : "receives"
    %% A student can have at most one login account.
    STUDENTS |o--o| USERS : "login (role=student)"
    %% A single account can make multiple payments (users = accounts).
    USERS ||--o{ PAYMENTS : "paid_by"

    STUDENTS {
        varchar student_no PK
        varchar full_name
        varchar email UK
    }
    USERS {
        int id PK
        varchar username UK
        varchar password_hash "bcrypt"
        enum role "student | bank | admin"
        varchar student_no FK "NULL unless role=student"
    }
    TUITIONS {
        int id PK
        varchar student_no FK
        varchar term "e.g. 2026-FALL"
        numeric amount "NUMERIC(12,2)"
        char currency "ISO-4217, e.g. USD"
        numeric paid_amount "NUMERIC(12,2), <= amount"
        timestamptz created_at
        timestamptz updated_at
    }
    PAYMENTS {
        int id PK
        varchar transaction_id UK "idempotency key"
        varchar student_no FK
        varchar term
        numeric amount "NUMERIC(12,2), > 0"
        enum status
        int paid_by_user_id FK
        timestamptz created_at
    }
    MOBILE_QUERY_USAGE {
        varchar student_no PK
        date query_date PK
        int count "max 3 per day"
    }
```

## Rules enforced by the database

| Rule                                        | Constraint                                                                       |
| ------------------------------------------- | -------------------------------------------------------------------------------- |
| One tuition per student and term            | `UNIQUE (student_no, term)`                                                      |
| No overpayment                              | `CHECK (paid_amount <= amount)`                                                  |
| No negative amounts                         | `CHECK (amount >= 0)`, `CHECK (paid_amount >= 0)`, `CHECK (payments.amount > 0)` |
| Duplicate transaction IDs rejected          | `UNIQUE (transaction_id)`                                                        |
| Only student users link to a student number | `CHECK` on `users`                                                               |
| Currency is a 3-letter ISO code             | `CHECK (currency ~ '^[A-Z]{3}$')`                                                |

Balance is not stored; it is always calculated as `amount - paid_amount`.
