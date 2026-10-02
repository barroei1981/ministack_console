"""
Tenant isolation middleware.

Extracts and validates tenant_id from request context.
"""

import re
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Tenant ID format: 12 digits
TENANT_ID_PATTERN = re.compile(r"^\d{12}$")


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and validate tenant_id from request.

    Tenant ID can be provided via:
    1. Query parameter: ?tenant_id=123456789012
    2. Header: X-Tenant-ID: 123456789012

    Stores validated tenant_id in request.state.tenant_id.
    """

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """
        Extract tenant_id from query param or header, validate, and store in request.state.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from handler or 400 error if tenant_id invalid

        Raises:
            HTTPException: 400 if tenant_id missing or invalid format
        """
        # Skip tenant validation for health check
        if request.url.path == "/api/health":
            return await call_next(request)

        # Try query parameter first
        tenant_id = request.query_params.get("tenant_id")

        # Fall back to header
        if not tenant_id:
            tenant_id = request.headers.get("X-Tenant-ID")

        # Validate tenant_id exists
        if not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="tenant_id required (query param or X-Tenant-ID header)",
            )

        # Validate tenant_id format (12 digits)
        if not TENANT_ID_PATTERN.match(tenant_id):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tenant_id format: must be 12 digits (got: {tenant_id})",
            )

        # Store in request state for route handlers
        request.state.tenant_id = tenant_id

        # Continue to next middleware/handler
        response = await call_next(request)
        return response
