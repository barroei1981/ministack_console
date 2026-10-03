"""
Project resource endpoints.
"""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query, Request

from api.models import (
    BulkDeleteResponse,
    CreateProjectRequest,
    ErrorResponse,
    PaginatedResourceResponse,
    PaginationMetadata,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectSummary,
    ResourceSummary,
)
from control_plane.graph.query import create_node, delete_node, get_graph, query_nodes
from control_plane.observability import log_audit, log_operational, log_security

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


@router.post(
    "/projects",
    response_model=ProjectDetailResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        409: {"model": ErrorResponse, "description": "Project already exists"},
    },
    summary="Create project",
    description="Create a new project in FalkorDB",
)
async def create_project(
    project_data: CreateProjectRequest,
    request: Request,
) -> ProjectDetailResponse:
    """
    Create a new project node in FalkorDB.

    Args:
        project_data: Project creation data

    Returns:
        Created project details
    """
    try:
        # Validate tenant isolation
        if project_data.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Check if project already exists
        existing = query_nodes(
            "Project",
            filters={"name": project_data.name, "tenant_id": project_data.tenant_id},
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Project '{project_data.name}' already exists for tenant {project_data.tenant_id}",
            )

        # Create project node
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        node_id = f"project-{project_data.tenant_id}-{project_data.name}"

        create_node(
            "Project",
            node_id,
            {
                "id": node_id,
                "name": project_data.name,
                "description": project_data.description or "",
                "tenant_id": project_data.tenant_id,
                "created_at": now,
            },
        )

        log_audit(
            "Project created",
            project_name=project_data.name,
            tenant_id=project_data.tenant_id,
            description=project_data.description,
        )

        return ProjectDetailResponse(
            name=project_data.name,
            description=project_data.description,
            tenant_id=project_data.tenant_id,
            created_at=now,
            resource_count=0,
            resource_counts_by_service={},
        )

    except HTTPException:
        raise
    except Exception as e:
        log_operational(
            "Failed to create project",
            project_name=project_data.name,
            tenant_id=project_data.tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create project: {e!s}"
        )


@router.get(
    "/projects/{project_name}",
    response_model=ProjectDetailResponse,
    responses={
        400: {"model": ErrorResponse, "description": "tenant_id required"},
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
    summary="Get project details",
    description="Get project details with resource breakdown by service type",
)
async def get_project_detail(
    project_name: str,
    request: Request,
    tenant_id: str = Query(..., description="Tenant ID (required)"),
) -> ProjectDetailResponse:
    """
    Get project details with resource counts by service type.

    Args:
        project_name: Project name
        tenant_id: Tenant ID (required query param)

    Returns:
        Project details with resource breakdown
    """
    try:
        # Query project node
        projects = query_nodes(
            "Project",
            filters={"name": project_name, "tenant_id": tenant_id},
        )

        # If no explicit Project node exists, synthesize one from tagged resources
        if not projects:
            # Check if any resources have this project tag
            resources = query_nodes(
                "Resource",
                filters={"tenant_id": tenant_id, "project": project_name},
            )

            if not resources:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{project_name}' not found for tenant {tenant_id}",
                )

            # Synthesize project from resources
            project_data = {
                "name": project_name,
                "description": None,
                "tenant_id": tenant_id,
                "created_at": None,
            }
        else:
            project_data = projects[0]

        # Query all resources for this project
        resources = query_nodes(
            "Resource",
            filters={"tenant_id": tenant_id, "project": project_name},
        )

        # Group by service type
        service_counts: defaultdict[str, int] = defaultdict(int)
        for resource in resources:
            resource_type = resource.get("type", "unknown")
            service_counts[resource_type] += 1

        log_operational(
            "Retrieved project details",
            project_name=project_name,
            tenant_id=tenant_id,
            resource_count=len(resources),
        )

        return ProjectDetailResponse(
            name=project_data.get("name", project_name),
            description=project_data.get("description"),
            tenant_id=tenant_id,
            created_at=project_data.get("created_at"),
            resource_count=len(resources),
            resource_counts_by_service=dict(service_counts),
        )

    except HTTPException:
        raise
    except Exception as e:
        log_operational(
            "Failed to get project details",
            project_name=project_name,
            tenant_id=tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get project details: {e!s}"
        )


@router.delete(
    "/projects/{project_name}/resources",
    response_model=BulkDeleteResponse,
    responses={
        400: {"model": ErrorResponse, "description": "tenant_id required"},
    },
    summary="Delete all project resources",
    description="Bulk delete all resources in a project",
)
async def delete_project_resources(
    project_name: str,
    request: Request,
    tenant_id: str = Query(..., description="Tenant ID (required)"),
) -> BulkDeleteResponse:
    """
    Delete all resources in a project (bulk operation).

    WARNING: This is a destructive operation that cannot be undone.

    Args:
        project_name: Project name
        tenant_id: Tenant ID (required query param)

    Returns:
        Bulk delete result
    """
    try:
        log_security(
            "Bulk delete requested",
            project_name=project_name,
            tenant_id=tenant_id,
            user_id=request.state.tenant_id,  # Using tenant_id as user_id for now
        )

        # Query all resources for this project
        resources = query_nodes(
            "Resource",
            filters={"tenant_id": tenant_id, "project": project_name},
        )

        deleted_count = 0

        # Delete each resource from FalkorDB
        for resource in resources:
            resource_id = resource.get("id")
            if resource_id:
                try:
                    delete_node("Resource", resource_id)
                    deleted_count += 1
                except Exception as e:
                    log_operational(
                        "Failed to delete resource in bulk operation",
                        resource_id=resource_id,
                        project_name=project_name,
                        error=str(e),
                    )

        log_audit(
            "Bulk delete completed",
            project_name=project_name,
            tenant_id=tenant_id,
            deleted_count=deleted_count,
            total_resources=len(resources),
        )

        return BulkDeleteResponse(
            deleted_count=deleted_count,
            project_name=project_name,
            tenant_id=tenant_id,
        )

    except Exception as e:
        log_operational(
            "Failed to delete project resources",
            project_name=project_name,
            tenant_id=tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete project resources: {e!s}"
        )
