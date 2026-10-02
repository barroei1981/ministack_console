"""
Project resource endpoints.
"""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query, Request

from api.models import (
    ErrorResponse,
    PaginatedResourceResponse,
    PaginationMetadata,
    ProjectListResponse,
    ProjectSummary,
    ResourceSummary,
)
from control_plane.graph.query import query_nodes
from control_plane.observability import log_operational

router = APIRouter()


@router.get(
    "/tenants/{tenant_id}/projects",
    response_model=ProjectListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Tenant not found"},
    },
    summary="List tenant projects",
    description="List projects for a tenant with resource counts",
)
async def list_tenant_projects(
    tenant_id: str,
    request: Request,
) -> ProjectListResponse:
    """
    List projects for a specific tenant with resource counts.

    Projects are identified by control-plane tags (project tag value).

    Args:
        tenant_id: Tenant ID (12 digits)

    Returns:
        List of projects with resource counts
    """
    try:
        # Enforce tenant isolation
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Verify tenant exists
        tenants = query_nodes("Tenant", filters={"id": tenant_id})
        if not tenants:
            raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")

        # Query all resources for this tenant
        resources = query_nodes("Resource", filters={"tenant_id": tenant_id})

        # Group resources by project tag
        project_counts: defaultdict[str, int] = defaultdict(int)
        for resource in resources:
            project = resource.get("project")
            if project:
                project_counts[project] += 1

        # Build project summaries
        projects = [
            ProjectSummary(
                name=project_name,
                resource_count=count,
                tenant_id=tenant_id,
            )
            for project_name, count in sorted(project_counts.items())
        ]

        log_operational(
            "Listed tenant projects",
            tenant_id=tenant_id,
            project_count=len(projects),
        )

        return ProjectListResponse(
            projects=projects,
            tenant_id=tenant_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        log_operational(
            "Failed to list tenant projects",
            tenant_id=tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to list tenant projects: {e!s}"
        )


@router.get(
    "/projects/{project_name}/resources",
    response_model=PaginatedResourceResponse,
    responses={
        400: {"model": ErrorResponse, "description": "tenant_id required"},
    },
    summary="List project resources",
    description="List resources for a specific project",
)
async def list_project_resources(
    project_name: str,
    request: Request,
    tenant_id: str = Query(..., description="Tenant ID (required)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(100, ge=1, le=500, description="Items per page (max 500)"),
) -> PaginatedResourceResponse:
    """
    List resources for a specific project.

    Args:
        project_name: Project name (from control-plane tags)
        tenant_id: Tenant ID (required query param)
        page: Page number (1-indexed)
        limit: Items per page (max 500)

    Returns:
        Paginated resource list
    """
    try:
        # Query resources for this tenant AND project
        all_resources = query_nodes(
            "Resource",
            filters={"tenant_id": tenant_id, "project": project_name},
        )

        # Calculate pagination
        total = len(all_resources)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit

        # Slice for current page
        page_resources = all_resources[start_idx:end_idx]

        # Convert to ResourceSummary models
        resource_summaries = []
        for resource in page_resources:
            # Extract state summary
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
            "Listed project resources",
            project_name=project_name,
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

    except Exception as e:
        log_operational(
            "Failed to list project resources",
            project_name=project_name,
            tenant_id=tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to list project resources: {e!s}"
        )
