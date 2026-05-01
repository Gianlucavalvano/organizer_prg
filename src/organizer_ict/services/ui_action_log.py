import functools
import inspect
import json
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any


# Global, reusable UI action logger for Flet handlers.
# Output: one JSON line on stdout for each event.


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, max_len: int = 300) -> str:
    try:
        s = str(value)
    except Exception:
        s = "<unprintable>"
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _extract_context(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    page = kwargs.get("page")
    current_user = kwargs.get("current_user") or kwargs.get("user")

    if args:
        first = args[0]

        # Typical case: method handler (self, event)
        if page is None and hasattr(first, "page"):
            page = getattr(first, "page", None)

        # Typical case: controller has current_user dict
        if current_user is None and hasattr(first, "current_user"):
            current_user = getattr(first, "current_user", None)

        # Utility handler may receive current_user dict directly.
        if current_user is None and isinstance(first, dict):
            if "username" in first or "id_utente" in first:
                current_user = first

    user_name = None
    user_id = None
    user_role = None
    if isinstance(current_user, dict):
        user_name = current_user.get("username")
        user_id = current_user.get("id_utente")
        user_role = current_user.get("ruolo")

    route = None
    if page is not None:
        route = getattr(page, "route", None)

    return {
        "user": user_name,
        "user_id": user_id,
        "role": user_role,
        "route": route,
    }


def log_ui_event(
    action: str,
    phase: str,
    *,
    request_id: str | None = None,
    elapsed_ms: int | None = None,
    error: Any = None,
    extra: dict[str, Any] | None = None,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
):
    payload: dict[str, Any] = {
        "ts": _now_iso(),
        "type": "ui_action",
        "action": action,
        "phase": phase,
        "request_id": request_id or str(uuid.uuid4()),
    }

    ctx = _extract_context(args, kwargs or {})
    payload.update(ctx)

    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms

    if error is not None:
        payload["error"] = _safe_str(error)

    if extra:
        payload["extra"] = extra

    print(json.dumps(payload, ensure_ascii=True), flush=True)


def traccia_click(nome: str | None = None):
    """
    Decorator for click/event handlers (sync + async), reusable across modules.
    Logs START/OK/ERR as JSON on stdout.
    """

    def decorator(func):
        action = nome or func.__qualname__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                request_id = str(uuid.uuid4())
                start = time.perf_counter()
                log_ui_event(action, "START", request_id=request_id, args=args, kwargs=kwargs)
                try:
                    out = await func(*args, **kwargs)
                    elapsed = int((time.perf_counter() - start) * 1000)
                    log_ui_event(action, "OK", request_id=request_id, elapsed_ms=elapsed, args=args, kwargs=kwargs)
                    return out
                except Exception as ex:
                    elapsed = int((time.perf_counter() - start) * 1000)
                    log_ui_event(action, "ERR", request_id=request_id, elapsed_ms=elapsed, error=ex, args=args, kwargs=kwargs)
                    traceback.print_exc()
                    raise

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())
            start = time.perf_counter()
            log_ui_event(action, "START", request_id=request_id, args=args, kwargs=kwargs)
            try:
                out = func(*args, **kwargs)
                elapsed = int((time.perf_counter() - start) * 1000)
                log_ui_event(action, "OK", request_id=request_id, elapsed_ms=elapsed, args=args, kwargs=kwargs)
                return out
            except Exception as ex:
                elapsed = int((time.perf_counter() - start) * 1000)
                log_ui_event(action, "ERR", request_id=request_id, elapsed_ms=elapsed, error=ex, args=args, kwargs=kwargs)
                traceback.print_exc()
                raise

        return sync_wrapper

    return decorator
