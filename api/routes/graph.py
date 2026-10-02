"""
Graph query endpoints for resource dependencies.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from api.models import DependencyListResponse, DependencyResponse, ErrorResponse
from control_plane.graph.query import query_relationships, query_reverse_relationships
from control_plane.observability import log_operational

router = APIRouter()


@router.get(
    "/graph/dependencies",
    response_model=DependencyListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "resource_id required"},
    },
    summary="Query resource dependencies",
    description="Get resources that the specified resource depends on",
)
async def query_dependencies(
    request: Request,
    resource_id: str = Query(..., description="Resource ID to query dependencies for"),
) -> DependencyListResponse:
    """
    Query resources that the specified resource depends on.

    Returns DEPENDS_ON relationships where the specified resource is the source.

    Args:
        resource_id: Resource ID (typically ARN)

    Returns:
        List of dependencies
    """
    try:
        # Query DEPENDS_ON relationships from this resource
        relationships = query_relationships(
            from_node_id=resource_id,
            from_label="Resource",
            rel_type="DEPENDS_ON",
        )

        # Convert to DependencyResponse models
        dependencies = [
            DependencyResponse(
                from_node_id=rel["from_node_id"],
                to_node_id=rel["to_node_id"],
                rel_type=rel["rel_type"],
                metadata=rel.get("properties", {}),
            )
            for rel in relationships
        ]

        log_operational(
            "Queried resource dependencies",
            resource_id=resource_id,
            dependency_count=len(dependencies),
        )

        return DependencyListResponse(
            dependencies=dependencies,
            resource_id=resource_id,
        )

    except Exception as e:
        log_operational(
            "Failed to query dependencies",
            resource_id=resource_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to query dependencies: {e!s}"
        )


@router.get(
    "/graph/dependents",
    response_model=DependencyListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "resource_id required"},
    },
    summary="Query resource dependents",
    description="Get resources that depend on the specified resource",
)
async def query_dependents(
    request: Request,
    resource_id: str = Query(..., description="Resource ID to query dependents for"),
) -> DependencyListResponse:
    """
    Query resources that depend on the specified resource.

    Returns DEPENDS_ON relationships where the specified resource is the target.

    Args:
        resource_id: Resource ID (typically ARN)

    Returns:
        List of dependent resources
    """
    try:
        # Query reverse DEPENDS_ON relationships (this resource is the target)
        relationships = query_reverse_relationships(
            to_node_id=resource_id,
            to_label="Resource",
            rel_type="DEPENDS_ON",
        )

        # Convert to DependencyResponse models
        dependencies = [
            DependencyResponse(
                from_node_id=rel["from_node_id"],
                to_node_id=rel["to_node_id"],
                rel_type=rel["rel_type"],
                metadata=rel.get("properties", {}),
            )
            for rel in relationships
        ]

        log_operational(
            "Queried resource dependents",
            resource_id=resource_id,
            dependent_count=len(dependencies),
        )

        return DependencyListResponse(
            dependencies=dependencies,
            resource_id=resource_id,
        )

    except Exception as e:
        log_operational(
            "Failed to query dependents",
            resource_id=resource_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to query dependents: {e!s}"
        )
