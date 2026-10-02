"""
Tenant resource endpoints.
"""


from fastapi import APIRouter, HTTPException, Query, Request

from api.models import (
    ErrorResponse,
    PaginatedResourceResponse,
    PaginationMetadata,
    ResourceSummary,
    TenantResponse,
)
from control_plane.graph.query import query_nodes
from control_plane.observability import log_operational

router = APIRouter()


@router.get(
    "/tenants",
    response_model=list[TenantResponse],
    summary="List tenants",
    description="List all tenants with resource counts",
)
async def list_tenants(request: Request) -> list[TenantResponse]:
    """
    List all tenants with resource counts.

    Returns:
        List of tenants with resource counts
    """
    try:
        # Query all Tenant nodes
        tenants = query_nodes("Tenant")

        # For each tenant, count resources
        tenant_responses = []
        for tenant in tenants:
            tenant_id = str(tenant.get("id", ""))
            name = str(tenant.get("name", tenant_id))
            created_at = str(tenant.get("created_at", ""))

            # Count resources for this tenant
            resources = query_nodes("Resource", filters={"tenant_id": tenant_id})
            resource_count = len(resources)

            tenant_responses.append(
                TenantResponse(
                    id=tenant_id,
                    name=name,
                    resource_count=resource_count,
                    created_at=created_at,
                )
            )

        log_operational(
            "Listed tenants",
            count=len(tenant_responses),
        )

        return tenant_responses

    except Exception as e:
        log_operational(
            "Failed to list tenants",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to list tenants: {e!s}")


@router.get(
    "/tenants/{tenant_id}/resources",
    response_model=PaginatedResourceResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Tenant not found"},
    },
    summary="List tenant resources",
    description="List resources for a specific tenant with pagination",
)
async def list_tenant_resources(
    tenant_id: str,
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
) -> PaginatedResourceResponse:
    """
    List resources for a specific tenant with pagination.

    Args:
        tenant_id: Tenant ID (12 digits)
        page: Page number (1-indexed)
        limit: Items per page (max 500)

    Returns:
        Paginated resource list
    """
    try:
        # Enforce tenant isolation
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Verify tenant exists
        tenants = query_nodes("Tenant", filters={"id": tenant_id})
        if not tenants:
            raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")

        # Query all resources for this tenant (no limit yet)
        all_resources = query_nodes("Resource", filters={"tenant_id": tenant_id})

        # Calculate pagination
        total = len(all_resources)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit

        # Slice for current page
        page_resources = all_resources[start_idx:end_idx]

        # Convert to ResourceSummary models
        resource_summaries = []
        for resource in page_resources:
            # Extract state summary (service-specific subset)
            state = resource.get("state", {})
            state_summary = {}

            # Common fields to include in summary
            if "status" in state:
                state_summary["status"] = state["status"]
            if "runtime" in state:
                state_summary["runtime"] = state["runtime"]
            if "location" in state:
                state_summary["location"] = state["location"]

            resource_summaries.append(
                ResourceSummary(
                    id=resource.get("id", ""),
                    type=resource.get("type", ""),
                    name=resource.get("name", ""),
                    tenant_id=resource.get("tenant_id", ""),
                    project=resource.get("project"),
                    tags=resource.get("tags", {}),
                    created_at=resource.get("created_at", ""),
                    state_summary=state_summary,
                )
            )

        # Build pagination metadata
        base_url = str(request.url.remove_query_params("page"))
        next_url = None
        prev_url = None

        if end_idx < total:
            next_url = f"{base_url}?page={page + 1}&limit={limit}"
        if page > 1:
            prev_url = f"{base_url}?page={page - 1}&limit={limit}"

        pagination = PaginationMetadata(
            page=page,
            limit=limit,
            total=total,
            next=next_url,
            prev=prev_url,
        )

        log_operational(
            "Listed tenant resources",
            tenant_id=tenant_id,
            page=page,
            limit=limit,
            total=total,
            returned=len(resource_summaries),
        )

        return PaginatedResourceResponse(
            resources=resource_summaries,
            pagination=pagination,
        )

    except HTTPException:
        raise
    except Exception as e:
        log_operational(
            "Failed to list tenant resources",
            tenant_id=tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to list tenant resources: {e!s}"
        )
