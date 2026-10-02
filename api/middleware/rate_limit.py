"""
Rate limiting middleware.

Simple in-memory rate limiter for Phase 1.
"""

import time
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Rate limit: 1000 requests per minute per tenant
RATE_LIMIT_REQUESTS = 1000
RATE_LIMIT_WINDOW_SECONDS = 60

# In-memory tracking: {tenant_id: [timestamp1, timestamp2, ...]}
_request_timestamps: dict[str, list[float]] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware with per-tenant tracking.

    Enforces 1000 requests per minute per tenant.
    Uses in-memory storage (suitable for single-instance deployments).

    For production multi-instance deployments, replace with Redis-based limiter.
    """

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """
        Check rate limit for tenant, enforce 1000 req/min.

        Args:
            request: Incoming request (expects request.state.tenant_id)
            call_next: Next middleware/handler

        Returns:
            Response from handler or 429 error if rate limit exceeded

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        # Skip rate limiting for health check
        if request.url.path == "/api/health":
            return await call_next(request)

        # Get tenant_id from request state (set by tenant_context middleware)
        tenant_id = getattr(request.state, "tenant_id", None)

        if not tenant_id:
            # If tenant_id not set, let it pass (tenant_context middleware will handle)
            return await call_next(request)

        # Current timestamp
        now = time.time()

        # Initialize tenant tracking if not exists
        if tenant_id not in _request_timestamps:
            _request_timestamps[tenant_id] = []

        # Get timestamps within current window
        window_start = now - RATE_LIMIT_WINDOW_SECONDS
        timestamps = _request_timestamps[tenant_id]

        # Remove timestamps outside window
        timestamps[:] = [ts for ts in timestamps if ts > window_start]

        # Check if limit exceeded
        if len(timestamps) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW_SECONDS}s",
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
            )

        # Add current request timestamp
        timestamps.append(now)

        # Continue to handler
        response = await call_next(request)

        # Add rate limit headers
        remaining = RATE_LIMIT_REQUESTS - len(timestamps)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(window_start + RATE_LIMIT_WINDOW_SECONDS))

        return response
