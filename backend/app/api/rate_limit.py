import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_local = threading.local()


def _buckets() -> dict:
    if not hasattr(_local, "buckets"):
        _local.buckets = defaultdict(lambda: deque(maxlen=600))
    return _local.buckets


EXEMPT_PATHS = ("/healthz", "/docs", "/openapi.json", "/redoc")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, per_minute: int):
        super().__init__(app)
        self.per_minute = per_minute

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in EXEMPT_PATHS):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        bucket = _buckets()[client]
        now = time.monotonic()
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= self.per_minute:
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        bucket.append(now)
        return await call_next(request)
