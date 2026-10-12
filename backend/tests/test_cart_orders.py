from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models import Order, Payment
from app.services import order_service


def test_cart_totals(client, world, login):
    h = login(world.cust1)
    r = client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 2}, headers=h)
    cart = r.json()
    assert float(cart["subtotal"]) == 200
    assert float(cart["delivery_fee"]) == 20
    assert float(cart["total"]) == 220


def test_free_delivery_above_500(client, world, login):
    h = login(world.cust1)
    r = client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 6}, headers=h)
    assert float(r.json()["delivery_fee"]) == 0


def test_cart_add_change_remove_clear(client, world, login):
    h = login(world.cust1)
    client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 1}, headers=h)
    client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 2}, headers=h)
    assert float(client.get("/api/v1/cart", headers=h).json()["items"][0]["quantity"]) == 3
    r = client.patch(f"/api/v1/cart/items/{world.product_a}", json={"quantity": 4}, headers=h)
    assert float(r.json()["items"][0]["quantity"]) == 4
    assert client.delete(f"/api/v1/cart/items/{world.product_a}", headers=h).json()["item_count"] == 0
    client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 1}, headers=h)
    assert client.delete("/api/v1/cart", headers=h).json()["item_count"] == 0


def test_cannot_add_more_than_stock(client, world, login):
    h = login(world.cust1)
    r = client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 11}, headers=h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSUFFICIENT_STOCK"


def test_cannot_mix_stores_in_one_cart(client, world, login):
    h = login(world.cust1)
    client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 1}, headers=h)
    r = client.post("/api/v1/cart/items", json={"product_id": world.product_b, "quantity": 1}, headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CART_STORE_MISMATCH"


def test_checkout_reserves_stock_and_empties_cart(client, world, login, checkout, stock):
    h = login(world.cust1)
    r = checkout(h, world.product_a, qty=2)
    assert r.status_code == 201, r.text
    order = r.json()["order"]
    assert order["status"] == "PENDING_PAYMENT"
    assert order["pay_before"] is not None
    assert float(order["total"]) == 220
    assert stock(world.product_a) == 8
    assert client.get("/api/v1/cart", headers=h).json()["item_count"] == 0


def test_checkout_outside_seller_radius_requires_acknowledgement(client, world, login, checkout, stock, address):
    h = login(world.cust1)
    client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 2}, headers=h)
    aid = address(h, lat=17.40, lng=78.55)  # about 5.56 km

    blocked = client.post("/api/v1/orders/checkout", json={"address_id": aid}, headers=h)
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "SELF_DELIVERY_ACK_REQUIRED"
    assert stock(world.product_a) == 10

    accepted = client.post("/api/v1/orders/checkout", json={
        "address_id": aid, "accept_self_delivery": True,
    }, headers=h)
    assert accepted.status_code == 201, accepted.text
    order = accepted.json()["order"]
    assert order["seller_delivery_available"] is False
    assert float(order["delivery_fee"]) == 0
    assert float(order["total"]) == 200
    assert stock(world.product_a) == 8


def test_external_delivery_order_owner_cannot_mark_out_for_delivery(client, world, login, address):
    customer = login(world.cust1)
    owner = login(world.owner_a)
    client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 1}, headers=customer)
    aid = address(customer, lat=17.40, lng=78.55)
    checkout_response = client.post("/api/v1/orders/checkout", json={
        "address_id": aid, "accept_self_delivery": True,
    }, headers=customer)
    order_id = checkout_response.json()["order"]["id"]
    client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=customer)

    for status in ["CONFIRMED", "PACKING", "READY_FOR_DELIVERY"]:
        result = client.post(f"/api/v1/owner/orders/{order_id}/status",
                             json={"status": status}, headers=owner)
        assert result.status_code == 200, result.text
    cannot_dispatch = client.post(f"/api/v1/owner/orders/{order_id}/status",
                                  json={"status": "OUT_FOR_DELIVERY"}, headers=owner)
    assert cannot_dispatch.status_code == 409

    received = client.post(f"/api/v1/orders/{order_id}/confirm-external-delivery", headers=customer)
    assert received.status_code == 200
    assert received.json()["status"] == "DELIVERED"


