ADD_URL = "/api/v1/admin/tuition"
BATCH_URL = "/api/v1/admin/tuition/batch"
UNPAID_URL = "/api/v1/admin/tuition/unpaid"



def test_add_new_tuition_returns_201(client, admin):
    response = client.post(ADD_URL, headers=admin, json={"student_no": "20230003", "term": "2027-SPRING", "amount": "2000.00"})

    assert response.status_code == 201
    assert response.json()["created"] is True
    assert response.json()["currency"] == "USD"


def test_add_existing_tuition_updates_it(client, admin):
    response = client.post(ADD_URL, headers=admin, json={"student_no": "20230001", "term": "2026-FALL", "amount": "3500.00"})

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert response.json()["balance"] == "3500.00"


def test_update_below_paid_amount_returns_422(client, admin):
    response = client.post(ADD_URL, headers=admin, json={"student_no": "20230002", "term": "2026-FALL", "amount": "100.00"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AMOUNT_BELOW_PAID"


def test_add_tuition_unknown_student_returns_404(client, admin):
    response = client.post(ADD_URL, headers=admin, json={"student_no": "20239999", "term": "2026-FALL", "amount": "1.00"})

    assert response.status_code == 404


def test_bank_cannot_add_tuition(client, bank):
    response = client.post(ADD_URL, headers=bank, json={"student_no": "20230001", "term": "2026-FALL", "amount": "1.00"})

    assert response.status_code == 403



def upload(client, headers, content: str):
    return client.post(BATCH_URL, headers=headers, files={"file": ("tuition.csv", content.encode(), "text/csv")})


def test_batch_partial_success_reports_failed_rows(client, admin):
    csv_text = (
        "studentNo,term,amount,currency\n"
        "20230001,2027-SPRING,3100.00,USD\n"
        "20230003,2027-SPRING,2250.00,USD\n"
        "20239999,2027-SPRING,3000.00,USD\n"
        "20230003,2027-SPRING,2500.00,USD\n"
        "20230001,2027-FALL,-50,USD\n"
    )
    response = upload(client, admin, csv_text)

    assert response.status_code == 200
    body = response.json()
    assert body["success_count"] == 2
    assert body["failure_count"] == 3
    assert [f["line"] for f in body["failures"]] == [4, 5, 6]


def test_batch_wrong_header_returns_400(client, admin):
    response = upload(client, admin, "id,amount\n1,2\n")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CSV"



def test_unpaid_list_is_paged(client, admin):
    first = client.get(f"{UNPAID_URL}?term=2026-FALL&page=1&page_size=1", headers=admin).json()
    second = client.get(f"{UNPAID_URL}?term=2026-FALL&page=2&page_size=1", headers=admin).json()

    assert first["total_items"] == 2
    assert first["total_pages"] == 2
    assert first["items"][0]["student_no"] == "20230001"
    assert second["items"][0]["student_no"] == "20230002"


def test_unpaid_list_excludes_fully_paid(client, admin):
    body = client.get(f"{UNPAID_URL}?term=2026-FALL", headers=admin).json()

    assert "20230003" not in [item["student_no"] for item in body["items"]]


def test_unpaid_list_requires_admin(client, student1):
    response = client.get(f"{UNPAID_URL}?term=2026-FALL", headers=student1)

    assert response.status_code == 403


def test_unpaid_list_invalid_term_returns_400(client, admin):
    response = client.get(f"{UNPAID_URL}?term=fall", headers=admin)

    assert response.status_code == 400