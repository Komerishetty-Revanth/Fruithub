from datetime import datetime, timedelta, timezone


def _offer(world_title, start_days, end_days, value=10, kind="PERCENTAGE"):
    now = datetime.now(timezone.utc)
    return {
        "title": world_title, "discount_type": kind, "discount_value": value,
        "starts_at": (now + timedelta(days=start_days)).isoformat(),
        "ends_at": (now + timedelta(days=end_days)).isoformat(),
        "product_ids": [],
    }


# ---------- offers ----------

def test_live_offer_shows_and_expired_offer_does_not(client, world, login):
    h = login(world.owner_a)
    assert client.post("/api/v1/owner/offers", json=_offer("Live deal", -1, 5), headers=h).status_code == 201
    assert client.post("/api/v1/owner/offers", json=_offer("Old deal", -10, -5), headers=h).status_code == 201
    assert client.post("/api/v1/owner/offers", json=_offer("Future deal", 5, 9), headers=h).status_code == 201
    titles = [o["title"] for o in client.get("/api/v1/offers").json()["offers"]]
    assert titles == ["Live deal"]


def test_deactivated_offer_disappears(client, world, login):
    h = login(world.owner_a)
    offer_id = client.post("/api/v1/owner/offers", json=_offer("Temp", -1, 5), headers=h).json()["id"]
    client.post(f"/api/v1/owner/offers/{offer_id}/deactivate", headers=h)
    assert client.get("/api/v1/offers").json()["offers"] == []


def test_offer_validation(client, world, login):
    h = login(world.owner_a)
    assert client.post("/api/v1/owner/offers", json=_offer("Backwards", 5, 1), headers=h).status_code == 422
    assert client.post("/api/v1/owner/offers", json=_offer("Too big", -1, 5, value=150), headers=h).status_code == 422


def test_percentage_offer_lowers_cart_price(client, world, login):
    client.post("/api/v1/owner/offers", json=_offer("10 off", -1, 5, value=10), headers=login(world.owner_a))
    r = client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 2},
                    headers=login(world.cust1))
    item = r.json()["items"][0]
    assert float(item["unit_price"]) == 90
    assert float(r.json()["subtotal"]) == 200
    assert float(r.json()["discount_total"]) == 20


def test_fixed_offer_respects_minimum_order(client, world, login):
    o = _offer("Rs 50 off 500+", -1, 5, value=50, kind="FIXED")
    o["min_order_amount"] = 500
    client.post("/api/v1/owner/offers", json=o, headers=login(world.owner_a))
    h = login(world.cust1)
    small = client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 2}, headers=h)
    assert float(small.json()["discount_total"]) == 0
    big = client.patch(f"/api/v1/cart/items/{world.product_a}", json={"quantity": 6}, headers=h)
    assert float(big.json()["discount_total"]) == 50


# ---------- admin ----------

def test_admin_creates_owner_and_store(client, world, login):
    ha = login(world.admin)
    r = client.post("/api/v1/admin/owners", headers=ha, json={
        "email": "newowner@t.dev", "full_name": "New Owner", "phone": "9876500002", "password": "Passw0rd!123"})
    assert r.status_code == 201 and r.json()["role"] == "OWNER"
    owner_id = r.json()["id"]

    s = client.post("/api/v1/admin/stores", headers=ha, json={
        "owner_id": owner_id, "name": "Fresh Store", "latitude": 12.97, "longitude": 77.59})
    assert s.status_code == 201, s.text
    assert s.json()["delivery_radius_km"] == 5.0

    again = client.post("/api/v1/admin/stores", headers=ha, json={
        "owner_id": owner_id, "name": "Second", "latitude": 12.97, "longitude": 77.59})
    assert again.status_code == 409

    ho = login("newowner@t.dev")
    assert client.get("/api/v1/owner/store", headers=ho).json()["name"] == "Fresh Store"


def test_cannot_make_a_customer_a_store_owner(client, world, login):
    cust_id = client.get("/api/v1/auth/me", headers=login(world.cust1)).json()["id"]
    r = client.post("/api/v1/admin/stores", headers=login(world.admin), json={
        "owner_id": cust_id, "name": "Nope", "latitude": 1, "longitude": 1})
    assert r.status_code == 422


def test_admin_changes_radius_and_external_delivery_requires_ack(client, world, login, checkout):
    client.patch(f"/api/v1/admin/stores/{world.store_a}", json={"delivery_radius_km": 2},
                 headers=login(world.admin))
    r = checkout(login(world.cust1), world.product_a)       # 4.45 km away
    assert r.json()["error"]["code"] == "SELF_DELIVERY_ACK_REQUIRED"


def test_disabled_user_cannot_log_in(client, world, login):
    ha = login(world.admin)
    cust_id = client.get("/api/v1/auth/me", headers=login(world.cust1)).json()["id"]
    r = client.patch(f"/api/v1/admin/users/{cust_id}", json={"is_active": False}, headers=ha)
    assert r.status_code == 200
    bad = client.post("/api/v1/auth/login", json={"email": world.cust1, "password": "Passw0rd!123"})
    assert bad.status_code == 403


