"""Shared-secret gate for the compute/Gemini endpoints.

The app runs on a free Gemini tier, so analysis must be restricted to whoever
holds a single shared password (``AUTH_SECRET``). The threat is quota theft, not
per-user identity, so this is deliberately a stateless HMAC gate rather than a
user/session system:

  password  --POST /api/auth-->  signed token (HMAC-SHA256 over an expiry)
  token     --Bearer header-->   verified on every protected request

Nothing is stored server-side, which suits a single-process box that may sleep
or restart (Render free tier): verification just recomputes the HMAC and checks
the expiry. All comparisons are constant-time to avoid leaking the secret (or a
valid signature) through response timing.

Pure functions only — no FastAPI, no engine — so they test in milliseconds.
"""

import base64
import hashlib
import hmac
import time


def verify_password(secret: str, password: str) -> bool:
    """Constant-time check of a submitted password against the shared secret.

    An empty secret never matches: an unset ``AUTH_SECRET`` must not become a
    blank password that anyone can guess.
    """
    if not secret:
        return False
    return hmac.compare_digest(password.encode("utf-8"), secret.encode("utf-8"))


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> str:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad).decode("utf-8")


def issue_token(secret: str, ttl_seconds: int, *, now: int | None = None) -> str:
    """Mint ``<b64url(expiry_epoch)>.<hex hmac>`` valid for ``ttl_seconds``."""
    expiry = (int(time.time()) if now is None else now) + ttl_seconds
    payload = str(expiry)
    return f"{_b64(payload)}.{_sign(secret, payload)}"


def verify_token(secret: str, token: str, *, now: int | None = None) -> bool:
    """True iff ``token`` carries a signature made with ``secret`` and hasn't expired.

    The signature is verified before the expiry is trusted, so a tampered
    payload can't extend a token's life.
    """
    if not secret or not token or "." not in token:
        return False
    payload_b64, _, sig = token.partition(".")
    try:
        payload = _unb64(payload_b64)
    except (ValueError, UnicodeDecodeError):
        return False
    if not hmac.compare_digest(sig, _sign(secret, payload)):
        return False
    try:
        expiry = int(payload)
    except ValueError:
        return False
    return expiry > (int(time.time()) if now is None else now)
