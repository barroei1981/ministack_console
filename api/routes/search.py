"""
Resource search endpoints.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from control_plane.graph.query import get_graph
from control_plane.observability import log_operational

router = APIRouter()


@router.get(
    "/search/resources",
    summary="Search resources",
    description="Search across all resources by name, ID, or tags",
)
async def search_resources(
    request: Request,
    q: str = Query(..., description="Search query", min_length=1),
    tenant_id: str | None = Query(None, description="Filter by tenant ID"),
    service_type: str | None = Query(None, description="Filter by service type (s3, lambda, dynamodb)"),
    project: str | None = Query(None, description="Filter by project"),
    limit: int = Query(100, description="Max results", ge=1, le=1000),
):
    """
    Search resources across all services.

    Args:
        request: FastAPI request
        q: Search query
        tenant_id: Optional tenant filter
        service_type: Optional service type filter
        project: Optional project filter
        limit: Max results to return

    Returns:
        List of matching resources

    Raises:
        HTTPException: 500 if search fails
    """
    try:
        graph = get_graph()

        # Build Cypher query for case-insensitive search
        where_clauses = []
        params = {"search_query": q.lower()}

        # Search in name and id fields
        where_clauses.append(
            "(toLower(n.name) CONTAINS $search_query OR toLower(n.id) CONTAINS $search_query)"
        )

        # Add tenant filter if provided
        if tenant_id:
            where_clauses.append("n.tenant_id = $tenant_id")
            params["tenant_id"] = tenant_id

        # Add service type filter if provided
        if service_type:
            type_mapping = {
                "s3": "s3:bucket",
                "lambda": "lambda:function",
                "dynamodb": "dynamodb:table",
            }
            if service_type in type_mapping:
                where_clauses.append("n.type = $resource_type")
                params["resource_type"] = type_mapping[service_type]

        # Add project filter if provided
        if project:
            where_clauses.append("n.project = $project")
            params["project"] = project

        where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        query = f"""
            MATCH (n:Resource)
            {where_str}
            RETURN n
            LIMIT {limit}
        """

        log_operational(
            "Searching resources",
            query=q,
            tenant_id=tenant_id,
            service_type=service_type,
            project=project,
        )

        result = graph.query(query, params=params)

        resources = []
        for record in result.result_set:
            node_data = record[0]

            if hasattr(node_data, 'properties'):
                node_props = dict(node_data.properties)
            else:
                node_props = node_data if isinstance(node_data, dict) else {}

            resources.append(node_props)

        log_operational(
            "Resource search completed",
            query=q,
            results_count=len(resources),
        )

        return {
            "results": resources,
            "count": len(resources),
            "query": q,
        }

    except Exception as e:
        log_operational(
            "Resource search failed",
            query=q,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Search failed: {e!s}"
        )