def test_disabled_user_old_token_stops_working(client, world, login):
    hc = login(world.cust1)
    cust_id = client.get("/api/v1/auth/me", headers=hc).json()["id"]
    client.patch(f"/api/v1/admin/users/{cust_id}", json={"is_active": False}, headers=login(world.admin))
    assert client.get("/api/v1/auth/me", headers=hc).status_code == 401


def test_admin_cannot_change_self_or_other_admins(client, world, login):
    ha = login(world.admin)
    my_id = client.get("/api/v1/auth/me", headers=ha).json()["id"]
    r = client.patch(f"/api/v1/admin/users/{my_id}", json={"is_active": False}, headers=ha)
    assert r.status_code == 403


def test_admin_user_search_and_filter(client, world, login):
    ha = login(world.admin)
    assert client.get("/api/v1/admin/users?role=OWNER", headers=ha).json()["total"] == 2
    assert client.get("/api/v1/admin/users?q=cust1", headers=ha).json()["total"] == 1


def test_admin_resolve_order_needs_note_and_refunds(client, world, login, checkout, stock):
    hc, ha = login(world.cust1), login(world.admin)
    order_id = checkout(hc, world.product_a, qty=2).json()["order"]["id"]
    client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=hc)
    no_note = client.post(f"/api/v1/admin/orders/{order_id}/resolve", json={"status": "CANCELLED", "note": "x"}, headers=ha)
    assert no_note.status_code == 422
    ok = client.post(f"/api/v1/admin/orders/{order_id}/resolve",
                     json={"status": "CANCELLED", "note": "Customer complaint"}, headers=ha)
    assert ok.status_code == 200
    assert ok.json()["status"] == "CANCELLED" and ok.json()["payment_status"] == "REFUNDED"
    assert stock(world.product_a) == 10
    again = client.post(f"/api/v1/admin/orders/{order_id}/resolve",
                        json={"status": "CONFIRMED", "note": "Try again"}, headers=ha)
    assert again.status_code == 409


def test_admin_cancel_does_not_claim_manual_upi_was_refunded(client, world, login, address):
    customer, owner, admin = login(world.cust1), login(world.owner_a), login(world.admin)
    client.patch("/api/v1/owner/store", headers=owner, json={"upi_vpa": "fruithub.owner@upi"})
    client.post(
        "/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 1},
        headers=customer,
    )
    created = client.post(
        "/api/v1/orders/checkout",
        headers=customer,
        json={"address_id": address(customer), "payment_method": "UPI_MANUAL"},
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["order"]["id"]
    client.post(
        f"/api/v1/orders/{order_id}/upi-reference",
        headers=customer, json={"transaction_reference": "123456789016"},
    )
    assert client.post(
        f"/api/v1/owner/orders/{order_id}/manual-payment/confirm", headers=owner,
    ).status_code == 200

    cancelled = client.post(
        f"/api/v1/admin/orders/{order_id}/resolve",
        headers=admin, json={"status": "CANCELLED", "note": "Support resolution"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["payment_status"] == "PAID"
    assert any(
        "refunded by the store outside FruitHub" in (event["note"] or "")
        for event in cancelled.json()["history"]
    )


def test_admin_order_search(client, world, login, checkout):
    ha, hc = login(world.admin), login(world.cust1)
    r = checkout(hc, world.product_a)
    number = r.json()["order"]["order_number"]
    assert client.get(f"/api/v1/admin/orders?q={number}", headers=ha).json()["total"] == 1
    assert client.get("/api/v1/admin/orders?q=nomatch", headers=ha).json()["total"] == 0


def test_admin_categories(client, world, login):
    ha = login(world.admin)
    assert client.post("/api/v1/admin/categories", json={"name": "mango"}, headers=ha).status_code == 409
    r = client.post("/api/v1/admin/categories", json={"name": "Citrus Fruits"}, headers=ha)
    assert r.status_code == 201 and r.json()["slug"] == "citrus-fruits"
    assert client.delete(f"/api/v1/admin/categories/{world.category}", headers=ha).status_code == 409


def test_admin_analytics_shape(client, world, login):
    data = client.get("/api/v1/admin/analytics", headers=login(world.admin)).json()
    assert data["total_customers"] == 2 and data["total_owners"] == 2
    assert data["total_products"] == 2 and len(data["last_7_days"]) == 7


def test_owner_analytics_shape(client, world, login):
    data = client.get("/api/v1/owner/analytics", headers=login(world.owner_a)).json()
    assert data["products"]["active"] == 1 and len(data["last_7_days"]) == 7


def test_location_check_endpoint(client, world):
    inside = client.post("/api/v1/locations/check", json={"latitude": 17.39, "longitude": 78.55}).json()
    assert inside["available"] is True
    outside = client.post("/api/v1/locations/check", json={"latitude": 17.40, "longitude": 78.55}).json()
    assert outside["available"] is False
    assert client.post("/api/v1/locations/check", json={"latitude": 95, "longitude": 78}).status_code == 422