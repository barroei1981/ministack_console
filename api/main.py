"""
FastAPI application setup.

Main entry point for the MiniStack Console REST API.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.tenant_context import TenantContextMiddleware
from api.routes import graph, graph_viz, health, projects, resources, search, sse, tenants
from control_plane.observability import log_operational

# Configuration
API_PORT = int(os.getenv("API_PORT", "3001"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown events.
    """
    # Startup
    log_operational(
        "API server starting",
        port=API_PORT,
    )

    yield

    # Shutdown
    log_operational("API server shutting down")


# Create FastAPI app
app = FastAPI(
    title="MiniStack Console API",
    version="1.0.0",
    description="REST API for MiniStack control-plane data access",
    lifespan=lifespan,
)


# CORS middleware (outermost - must see all responses)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tenant context middleware (extracts and validates tenant_id)
app.add_middleware(TenantContextMiddleware)

# Rate limiting middleware (uses tenant_id from context)
app.add_middleware(RateLimitMiddleware)


# Exception handlers
from fastapi.exceptions import HTTPException as FastAPIHTTPException


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(
    request: Request, exc: FastAPIHTTPException
) -> JSONResponse:
    """
    Handle FastAPI HTTPException (raised by middleware and routes).
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail if isinstance(exc.detail, str) else "Error", "detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unhandled errors.
    """
    log_operational(
        "Unhandled exception",
        method=request.method,
        path=str(request.url.path),
        error=str(exc),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"},
    )


# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(tenants.router, prefix="/api", tags=["tenants"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(graph_viz.router, prefix="/api", tags=["graph-viz"])
app.include_router(sse.router, prefix="/api", tags=["sse"])
app.include_router(resources.router, prefix="/api", tags=["resources"])
app.include_router(search.router, prefix="/api", tags=["search"])


# Root endpoint
@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": "MiniStack Console API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=API_PORT,
        reload=True,
        log_level="info",
    )
