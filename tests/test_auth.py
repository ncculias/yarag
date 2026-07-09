def test_login_success(client, make_user):
    make_user()
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "pw12345"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["display_name"] == "愛麗絲"


def test_login_wrong_password(client, make_user):
    make_user()
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "帳號或密碼錯誤"


def test_login_disabled_user_same_message(client, make_user):
    make_user(username="bob", is_active=False)
    r = client.post("/api/v1/auth/login", json={"username": "bob", "password": "pw12345"})
    assert r.status_code == 401
    assert r.json()["detail"] == "帳號或密碼錯誤"


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_user(client, auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