def test_checkout_needs_complete_address(client, world, login, address):
    h = login(world.cust1)
    client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 1}, headers=h)
    aid = address(h, complete=False)
    r = client.post("/api/v1/orders/checkout", json={"address_id": aid}, headers=h)
    assert r.json()["error"]["code"] == "ADDRESS_INCOMPLETE"


def test_checkout_empty_cart(client, world, login, address):
    h = login(world.cust1)
    aid = address(h)
    r = client.post("/api/v1/orders/checkout", json={"address_id": aid}, headers=h)
    assert r.json()["error"]["code"] == "CART_EMPTY"


def test_stock_cannot_be_oversold(client, world, login, checkout):
    first = checkout(login(world.cust1), world.product_a, qty=6)
    assert first.status_code == 201
    h2 = login(world.cust2)
    r = client.post("/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 6}, headers=h2)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSUFFICIENT_STOCK"


def test_payment_confirms_order_and_is_idempotent(client, world, login, checkout):
    h = login(world.cust1)
    order_id = checkout(h, world.product_a).json()["order"]["id"]
    r = client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "PLACED" and r.json()["payment_status"] == "PAID"
    again = client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=h)
    assert again.status_code in (200, 409)
    assert client.get(f"/api/v1/orders/{order_id}", headers=h).json()["status"] == "PLACED"


def test_forged_payment_signature_rejected(client, world, login, checkout):
    h = login(world.cust1)
    r = checkout(h, world.product_a)
    order_id = r.json()["order"]["id"]
    provider_order_id = r.json()["payment"]["provider_order_id"]
    bad = client.post("/api/v1/payments/confirm", headers=h, json={
        "provider_order_id": provider_order_id,
        "provider_payment_id": "fake_pay_1", "signature": "0" * 64})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_PAYMENT_SIGNATURE"
    assert client.get(f"/api/v1/orders/{order_id}", headers=h).json()["status"] == "PENDING_PAYMENT"


def test_customer_cancel_returns_stock(client, world, login, checkout, stock):
    h = login(world.cust1)
    order_id = checkout(h, world.product_a, qty=3).json()["order"]["id"]
    assert stock(world.product_a) == 7
    r = client.post(f"/api/v1/orders/{order_id}/cancel", headers=h)
    assert r.json()["status"] == "CANCELLED"
    assert stock(world.product_a) == 10
    assert client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=h).status_code >= 400


def test_unpaid_order_expires_and_stock_returns(client, world, login, checkout, stock):
    h = login(world.cust1)
    order_id = checkout(h, world.product_a, qty=4).json()["order"]["id"]
    assert stock(world.product_a) == 6
    db = SessionLocal()
    try:
        db.query(Order).update({Order.created_at: datetime.now(timezone.utc) - timedelta(hours=1)})
        db.commit()
        assert order_service.expire_unpaid_orders(db) == 1
    finally:
        db.close()
    assert client.get(f"/api/v1/orders/{order_id}", headers=h).json()["status"] == "CANCELLED"
    assert stock(world.product_a) == 10


def test_full_order_flow_with_tracking_and_review(client, world, login, checkout):
    hc, ho = login(world.cust1), login(world.owner_a)
    order_id = checkout(hc, world.product_a).json()["order"]["id"]
    client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=hc)

    # owner cannot skip steps
    skip = client.post(f"/api/v1/owner/orders/{order_id}/status", json={"status": "DELIVERED"}, headers=ho)
    assert skip.status_code == 409
    assert skip.json()["error"]["code"] == "INVALID_STATUS_CHANGE"

    # review is not allowed before delivery
    early = client.put(f"/api/v1/products/{world.product_a}/reviews",
                       json={"rating": 5}, headers=hc)
    assert early.status_code == 403

    for status in ["CONFIRMED", "PACKING", "READY_FOR_DELIVERY", "OUT_FOR_DELIVERY", "DELIVERED"]:
        r = client.post(f"/api/v1/owner/orders/{order_id}/status", json={"status": status}, headers=ho)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == status

    seen = [e["status"] for e in client.get(f"/api/v1/orders/{order_id}", headers=hc).json()["history"]]
    assert seen == ["PENDING_PAYMENT", "PLACED", "CONFIRMED", "PACKING",
                    "READY_FOR_DELIVERY", "OUT_FOR_DELIVERY", "DELIVERED"]

    review = client.put(f"/api/v1/products/{world.product_a}/reviews",
                        json={"rating": 4, "comment": "Sweet"}, headers=hc)
    assert review.status_code == 200
    product = client.get(f"/api/v1/products/{world.product_a}").json()
    assert product["rating"] == 4.0 and product["rating_count"] == 1


