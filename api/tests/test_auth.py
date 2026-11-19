def test_login_success_returns_token(client):
    response = client.post("/api/v1/auth/login", json={"username": "student1", "password": "Passw0rd!"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "student"
    assert body["access_token"].count(".") == 2


def test_login_wrong_password_returns_401(client):
    response = client.post("/api/v1/auth/login", json={"username": "student1", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_empty_username_returns_400(client):
    response = client.post("/api/v1/auth/login", json={"username": "", "password": "Passw0rd!"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_me_without_token_returns_401(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_me_with_tampered_token_returns_401(client, student1):
    token = student1["Authorization"] + "x"
    response = client.get("/api/v1/auth/me", headers={"Authorization": token})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"