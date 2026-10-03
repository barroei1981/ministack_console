"""
Resource graph visualization endpoints.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from control_plane.graph.query import get_graph
from control_plane.observability import log_operational

router = APIRouter()


@router.get(
    "/graph/resources",
    summary="Get resource graph",
    description="Get resource nodes and edges for graph visualization",
)
async def get_resource_graph(
    request: Request,
    tenant_id: str | None = Query(None, description="Filter by tenant ID"),
    project: str | None = Query(None, description="Filter by project"),
    service_type: str | None = Query(None, description="Filter by service type (s3, lambda, dynamodb)"),
):
    """
    Get resource graph data for visualization.

    Returns nodes and edges representing resources and their dependencies.

    Args:
        request: FastAPI request
        tenant_id: Optional tenant filter
        project: Optional project filter
        service_type: Optional service type filter

    Returns:
        Graph data with nodes and edges

    Raises:
        HTTPException: 500 if graph query fails
    """
    try:
        graph = get_graph()

        # Build Cypher query for nodes
        where_clauses = []
        params = {}

        if tenant_id:
            where_clauses.append("n.tenant_id = $tenant_id")
            params["tenant_id"] = tenant_id

        if project:
            where_clauses.append("n.project = $project")
            params["project"] = project

        if service_type:
            type_mapping = {
                "s3": "s3:bucket",
                "lambda": "lambda:function",
                "dynamodb": "dynamodb:table",
            }
            if service_type in type_mapping:
                where_clauses.append("n.type = $resource_type")
                params["resource_type"] = type_mapping[service_type]

        where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Query for nodes (resources)
        nodes_query = f"""
            MATCH (n:Resource)
            {where_str}
            RETURN n.id AS id, n.name AS name, n.type AS type,
                   n.tenant_id AS tenant_id, n.project AS project,
                   n.created_at AS created_at
            LIMIT 1000
        """

        log_operational(
            "Fetching resource graph nodes",
            tenant_id=tenant_id,
            project=project,
            service_type=service_type,
        )

        nodes_result = graph.query(nodes_query, params=params)

        nodes = []
        node_ids = set()
        for record in nodes_result.result_set:
            node_id = record[0]
            node_ids.add(node_id)
            nodes.append({
                "id": node_id,
                "name": record[1],
                "type": record[2],
                "tenant_id": record[3],
                "project": record[4] if len(record) > 4 and record[4] else None,
                "created_at": record[5] if len(record) > 5 and record[5] else None,
            })

        # Query for edges (relationships between resources)
        # Note: FalkorDB stores relationships between nodes
        # We're looking for any relationship between Resource nodes
        edges_query = """
            MATCH (a:Resource)-[r]->(b:Resource)
            RETURN a.id AS source, b.id AS target, type(r) AS relationship_type
            LIMIT 5000
        """

        log_operational(
            "Fetching resource graph edges",
            node_count=len(nodes),
        )

        edges_result = graph.query(edges_query)

        edges = []
        for record in edges_result.result_set:
            source = record[0]
            target = record[1]
            rel_type = record[2] if len(record) > 2 else "RELATED_TO"

            # Only include edges where both nodes are in our filtered set
            if source in node_ids and target in node_ids:
                edges.append({
                    "id": f"{source}-{target}",
                    "source": source,
                    "target": target,
                    "type": rel_type,
                })

        log_operational(
            "Resource graph fetched",
            node_count=len(nodes),
            edge_count=len(edges),
        )

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "filters": {
                    "tenant_id": tenant_id,
                    "project": project,
                    "service_type": service_type,
                },
            },
        }

    except Exception as e:
        log_operational(
            "Resource graph fetch failed",
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch resource graph: {e!s}"
        )
