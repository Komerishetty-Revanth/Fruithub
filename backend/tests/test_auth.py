def _reg(email="new@t.dev", phone="9876543210", **extra):
    return {"email": email, "full_name": "New Person", "phone": phone,
            "password": "Passw0rd!123", **extra}


def test_register_creates_customer(client):
    r = client.post("/api/v1/auth/register", json=_reg(role="ADMIN"))   # role must be ignored
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "CUSTOMER"


def test_duplicate_email_rejected(client, world):
    r = client.post("/api/v1/auth/register", json=_reg(email=world.cust1))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "EMAIL_EXISTS"


def test_short_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={**_reg(), "password": "short"})
    assert r.status_code == 422
    assert r.json()["success"] is False


def test_login_ok(client, world):
    r = client.post("/api/v1/auth/login", json={"email": world.cust1, "password": "Passw0rd!123"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_wrong_password_and_unknown_email_give_same_error(client, world):
    a = client.post("/api/v1/auth/login", json={"email": world.cust1, "password": "WrongPass123"})
    b = client.post("/api/v1/auth/login", json={"email": "nobody@t.dev", "password": "WrongPass123"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["code"] == b.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_protected_route_needs_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_garbage_token_rejected(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_me_returns_profile_and_update_works(client, world, login):
    h = login(world.cust1)
    assert client.get("/api/v1/auth/me", headers=h).json()["email"] == world.cust1
    r = client.patch("/api/v1/auth/me", json={"full_name": "Renamed User"}, headers=h)
    assert r.json()["full_name"] == "Renamed User"


def test_change_password(client, world, login):
    h = login(world.cust1)
    bad = client.post("/api/v1/auth/change-password",
                      json={"current_password": "wrong-one-123", "new_password": "NewPassw0rd!1"}, headers=h)
    assert bad.status_code == 400
    ok = client.post("/api/v1/auth/change-password",
                     json={"current_password": "Passw0rd!123", "new_password": "NewPassw0rd!1"}, headers=h)
    assert ok.status_code == 200
    again = client.post("/api/v1/auth/login", json={"email": world.cust1, "password": "NewPassw0rd!1"})
    assert again.status_code == 200