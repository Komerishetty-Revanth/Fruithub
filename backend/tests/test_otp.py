def _register(client, email="otp@t.dev", phone="9876543210"):
    return client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Otp Person", "phone": phone, "password": "Passw0rd!123"})


def _headers(r):
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_phone_is_required(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "x@t.dev", "full_name": "No Phone", "password": "Passw0rd!123"})
    assert r.status_code == 422


def test_invalid_phone_rejected(client):
    assert _register(client, phone="12345").status_code == 422
    assert _register(client, phone="5876543210").status_code == 422   # must start with 6 to 9


def test_register_normalizes_phone_and_sends_otp(client):
    r = _register(client, phone="98765 43210")
    assert r.status_code == 201
    assert r.json()["user"]["phone"] == "+919876543210"
    assert r.json()["user"]["phone_verified"] is False
    assert len(r.json()["otp"]["dev_otp"]) == 6


def test_duplicate_phone_rejected(client):
    _register(client)
    r = _register(client, email="other@t.dev", phone="+91 98765 43210")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PHONE_EXISTS"


def test_correct_otp_verifies_phone(client):
    r = _register(client)
    h, code = _headers(r), r.json()["otp"]["dev_otp"]
    v = client.post("/api/v1/auth/phone/verify", json={"code": code}, headers=h)
    assert v.status_code == 200 and v.json()["phone_verified"] is True
    assert client.get("/api/v1/auth/me", headers=h).json()["phone_verified"] is True


def test_wrong_otp_rejected(client):
    r = _register(client)
    bad = client.post("/api/v1/auth/phone/verify", json={"code": "000000"}, headers=_headers(r))
    if r.json()["otp"]["dev_otp"] != "000000":
        assert bad.status_code == 400
        assert bad.json()["error"]["code"] == "INVALID_OTP"


def test_otp_locks_after_five_wrong_tries(client):
    r = _register(client)
    h, real = _headers(r), r.json()["otp"]["dev_otp"]
    wrong = "111111" if real != "111111" else "222222"
    for _ in range(5):
        assert client.post("/api/v1/auth/phone/verify", json={"code": wrong}, headers=h).status_code == 400
    locked = client.post("/api/v1/auth/phone/verify", json={"code": real}, headers=h)
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "OTP_LOCKED"


def test_resend_too_soon(client):
    r = _register(client)
    again = client.post("/api/v1/auth/phone/send", headers=_headers(r))
    assert again.status_code == 429
    assert again.json()["error"]["code"] == "OTP_TOO_SOON"


def test_otp_must_be_six_digits(client):
    r = _register(client)
    assert client.post("/api/v1/auth/phone/verify", json={"code": "12ab"}, headers=_headers(r)).status_code == 422


def test_unverified_customer_cannot_checkout_until_verified(client, address):
    r = _register(client)
    h, code = _headers(r), r.json()["otp"]["dev_otp"]
    aid = address(h)
    blocked = client.post("/api/v1/orders/checkout", json={"address_id": aid}, headers=h)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PHONE_NOT_VERIFIED"
    client.post("/api/v1/auth/phone/verify", json={"code": code}, headers=h)
    after = client.post("/api/v1/orders/checkout", json={"address_id": aid}, headers=h)
    assert after.json()["error"]["code"] == "CART_EMPTY"   # got past the phone check