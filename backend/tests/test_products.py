def test_public_catalog_and_search(client, world):
    assert client.get("/api/v1/products").json()["total"] == 2
    assert client.get("/api/v1/products?q=mango").json()["total"] == 1
    assert client.get("/api/v1/products?category=mango").json()["total"] == 2
    assert client.get("/api/v1/products?category=nothing").json()["total"] == 0
    assert len(client.get("/api/v1/categories").json()) == 1


def test_product_detail_and_missing(client, world):
    assert client.get(f"/api/v1/products/{world.product_a}").status_code == 200
    r = client.get("/api/v1/products/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert client.get("/api/v1/products/not-a-uuid").status_code == 422


def test_owner_product_lifecycle(client, world, login):
    h = login(world.owner_a)
    r = client.post("/api/v1/owner/products", headers=h, json={
        "name": "Guava", "category_id": world.category, "price": 80,
        "discount_price": 65, "unit": "kg", "stock_quantity": 25})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.get("/api/v1/products?q=guava").json()["total"] == 1

    assert client.patch(f"/api/v1/owner/products/{pid}", json={"price": 90}, headers=h).json()["price"] == "90.00"

    client.post(f"/api/v1/owner/products/{pid}/deactivate", headers=h)
    assert client.get("/api/v1/products?q=guava").json()["total"] == 0
    client.post(f"/api/v1/owner/products/{pid}/activate", headers=h)
    assert client.get("/api/v1/products?q=guava").json()["total"] == 1


def test_discount_above_price_rejected(client, world, login):
    r = client.post("/api/v1/owner/products", headers=login(world.owner_a), json={
        "name": "Bad Deal", "category_id": world.category, "price": 50, "discount_price": 80})
    assert r.status_code == 422


def test_stock_adjustment_and_cannot_go_negative(client, world, login, stock):
    h = login(world.owner_a)
    pid = world.product_a
    client.post(f"/api/v1/owner/products/{pid}/stock", json={"change_quantity": 5}, headers=h)
    assert stock(pid) == 15
    r = client.post(f"/api/v1/owner/products/{pid}/stock", json={"change_quantity": -999}, headers=h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    assert stock(pid) == 15
    assert client.post(f"/api/v1/owner/products/{pid}/stock",
                       json={"change_quantity": 0}, headers=h).status_code == 422


def test_unapproved_store_products_hidden(client, world, login):
    store_id = world.store_b
    client.patch(f"/api/v1/admin/stores/{store_id}", json={"is_approved": False},
                 headers=login(world.admin))
    assert client.get("/api/v1/products").json()["total"] == 1
    assert client.get(f"/api/v1/products/{world.product_b}").status_code == 404


def test_image_upload_rejects_non_images(client, world, login):
    h = login(world.owner_a)
    r = client.post(f"/api/v1/owner/products/{world.product_a}/image", headers=h,
                    files={"file": ("evil.jpg", b"this is not an image", "image/jpeg")})
    assert r.status_code == 400
    r2 = client.post(f"/api/v1/owner/products/{world.product_a}/image", headers=h,
                     files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "INVALID_FILE_TYPE"