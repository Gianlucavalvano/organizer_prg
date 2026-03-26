import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

from backend.settings import get_access_token_minutes, get_api_secret_key


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(input_data: str, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), input_data.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_access_token(payload: dict) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=get_access_token_minutes())
    data = dict(payload)
    data["type"] = "access"
    data["exp"] = int(expires.timestamp())

    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(data, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"
    signature_b64 = _sign(signing_input, get_api_secret_key())
    return f"{signing_input}.{signature_b64}"


def decode_and_verify_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = _sign(signing_input, get_api_secret_key())
    if not hmac.compare_digest(signature_b64, expected_sig):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise ValueError("Token expired")
    return payload

