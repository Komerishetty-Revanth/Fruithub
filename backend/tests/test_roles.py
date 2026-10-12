def test_customer_blocked_from_owner_and_admin(client, world, login):
    h = login(world.cust1)
    assert client.get("/api/v1/owner/products", headers=h).status_code == 403
    assert client.get("/api/v1/owner/orders", headers=h).status_code == 403
    assert client.get("/api/v1/admin/users", headers=h).status_code == 403


def test_owner_blocked_from_admin_and_customer_areas(client, world, login):
    h = login(world.owner_a)
    assert client.get("/api/v1/admin/users", headers=h).status_code == 403
    assert client.get("/api/v1/cart", headers=h).status_code == 403
    assert client.get("/api/v1/orders", headers=h).status_code == 403


def test_admin_cannot_use_owner_routes(client, world, login):
    assert client.get("/api/v1/owner/products", headers=login(world.admin)).status_code == 403


def test_anonymous_blocked(client):
    for path in ("/api/v1/owner/products", "/api/v1/admin/users", "/api/v1/cart", "/api/v1/orders"):
        assert client.get(path).status_code == 401


def test_owner_lists_only_own_products(client, world, login):
    r = client.get("/api/v1/owner/products", headers=login(world.owner_a))
    ids = [p["id"] for p in r.json()["items"]]
    assert ids == [world.product_a]


def test_owner_a_cannot_touch_owner_b_product(client, world, login):
    h = login(world.owner_a)
    pid = world.product_b
    assert client.get(f"/api/v1/owner/products/{pid}", headers=h).status_code == 404
    assert client.patch(f"/api/v1/owner/products/{pid}", json={"price": 1}, headers=h).status_code == 404
    assert client.post(f"/api/v1/owner/products/{pid}/stock",
                       json={"change_quantity": 5}, headers=h).status_code == 404
    assert client.post(f"/api/v1/owner/products/{pid}/deactivate", headers=h).status_code == 404
    # and nothing changed
    hb = login(world.owner_b)
    p = client.get(f"/api/v1/owner/products/{pid}", headers=hb).json()
    assert float(p["price"]) == 200 and float(p["stock_quantity"]) == 10 and p["is_active"] is True


def test_owner_a_cannot_put_owner_b_product_in_offer(client, world, login):
    r = client.post("/api/v1/owner/offers", headers=login(world.owner_a), json={
        "title": "Sneaky", "discount_type": "PERCENTAGE", "discount_value": 50,
        "starts_at": "2020-01-01T00:00:00Z", "ends_at": "2099-01-01T00:00:00Z",
        "product_ids": [world.product_b],
    })
    assert r.status_code == 404


def test_customer_cannot_read_another_customers_data(client, world, login, address, checkout):
    h1, h2 = login(world.cust1), login(world.cust2)
    aid = address(h1)
    assert client.patch(f"/api/v1/addresses/{aid}", json={"label": "Hacked"}, headers=h2).status_code == 404
    assert client.delete(f"/api/v1/addresses/{aid}", headers=h2).status_code == 404
    order_id = checkout(h1, world.product_a).json()["order"]["id"]
    assert client.get(f"/api/v1/orders/{order_id}", headers=h2).status_code == 404
    assert client.post(f"/api/v1/orders/{order_id}/cancel", headers=h2).status_code == 404
    assert client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=h2).status_code == 404


def test_owner_a_cannot_see_or_change_owner_b_orders(client, world, login, checkout):
    h = login(world.cust1)
    r = checkout(h, world.product_b, qty=1, lat=17.60, lng=78.80)
    assert r.status_code == 201, r.text
    order_id = r.json()["order"]["id"]
    assert client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=h).status_code == 200

    ha, hb = login(world.owner_a), login(world.owner_b)
    assert client.get(f"/api/v1/owner/orders/{order_id}", headers=ha).status_code == 404
    assert client.post(f"/api/v1/owner/orders/{order_id}/status",
                       json={"status": "CONFIRMED"}, headers=ha).status_code == 404
    assert client.get("/api/v1/owner/orders", headers=ha).json()["total"] == 0
    assert client.get(f"/api/v1/owner/orders/{order_id}", headers=hb).status_code == 200