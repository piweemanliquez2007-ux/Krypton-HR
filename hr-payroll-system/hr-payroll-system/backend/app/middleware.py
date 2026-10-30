"""Rate limiting middleware - prevents brute force and DoS attacks."""
import time
from collections import defaultdict
from fastapi import Request, Response
from fastapi.responses import JSONResponse

# In-memory store: {ip_address: [(timestamp, count), ...]}
_rate_limit_store: dict[str, list[tuple[float, int]]] = defaultdict(list)

# The kiosk scan endpoints get their own bucket, keyed by device id as well as
# by IP. Every employee at the entrance shares the tablet's IP, so a single IP
# budget would let one busy office block the whole kiosk.
_scan_limit_store: dict[str, list[tuple[float, int]]] = defaultdict(list)

# Limits per minute
AUTH_MAX = 10
SCAN_MAX = 60
NORMAL_MAX = 100

# Clean up old entries every 5 minutes
_last_cleanup = time.time()


def _cleanup():
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < 300:
        return
    _last_cleanup = now
    cutoff = now - 3600  # 1 hour window
    for store in (_rate_limit_store, _scan_limit_store):
        for key in list(store.keys()):
            store[key] = [(ts, c) for ts, c in store[key] if ts > cutoff]
            if not store[key]:
                del store[key]


def _is_scan_path(path: str) -> bool:
    """The kiosk handshake: POST /api/attendance/scan and /api/attendance/scan/confirm."""
    return path.startswith("/api/attendance/scan")


async def rate_limit_middleware(request: Request, call_next):
    """Rate limits by IP: 100 requests/min normally, 10/min for auth, 60/min per kiosk."""
    _cleanup()

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60  # 1 minute window

    if _is_scan_path(request.url.path):
        device_id = request.headers.get("x-device-id", "-")
        store = _scan_limit_store
        key = f"{client_ip}|{device_id}"
        max_requests = SCAN_MAX
    elif request.url.path.startswith("/auth"):
        # The login endpoint gets its own bucket: brute forcing a password
        # must be limited by the number of login attempts, not by the number
        # of ordinary API calls that happen to come from the same address.
        store = _rate_limit_store
        key = f"auth|{client_ip}"
        max_requests = AUTH_MAX
    else:
        store = _rate_limit_store
        key = f"api|{client_ip}"
        max_requests = NORMAL_MAX

    # Get request history for this key
    history = store[key]
    # Remove entries older than the window
    history = [(ts, c) for ts, c in history if ts > now - window]
    store[key] = history

    total = sum(c for _, c in history)

    if total >= max_requests:
        retry_after = int(window - (now - history[0][0])) if history else window
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": str(retry_after)},
        )

    # Record this request
    store[key].append((now, 1))

    response = await call_next(request)

    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(max_requests)
    response.headers["X-RateLimit-Remaining"] = str(max_requests - total - 1)
    response.headers["X-RateLimit-Reset"] = str(int(now + window))

    return response


async def security_headers_middleware(request: Request, call_next):
    """Adds security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response