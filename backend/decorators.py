import functools
import hashlib
import hmac
import inspect
import logging
import secrets
from typing import Any, Callable

from fastapi import HTTPException, status

from backend.security import decode_and_verify_token

logger = logging.getLogger("organizer.api")


def _preserve_signature(wrapper: Callable, wrapped: Callable) -> Callable:
    wrapper.__signature__ = inspect.signature(wrapped)
    return wrapper


def with_api_logging(action: str | None = None):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = action or func.__name__
            logger.info("API start: %s", name)
            try:
                out = func(*args, **kwargs)
                logger.info("API ok: %s", name)
                return out
            except Exception:
                logger.exception("API failed: %s", name)
                raise

        return _preserve_signature(wrapper, func)

    return decorator


def require_auth_user(user_kw: str = "user"):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get(user_kw)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authenticated user",
                )
            return func(*args, **kwargs)

        return _preserve_signature(wrapper, func)

    return decorator


def require_permission(perm_code: str, user_kw: str = "user"):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get(user_kw)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authenticated user",
                )
            ruolo = (getattr(user, "ruolo", "") or "").upper()
            permessi = list(getattr(user, "permessi", []) or [])
            if ruolo != "ADMIN" and perm_code not in permessi:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permesso mancante: {perm_code}",
                )
            return func(*args, **kwargs)

        return _preserve_signature(wrapper, func)

    return decorator


def require_admin(user_kw: str = "user"):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get(user_kw)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authenticated user",
                )
            ruolo = (getattr(user, "ruolo", "") or "").upper()
            if ruolo != "ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo ADMIN",
                )
            return func(*args, **kwargs)

        return _preserve_signature(wrapper, func)

    return decorator


def decode_token(credentials_kw: str = "credentials", payload_kw: str = "token_payload"):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            credentials = kwargs.get(credentials_kw)
            if credentials is None or str(getattr(credentials, "scheme", "")).lower() != "bearer":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing bearer token",
                )
            try:
                payload = decode_and_verify_token(credentials.credentials)
                if payload.get("type") != "access":
                    raise ValueError("Invalid token type")
            except HTTPException:
                raise
            except Exception as ex:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: {ex}",
                ) from ex

            kwargs[payload_kw] = payload
            return func(*args, **kwargs)

        return _preserve_signature(wrapper, func)

    return decorator


def hash_password(password: str) -> str:
    raw = (password or "").encode("utf-8")
    iterations = 200000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw, salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password_hash(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, it_s, salt_hex, digest_hex = stored_hash.split("$", 3)
            iterations = int(it_s)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            current = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iterations)
            return hmac.compare_digest(current, expected)
        except Exception:
            return False
    return (password or "") == stored_hash


def with_hashed_password(
    payload_kw: str = "payload",
    password_attr: str = "password",
    out_kw: str = "password_hash",
    required: bool = True,
):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            payload = kwargs.get(payload_kw)
            password = getattr(payload, password_attr, None) if payload is not None else None
            if required and not password:
                raise HTTPException(status_code=400, detail="Password vuota")
            kwargs[out_kw] = hash_password(password or "") if password else None
            return func(*args, **kwargs)

        return _preserve_signature(wrapper, func)

    return decorator


def require_password_match(
    plain_kw: str = "plain_password",
    stored_kw: str = "stored_hash",
):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            plain = kwargs.get(plain_kw)
            stored = kwargs.get(stored_kw)
            if not verify_password_hash(str(plain or ""), str(stored or "")):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Credenziali non valide",
                )
            return func(*args, **kwargs)

        return _preserve_signature(wrapper, func)

    return decorator
