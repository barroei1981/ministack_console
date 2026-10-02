"""
Health check endpoint.
"""

from fastapi import APIRouter, status

from api.models import HealthResponse, HealthServiceStatus
from control_plane.graph.query import health_check as graph_health_check
from control_plane.ministack_client import MiniStackClient
from control_plane.observability import log_operational

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check FalkorDB and MiniStack connection status",
)
async def health_check() -> HealthResponse:
    """
    Check health of FalkorDB and MiniStack connections.

    Returns 200 if both services are healthy, 503 if either is down.
    """
    # Check FalkorDB
    falkordb_healthy = graph_health_check()
    falkordb_status = HealthServiceStatus(
        connected=falkordb_healthy,
        instance_id=None,
        error=None if falkordb_healthy else "Connection failed",
    )

    # Check MiniStack
    ministack_client = MiniStackClient()
    ministack_result = await ministack_client.health_check()

    ministack_status = HealthServiceStatus(
        connected=ministack_result["healthy"],
        instance_id=ministack_result.get("instance_id"),
        error=ministack_result.get("error"),
    )

    # Overall status
    overall_healthy = falkordb_healthy and ministack_result["healthy"]
    overall_status = "healthy" if overall_healthy else "unhealthy"

    log_operational(
        "Health check completed",
        status=overall_status,
        falkordb_connected=falkordb_healthy,
        ministack_connected=ministack_result["healthy"],
    )

    response = HealthResponse(
        status=overall_status,
        ministack=ministack_status,
        falkordb=falkordb_status,
    )

    # Return 503 if unhealthy
    if not overall_healthy:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content=response.model_dump(),
        )

    return response
