"""
Unit tests for core security utilities.

Tests hash_password, verify_password, create_access_token, create_refresh_token,
and JWT decode behaviour — all run offline with no DB or network calls.
"""

import time
from datetime import datetime, timedelta

import pytest
from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


# ── Password Hashing ──────────────────────────────────────────────────────────

class TestPasswordHashing:
    """Unit tests for hash_password and verify_password."""

    def test_hash_produces_string(self):
        """hash_password must return a non-empty string."""
        result = hash_password("mysecretpassword")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_is_not_plaintext(self):
        """The returned hash must not equal the original password."""
        password = "mysecretpassword"
        assert hash_password(password) != password

    def test_hash_starts_with_bcrypt_prefix(self):
        """bcrypt hashes start with '$2b$' or '$2a$'."""
        hashed = hash_password("testpass")
        assert hashed.startswith("$2")

    def test_two_hashes_of_same_password_differ(self):
        """bcrypt generates a unique salt each time — hashes must differ."""
        pw = "samepassword"
        assert hash_password(pw) != hash_password(pw)

    def test_verify_correct_password_returns_true(self):
        """verify_password returns True when the password matches the hash."""
        password = "correct_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password_returns_false(self):
        """verify_password returns False for an incorrect password."""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_password_returns_false(self):
        """An empty string should not match a non-empty password hash."""
        hashed = hash_password("some_password")
        assert verify_password("", hashed) is False

    def test_hash_unicode_password(self):
        """Password with unicode characters should be hashed and verified correctly."""
        password = "pässwörد123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


# ── Access Token ──────────────────────────────────────────────────────────────

class TestCreateAccessToken:
    """Unit tests for create_access_token."""

    def test_returns_string(self):
        """create_access_token must return a JWT string."""
        token = create_access_token({"sub": "1", "role": "user"})
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature

    def test_payload_sub_preserved(self):
        """The 'sub' claim must survive encode→decode."""
        token = create_access_token({"sub": "42", "role": "user"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "42"

    def test_payload_role_preserved(self):
        """The 'role' claim must survive encode→decode."""
        token = create_access_token({"sub": "1", "role": "admin"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["role"] == "admin"

    def test_token_has_exp_claim(self):
        """Access token must include an 'exp' (expiry) claim."""
        token = create_access_token({"sub": "1"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_token_not_yet_expired(self):
        """A freshly created token must not be expired."""
        token = create_access_token({"sub": "1"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["exp"] > time.time()

    def test_expiry_within_expected_window(self):
        """Token expiry should be within ±60 seconds of the configured window."""
        token = create_access_token({"sub": "1"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        expected_exp = time.time() + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert abs(payload["exp"] - expected_exp) < 60

    def test_wrong_secret_raises_jwt_error(self):
        """Decoding with a wrong secret must raise JWTError."""
        token = create_access_token({"sub": "1"})
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-secret", algorithms=[settings.ALGORITHM])


# ── Refresh Token ─────────────────────────────────────────────────────────────

class TestCreateRefreshToken:
    """Unit tests for create_refresh_token."""

    def test_returns_string(self):
        """create_refresh_token must return a JWT string."""
        token = create_refresh_token({"sub": "1"})
        assert isinstance(token, str)

    def test_has_exp_claim(self):
        """Refresh token must include an 'exp' claim."""
        token = create_refresh_token({"sub": "1"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_refresh_token_longer_expiry_than_access(self):
        """Refresh token must expire later than access token."""
        access = create_access_token({"sub": "1"})
        refresh = create_refresh_token({"sub": "1"})

        access_exp = jwt.decode(access, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["exp"]
        refresh_exp = jwt.decode(refresh, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["exp"]
        assert refresh_exp > access_exp

    def test_sub_claim_preserved(self):
        """The 'sub' claim must be intact after encode→decode."""
        token = create_refresh_token({"sub": "99"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "99"

    def test_expiry_within_expected_window(self):
        """Refresh token expiry should be within ±120 seconds of expected."""
        token = create_refresh_token({"sub": "1"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        expected_exp = time.time() + settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        assert abs(payload["exp"] - expected_exp) < 120