def test_owner_reject_refunds_and_restocks(client, world, login, checkout, stock):
    hc, ho = login(world.cust1), login(world.owner_a)
    order_id = checkout(hc, world.product_a, qty=3).json()["order"]["id"]
    client.post(f"/api/v1/payments/mock/{order_id}/pay", headers=hc)
    assert stock(world.product_a) == 7
    r = client.post(f"/api/v1/owner/orders/{order_id}/status",
                    json={"status": "CANCELLED", "note": "Out of ripe stock"}, headers=ho)
    assert r.json()["status"] == "CANCELLED" and r.json()["payment_status"] == "REFUNDED"
    assert stock(world.product_a) == 10


def test_unpaid_orders_hidden_from_owner(client, world, login, checkout):
    checkout(login(world.cust1), world.product_a)
    assert client.get("/api/v1/owner/orders", headers=login(world.owner_a)).json()["total"] == 0


def test_manual_upi_payment_requires_owner_verification(client, world, login, address, stock):
    customer = login(world.cust1)
    owner = login(world.owner_a)
    foreign_owner = login(world.owner_b)
    configured = client.patch(
        "/api/v1/owner/store", headers=owner, json={"upi_vpa": "fruithub.owner@upi"},
    )
    assert configured.status_code == 200, configured.text

    added = client.post(
        "/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 2},
        headers=customer,
    )
    assert added.status_code == 200, added.text
    address_id = address(customer)
    checkout_response = client.post(
        "/api/v1/orders/checkout",
        headers=customer,
        json={"address_id": address_id, "payment_method": "UPI_MANUAL"},
    )
    assert checkout_response.status_code == 201, checkout_response.text
    checkout_data = checkout_response.json()
    order_id = checkout_data["order"]["id"]
    assert checkout_data["payment"]["provider"] == "manual_upi"
    assert checkout_data["payment"]["upi_vpa"] == "fruithub.owner@upi"
    assert checkout_data["payment"]["payment_uri"].startswith("upi://pay?")
    assert checkout_data["payment"]["payment_uri"].find("tr=") >= 0
    assert checkout_data["order"]["payment_status"] == "PENDING"
    payment_info = client.get(f"/api/v1/orders/{order_id}/upi-payment", headers=customer)
    assert payment_info.status_code == 200, payment_info.text
    assert payment_info.json()["reference_submitted"] is False
    assert payment_info.json()["payment_uri"] == checkout_data["payment"]["payment_uri"]
    assert client.get(
        f"/api/v1/orders/{order_id}/upi-payment", headers=foreign_owner,
    ).status_code == 403

    reference = client.post(
        f"/api/v1/orders/{order_id}/upi-reference",
        headers=customer, json={"transaction_reference": "123456789012"},
    )
    assert reference.status_code == 200, reference.text
    assert reference.json()["payment_status"] == "PENDING"
    assert reference.json()["status"] == "PENDING_PAYMENT"
    payment_info_after_reference = client.get(
        f"/api/v1/orders/{order_id}/upi-payment", headers=customer,
    )
    assert payment_info_after_reference.status_code == 200
    assert payment_info_after_reference.json()["reference_submitted"] is True
    assert client.post(f"/api/v1/orders/{order_id}/cancel", headers=customer).status_code == 409

    queue = client.get("/api/v1/owner/orders/manual-payments", headers=owner)
    assert queue.status_code == 200 and len(queue.json()) == 1
    assert queue.json()[0]["transaction_reference"] == "123456789012"
    assert client.post(
        f"/api/v1/owner/orders/{order_id}/manual-payment/confirm",
        headers=foreign_owner,
    ).status_code == 404
    confirmed = client.post(
        f"/api/v1/owner/orders/{order_id}/manual-payment/confirm",
        headers=owner,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "PLACED"
    assert confirmed.json()["payment_status"] == "PAID"
    assert stock(world.product_a) == 8


def test_owner_rejects_unverified_upi_and_restores_stock(client, world, login, address, stock):
    customer, owner = login(world.cust1), login(world.owner_a)
    client.patch("/api/v1/owner/store", headers=owner, json={"upi_vpa": "fruithub.owner@upi"})
    client.post(
        "/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 3},
        headers=customer,
    )
    checkout_response = client.post(
        "/api/v1/orders/checkout",
        headers=customer,
        json={"address_id": address(customer), "payment_method": "UPI_MANUAL"},
    )
    assert checkout_response.status_code == 201, checkout_response.text
    order_id = checkout_response.json()["order"]["id"]
    assert client.post(
        f"/api/v1/orders/{order_id}/upi-reference",
        headers=customer, json={"transaction_reference": "123456789013"},
    ).status_code == 200

    rejected = client.post(
        f"/api/v1/owner/orders/{order_id}/manual-payment/reject",
        headers=owner, json={"note": "Reference not found in account"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "CANCELLED"
    assert rejected.json()["payment_status"] == "FAILED"
    assert stock(world.product_a) == 10


def test_upi_reference_holds_stock_for_review_then_expires(client, world, login, address, stock):
    customer, owner = login(world.cust1), login(world.owner_a)
    client.patch("/api/v1/owner/store", headers=owner, json={"upi_vpa": "fruithub.owner@upi"})
    client.post(
        "/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 2},
        headers=customer,
    )
    checkout_response = client.post(
        "/api/v1/orders/checkout",
        headers=customer,
        json={"address_id": address(customer), "payment_method": "UPI_MANUAL"},
    )
    assert checkout_response.status_code == 201, checkout_response.text
    order_id = checkout_response.json()["order"]["id"]
    client.post(
        f"/api/v1/orders/{order_id}/upi-reference",
        headers=customer, json={"transaction_reference": "123456789014"},
    )

    db = SessionLocal()
    try:
        db.query(Order).filter(Order.id == order_id).update({
            Order.created_at: datetime.now(timezone.utc) - timedelta(hours=1),
        })
        db.commit()
        assert order_service.expire_unpaid_orders(db) == 0
        db.query(Payment).filter(Payment.order_id == order_id).update({
            Payment.updated_at: datetime.now(timezone.utc) - timedelta(hours=25),
        })
        db.commit()
        assert order_service.expire_unpaid_orders(db) == 1
    finally:
        db.close()
    assert stock(world.product_a) == 10
    assert client.get(f"/api/v1/orders/{order_id}", headers=customer).json()["status"] == "CANCELLED"


def test_cancelling_paid_upi_order_does_not_claim_automatic_refund(client, world, login, address):
    customer, owner = login(world.cust1), login(world.owner_a)
    client.patch("/api/v1/owner/store", headers=owner, json={"upi_vpa": "fruithub.owner@upi"})
    client.post(
        "/api/v1/cart/items", json={"product_id": world.product_a, "quantity": 1},
        headers=customer,
    )
    checkout_response = client.post(
        "/api/v1/orders/checkout",
        headers=customer,
        json={"address_id": address(customer), "payment_method": "UPI_MANUAL"},
    )
    assert checkout_response.status_code == 201, checkout_response.text
    order_id = checkout_response.json()["order"]["id"]
    client.post(
        f"/api/v1/orders/{order_id}/upi-reference",
        headers=customer, json={"transaction_reference": "123456789015"},
    )
    assert client.post(
        f"/api/v1/owner/orders/{order_id}/manual-payment/confirm", headers=owner,
    ).status_code == 200

    cancelled = client.post(
        f"/api/v1/owner/orders/{order_id}/status",
        headers=owner, json={"status": "CANCELLED"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["payment_status"] == "PAID"
    assert any(
        "refunded by the store outside FruitHub" in (event["note"] or "")
        for event in cancelled.json()["history"]
    )