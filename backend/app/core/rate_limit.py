from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from fastapi import HTTPException, Request
from app.core.config import get_settings

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def enforce_login_rate_limit(request: Request):
    settings = get_settings(); now = monotonic()
    key = request.client.host if request.client else "unknown"
    with _lock:
        bucket = _attempts[key]
        while bucket and bucket[0] <= now - settings.login_rate_limit_window_seconds: bucket.popleft()
        if len(bucket) >= settings.login_rate_limit_attempts: raise HTTPException(429, "Too many login attempts; try again later")


def record_login_failure(request: Request):
    key = request.client.host if request.client else "unknown"
    with _lock: _attempts[key].append(monotonic())


def reset_rate_limits_for_tests():
    with _lock: _attempts.clear()
