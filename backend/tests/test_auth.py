def login(client, phone="9000000001", password="Password123!"):
    return client.post("/api/v1/auth/login", json={"phone": phone, "password": password})


def test_login_current_user_and_logout(client):
    assert login(client).status_code == 200
    assert client.get("/api/v1/auth/me").json()["role"] == "owner"
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_bad_password_is_rejected(client):
    assert login(client, password="WrongPassword!").status_code == 401


def test_staff_cannot_access_owner_endpoints(client):
    assert login(client, phone="9000000002").status_code == 200
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.post("/api/v1/admin/products", json={"name": "X", "sku": "X", "unit_name": "packet", "selling_price": "1.00"}).status_code == 403


def test_manager_can_view_operations_but_not_admin(client):
    assert login(client, phone="9000000003").status_code == 200
    assert client.get("/api/v1/operations/status").status_code == 200
    assert client.get("/api/v1/admin/products").status_code == 403

