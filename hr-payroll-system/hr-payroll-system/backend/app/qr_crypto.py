"""
QR PAYLOAD CRYPTOGRAPHY
========================

A QR code is a *bearer token*: whoever holds a picture of it can present it.
This module is what makes a stolen picture harmless.

Payload format (the text encoded in the QR image):

    HRQR1.<base64url(json)>.<base64url(hmac)>

    json = {"e": employee_id, "c": credential_id, "s": seq,
            "i": issued_at, "x": expires_at, "m": mode}

    hmac = HMAC-SHA256(signing_key, base64url(json))

Why each piece matters
----------------------
* The HMAC proves the payload was minted by THIS server. An attacker cannot
  craft a payload for another employee, even if they read the whole database:
  without the signing key (kept in .env, never in Postgres) the tag will not
  verify. Comparison is constant time (hmac.compare_digest).
* "s" (seq) is a per-credential counter. The server stores the last sequence
  it accepted, so a replayed payload is rejected. This is what stops a photo
  of a *dynamic* QR from being used twice.
* "x" (expires_at) bounds the lifetime of a *dynamic* QR. A photo taken today
  is worthless tomorrow, so a leaked screenshot cannot be used tomorrow.
* A *static* badge QR has no expiry by nature (it is printed on a card), so it
  is protected by the second factor instead: the kiosk demands a PIN after
  the QR is accepted (see qr_service.py).

The payload is deliberately short. It carries identifiers and timestamps, never
the PIN, never a salary, never anything secret beyond what the HMAC covers.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from app.config import settings

PAYLOAD_PREFIX = "HRQR1"
CLAIM_EMPLOYEE = "e"
CLAIM_CREDENTIAL = "c"
CLAIM_SEQ = "s"
CLAIM_ISSUED = "i"
CLAIM_EXPIRES = "x"
CLAIM_MODE = "m"

MODE_STATIC = "static"    # printed badge: no expiry, PIN required
MODE_DYNAMIC = "dynamic"  # mobile QR: short expiry + single use


class QrPayloadError(Exception):
    """Raised when a scanned payload is malformed, forged or expired."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason       # short code stored in the audit log
        self.message = message     # message shown to the user


@dataclass(frozen=True)
class QrPayload:
    employee_id: int
    credential_id: str
    seq: int
    issued_at: int
    expires_at: int | None
    mode: str


def _signing_key() -> bytes:
    """The HMAC key. Falls back to the JWT secret so a fresh install works."""
    secret = settings.qr_signing_secret or settings.jwt_secret
    return secret.encode("utf-8")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def build_payload(employee_id: int, credential_id: str, seq: int, mode: str,
                  ttl_seconds: int | None = None) -> str:
    """
    Builds the signed text that goes into the QR image.

    ttl_seconds=None means "never expires" (static badge).
    """
    now = int(time.time())
    expires_at = now + ttl_seconds if ttl_seconds else None
    claims = {
        CLAIM_EMPLOYEE: employee_id,
        CLAIM_CREDENTIAL: credential_id,
        CLAIM_SEQ: seq,
        CLAIM_ISSUED: now,
        CLAIM_EXPIRES: expires_at,
        CLAIM_MODE: mode,
    }
    body = _b64encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    tag = _b64encode(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{PAYLOAD_PREFIX}.{body}.{tag}"


def parse_payload(scanned: str) -> QrPayload:
    """
    Validates a scanned payload and returns its claims.

    Raises QrPayloadError with reason in
    {"malformed", "bad_signature", "expired"} - the caller logs the reason
    and shows a generic message, so an attacker learns nothing.
    """
    if not scanned or not isinstance(scanned, str):
        raise QrPayloadError("malformed", "This QR code could not be read.")

    parts = scanned.strip().split(".")
    if len(parts) != 3 or parts[0] != PAYLOAD_PREFIX:
        raise QrPayloadError("malformed", "This QR code could not be read.")

    _, body, tag = parts
    try:
        expected = hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest()
        given = _b64decode(tag)
    except (ValueError, TypeError):
        raise QrPayloadError("malformed", "This QR code could not be read.") from None

    if not hmac.compare_digest(expected, given):
        raise QrPayloadError("bad_signature", "This QR code is not valid.")

    try:
        claims = json.loads(_b64decode(body))
    except (ValueError, TypeError):
        raise QrPayloadError("malformed", "This QR code could not be read.") from None

    try:
        employee_id = int(claims[CLAIM_EMPLOYEE])
        credential_id = str(claims[CLAIM_CREDENTIAL])
        seq = int(claims[CLAIM_SEQ])
        issued_at = int(claims[CLAIM_ISSUED])
        expires_at = claims.get(CLAIM_EXPIRES)
        mode = str(claims.get(CLAIM_MODE, MODE_STATIC))
    except (KeyError, TypeError, ValueError):
        raise QrPayloadError("malformed", "This QR code could not be read.") from None

    if expires_at is not None:
        # Small tolerance for clock drift between the kiosk and the server.
        if time.time() > int(expires_at) + settings.qr_clock_skew_seconds:
            raise QrPayloadError("expired", "This QR code has expired. Please refresh it.")

    return QrPayload(
        employee_id=employee_id,
        credential_id=credential_id,
        seq=seq,
        issued_at=issued_at,
        expires_at=int(expires_at) if expires_at is not None else None,
        mode=mode,
    )


def hash_kiosk_key(raw_key: str) -> str:
    """SHA-256 hex of a kiosk device key (high entropy random secret)."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_kiosk_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a presented kiosk key against the stored hash."""
    return hmac.compare_digest(hash_kiosk_key(raw_key), stored_hash)


def generate_kiosk_key() -> str:
    """A fresh 32-byte secret for a newly enrolled kiosk."""
    return secrets.token_hex(32)
