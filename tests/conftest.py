import os

os.environ.setdefault("ENDPOINT_URL", "https://test.r2.example.com")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("DEFAULT_BUCKET", "test-bucket")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("CF_ACCOUNT_ID", "test-account")
os.environ.setdefault("CF_AI_SEARCH_INSTANCE", "test-instance")
os.environ.setdefault("CF_API_TOKEN", "test-cf-token")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from yarag.app import app
    from yarag.db import Base, engine, init_db

    Base.metadata.drop_all(engine)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_user():
    from yarag.db import SessionLocal
    from yarag.models import User
    from yarag.security import hash_password

    def _make(username="alice", password="pw12345", display_name="愛麗絲", is_active=True):
        with SessionLocal() as db:
            u = User(
                username=username,
                display_name=display_name,
                password_hash=hash_password(password),
                is_active=is_active,
            )
            db.add(u)
            db.commit()
            return u.id

    return _make


@pytest.fixture()
def auth_headers(client, make_user):
    make_user()
    token = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "pw12345"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
