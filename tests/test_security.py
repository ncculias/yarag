from datetime import UTC, datetime, timedelta

import jwt as pyjwt

from yarag.config import settings
from yarag.security import create_token, decode_token, hash_password, verify_password


def test_password_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_token_roundtrip():
    assert decode_token(create_token(42)) == 42


def test_token_invalid_and_expired():
    assert decode_token("garbage") is None
    expired = pyjwt.encode(
        {"sub": "42", "exp": datetime.now(UTC) - timedelta(hours=1)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    assert decode_token(expired) is None
