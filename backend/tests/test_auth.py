"""Tests for the shared-secret gate.

Two layers: the pure token/password functions in backend.auth (engine-free,
millisecond-fast), and the FastAPI wiring in backend.main via TestClient. The
endpoint tests exercise only the gate itself -- a missing/valid token, a wrong
password, the unconfigured fail-closed path -- so none of them needs Stockfish
or Gemini.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import auth as auth_mod
from backend import main

SECRET = "correct horse battery staple"


# --- token / password primitives -------------------------------------------

def test_issued_token_verifies():
    token = auth_mod.issue_token(SECRET, 3600)
    assert auth_mod.verify_token(SECRET, token) is True


def test_expired_token_is_rejected():
    token = auth_mod.issue_token(SECRET, ttl_seconds=10, now=1_000)
    assert auth_mod.verify_token(SECRET, token, now=1_005) is True
    assert auth_mod.verify_token(SECRET, token, now=1_011) is False


def test_token_signed_with_another_secret_is_rejected():
    token = auth_mod.issue_token("some other secret", 3600)
    assert auth_mod.verify_token(SECRET, token) is False


def test_tampered_signature_is_rejected():
    token = auth_mod.issue_token(SECRET, 3600)
    payload, _, sig = token.partition(".")
    forged = f"{payload}.{'0' * len(sig)}"
    assert auth_mod.verify_token(SECRET, forged) is False


def test_tampered_expiry_cannot_extend_life():
    """Re-signing needs the secret, so a bumped expiry fails the signature."""
    token = auth_mod.issue_token(SECRET, ttl_seconds=10, now=1_000)
    _, _, sig = token.partition(".")
    far_future = auth_mod._b64("9999999999")
    assert auth_mod.verify_token(SECRET, f"{far_future}.{sig}", now=2_000) is False


@pytest.mark.parametrize("token", ["", "no-dot", "not base64!.deadbeef", "."])
def test_malformed_tokens_are_rejected(token):
    assert auth_mod.verify_token(SECRET, token) is False


def test_empty_secret_never_verifies():
    token = auth_mod.issue_token(SECRET, 3600)
    assert auth_mod.verify_token("", token) is False


def test_verify_password():
    assert auth_mod.verify_password(SECRET, SECRET) is True
    assert auth_mod.verify_password(SECRET, "wrong") is False
    assert auth_mod.verify_password("", "") is False  # unset secret is not a blank password


# --- endpoint wiring --------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", SECRET)
    main._auth_failures.clear()  # isolate the brute-force throttle between tests
    return TestClient(main.app)


def test_auth_returns_a_working_token(client):
    res = client.post("/api/auth", json={"password": SECRET})
    assert res.status_code == 200
    token = res.json()["token"]
    assert auth_mod.verify_token(SECRET, token) is True


def test_auth_rejects_wrong_password(client):
    res = client.post("/api/auth", json={"password": "nope"})
    assert res.status_code == 401


def test_protected_endpoint_requires_a_token(client):
    # No Authorization header -> refused before any engine work.
    assert client.get("/api/position", params={"fen": "x"}).status_code == 401
    assert client.post("/api/move-review", json={}).status_code == 401


def test_valid_token_clears_the_gate(client):
    """require_auth passes with a real token; only the guard is under test here."""
    token = client.post("/api/auth", json={"password": SECRET}).json()["token"]
    # Called directly so we assert the gate alone, without invoking Stockfish.
    assert main.require_auth(f"Bearer {token}") is None
    with pytest.raises(HTTPException) as bad:
        main.require_auth("Bearer garbage")
    assert bad.value.status_code == 401


def test_brute_force_is_throttled(client):
    for _ in range(main._AUTH_MAX_FAILURES):
        assert client.post("/api/auth", json={"password": "x"}).status_code == 401
    # Further attempts are refused even if the password is now correct.
    assert client.post("/api/auth", json={"password": SECRET}).status_code == 429


def test_gate_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    c = TestClient(main.app)
    assert c.post("/api/auth", json={"password": "anything"}).status_code == 503
    assert c.post("/api/analyze", json={"pgn": "x"}).status_code == 503
