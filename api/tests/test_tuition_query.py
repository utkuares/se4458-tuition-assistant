
def test_student_can_query_own_tuition_all_terms(client, student1):
    response = client.get("/api/v1/banking/tuition/20230001", headers=student1)

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "ALL_TERMS"
    assert body["balance"] == "6000.00"
    assert len(body["terms"]) == 2


def test_student_can_query_single_term(client, student1):
    response = client.get("/api/v1/banking/tuition/20230001?term=2026-FALL", headers=student1)

    assert response.status_code == 200
    assert response.json()["scope"] == "TERM"
    assert response.json()["balance"] == "3000.00"


def test_student_cannot_query_another_student(client, student1):
    response = client.get("/api/v1/banking/tuition/20230002", headers=student1)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_RESOURCE"


def test_bank_can_query_any_student(client, bank):
    response = client.get("/api/v1/banking/tuition/20230002", headers=bank)

    assert response.status_code == 200
    assert response.json()["balance"] == "200.00"


def test_admin_cannot_use_banking_query(client, admin):
    response = client.get("/api/v1/banking/tuition/20230001", headers=admin)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


def test_banking_query_without_token_returns_401(client):
    response = client.get("/api/v1/banking/tuition/20230001")

    assert response.status_code == 401


def test_banking_query_unknown_student_returns_404(client, bank):
    response = client.get("/api/v1/banking/tuition/20239999", headers=bank)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STUDENT_NOT_FOUND"



def test_mobile_query_works_without_token(client):
    response = client.get("/api/v1/mobile/tuition/20230001")

    assert response.status_code == 200
    assert response.json()["balance"] == "6000.00"


def test_mobile_query_fourth_call_returns_429(client):
    for _ in range(3):
        assert client.get("/api/v1/mobile/tuition/20230001").status_code == 200

    response = client.get("/api/v1/mobile/tuition/20230001")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "DAILY_LIMIT_EXCEEDED"


def test_mobile_limit_is_per_student(client):
    for _ in range(3):
        client.get("/api/v1/mobile/tuition/20230001")

    response = client.get("/api/v1/mobile/tuition/20230002")

    assert response.status_code == 200


def test_mobile_query_invalid_student_no_returns_400(client):
    response = client.get("/api/v1/mobile/tuition/abc")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"