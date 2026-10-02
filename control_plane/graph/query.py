"""
FalkorDB Connection Management and CRUD Operations.

Provides connection pooling, retry logic, and base graph operations.
"""

import os
import time
import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from falkordb import FalkorDB
except ImportError:
    # Fallback message if falkordb is not installed
    FalkorDB = None

logger = logging.getLogger(__name__)

# Configuration (read from environment variables)
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_GRAPH_NAME = os.getenv("FALKORDB_GRAPH_NAME", "ministack_console")
FALKORDB_MAX_RETRIES = int(os.getenv("FALKORDB_MAX_RETRIES", "3"))
FALKORDB_RETRY_DELAY = float(os.getenv("FALKORDB_RETRY_DELAY", "1.0"))

# Global connection pool
_connection_pool: Optional[FalkorDB] = None
_graph_instance = None


def _get_connection():
    """
    Get or create FalkorDB connection with retry logic.

    Returns:
        FalkorDB connection instance

    Raises:
        ConnectionError: If unable to connect after max retries
    """
    global _connection_pool

    if FalkorDB is None:
        raise ImportError(
            "falkordb package not installed. Install with: pip install falkordb"
        )

    if _connection_pool is not None:
        return _connection_pool

    retries = 0
    last_error = None

    while retries < FALKORDB_MAX_RETRIES:
        try:
            logger.info(
                f"Connecting to FalkorDB at {FALKORDB_HOST}:{FALKORDB_PORT} "
                f"(attempt {retries + 1}/{FALKORDB_MAX_RETRIES})"
            )

            _connection_pool = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)

            # Test connection by selecting a test graph and running a simple query
            test_graph = _connection_pool.select_graph(f"_connection_test_{uuid.uuid4().hex[:8]}")
            test_graph.query("RETURN 1")

            logger.info("FalkorDB connection established")
            return _connection_pool

        except Exception as e:
            last_error = e
            retries += 1
            if retries < FALKORDB_MAX_RETRIES:
                delay = min(FALKORDB_RETRY_DELAY * (2 ** (retries - 1)), 60.0)  # Exponential backoff capped at 60s
                logger.warning(
                    f"FalkorDB connection failed: {e}. Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"FalkorDB connection failed after {retries} attempts")

    raise ConnectionError(
        f"Unable to connect to FalkorDB at {FALKORDB_HOST}:{FALKORDB_PORT} "
        f"after {FALKORDB_MAX_RETRIES} attempts. Last error: {last_error}"
    )


def get_graph():
    """
    Get FalkorDB graph instance.

    Returns:
        FalkorDB graph instance

    Raises:
        ConnectionError: If unable to connect to FalkorDB
    """
    global _graph_instance

    if _graph_instance is not None:
        return _graph_instance

    conn = _get_connection()
    _graph_instance = conn.select_graph(FALKORDB_GRAPH_NAME)

    return _graph_instance


def health_check() -> bool:
    """
    Check if FalkorDB is healthy and responsive.

    Returns:
        bool: True if healthy, False otherwise
    """
    try:
        graph = get_graph()
        # Simple query to test responsiveness
        result = graph.query("RETURN 1 AS test")
        return len(result.result_set) > 0

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False


def create_node(label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a node in the graph.

    Args:
        label: Node label (e.g., "Resource", "Tenant", "Project")
        properties: Node properties as key-value pairs

    Returns:
        Dict with created node properties

    Raises:
        ValueError: If required properties are missing
        Exception: If node creation fails
    """
    if not label:
        raise ValueError("Node label is required")

    if not properties:
        raise ValueError("Node properties are required")

    # Validate property keys for Cypher injection safety
    if not all(k.replace('_', '').replace('.', '').isalnum() for k in properties.keys()):
        raise ValueError("Property keys must be alphanumeric with underscores/dots only")

    try:
        graph = get_graph()

        # Build Cypher CREATE query
        # Convert properties to Cypher format: {key: value, ...}
        props_str = ", ".join(
            [f"{key}: ${key}" for key in properties.keys()]
        )

        query = f"CREATE (n:{label} {{{props_str}}}) RETURN n"

        logger.debug(f"Creating node: {query} with params: {properties}")

        result = graph.query(query, params=properties)

        if not result.result_set:
            raise Exception("Node creation returned no result")

        # Return created node properties
        created_node = dict(properties)
        logger.info(f"Created {label} node: {created_node.get('id', created_node.get('name', 'unknown'))}")

        return created_node

    except Exception as e:
        logger.error(f"Failed to create {label} node: {e}")
        raise


def create_relationship(
    from_node_id: str,
    from_label: str,
    rel_type: str,
    to_node_id: str,
    to_label: str,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a relationship between two nodes.

    Args:
        from_node_id: Source node ID property value
        from_label: Source node label
        rel_type: Relationship type (e.g., "OWNS", "CONTAINS")
        to_node_id: Target node ID property value
        to_label: Target node label
        properties: Optional relationship properties

    Returns:
        Dict with relationship details

    Raises:
        ValueError: If required parameters are missing
        Exception: If relationship creation fails
    """
    if not all([from_node_id, from_label, rel_type, to_node_id, to_label]):
        raise ValueError("All node and relationship identifiers are required")

    try:
        graph = get_graph()

        # Build Cypher MATCH + CREATE query
        if properties:
            props_str = ", ".join([f"{key}: ${key}" for key in properties.keys()])
            rel_props = f" {{{props_str}}}"
            params = dict(properties)
        else:
            rel_props = ""
            params = {}

        params["from_id"] = from_node_id
        params["to_id"] = to_node_id

        query = f"""
        MATCH (a:{from_label}), (b:{to_label})
        WHERE a.id = $from_id AND b.id = $to_id
        CREATE (a)-[r:{rel_type}{rel_props}]->(b)
        RETURN r
        """

        logger.debug(f"Creating relationship: {query} with params: {params}")

        result = graph.query(query, params=params)

        if not result.result_set:
            raise Exception(
                f"Relationship creation failed: nodes not found or relationship already exists"
            )

        logger.info(
            f"Created relationship: ({from_label})-[{rel_type}]->({to_label})"
        )

        return {
            "from_node_id": from_node_id,
            "from_label": from_label,
            "rel_type": rel_type,
            "to_node_id": to_node_id,
            "to_label": to_label,
            "properties": properties or {},
        }

    except Exception as e:
        logger.error(f"Failed to create relationship: {e}")
        raise


def query_nodes(
    label: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Query nodes by label and optional filters.

    Args:
        label: Node label to query
        filters: Optional property filters (exact match)
        limit: Optional result limit

    Returns:
        List of node properties as dicts

    Raises:
        Exception: If query fails
    """
    if not label:
        raise ValueError("Node label is required")

    # Validate filter keys for Cypher injection safety
    if filters and not all(k.replace('_', '').replace('.', '').isalnum() for k in filters.keys()):
        raise ValueError("Filter keys must be alphanumeric with underscores/dots only")

    try:
        graph = get_graph()

        # Build Cypher MATCH query
        if filters:
            where_clauses = []
            params = {}
            for key, value in filters.items():
                param_name = f"filter_{key}"
                where_clauses.append(f"n.{key} = ${param_name}")
                params[param_name] = value

            where_str = " WHERE " + " AND ".join(where_clauses)
        else:
            where_str = ""
            params = {}

        limit_str = f" LIMIT {limit}" if limit else ""

        query = f"MATCH (n:{label}){where_str} RETURN n{limit_str}"

        logger.debug(f"Querying nodes: {query} with params: {params}")

        result = graph.query(query, params=params)

        nodes = []
        for record in result.result_set:
            # FalkorDB returns node as first element
            node_data = record[0]

            # Extract properties from node
            if hasattr(node_data, 'properties'):
                node_props = dict(node_data.properties)
            else:
                # Fallback: node is already a dict
                node_props = node_data if isinstance(node_data, dict) else {}

            nodes.append(node_props)

        logger.info(f"Query returned {len(nodes)} {label} nodes")
        return nodes

    except Exception as e:
        logger.error(f"Failed to query {label} nodes: {e}")
        raise


def query_relationships(
    from_node_id: str,
    from_label: str,
    rel_type: str,
    include_deleted: bool = False,
) -> List[Dict[str, Any]]:
    """
    Query relationships from a node.

    By default, only returns active relationships (deleted_at IS NULL).
    Use include_deleted=True to get historical relationships.

    Args:
        from_node_id: Source node ID
        from_label: Source node label
        rel_type: Relationship type
        include_deleted: Include soft-deleted relationships (default: False)

    Returns:
        List of relationship dicts with target node info:
        [
            {
                "from_node_id": "...",
                "to_node_id": "...",
                "rel_type": "...",
                "properties": {...}
            }
        ]

    Raises:
        Exception: If query fails
    """
    if not all([from_node_id, from_label, rel_type]):
        raise ValueError("All parameters are required")

    try:
        graph = get_graph()

        # Filter out soft-deleted relationships by default
        where_clause = "" if include_deleted else "WHERE r.deleted_at IS NULL"

        query = f"""
        MATCH (a:{from_label} {{id: $from_id}})-[r:{rel_type}]->(b)
        {where_clause}
        RETURN a.id AS from_id, type(r) AS rel_type, properties(r) AS props, b.id AS to_id
        """

        result = graph.query(query, params={"from_id": from_node_id})

        relationships = []
        for record in result.result_set:
            relationships.append({
                "from_node_id": record[0],
                "rel_type": record[1],
                "properties": dict(record[2]) if record[2] else {},
                "to_node_id": record[3],
            })

        logger.debug(f"Found {len(relationships)} {rel_type} relationships for {from_node_id}")
        return relationships

    except Exception as e:
        logger.error(f"Failed to query relationships: {e}")
        raise


def soft_delete_relationship(
    from_node_id: str,
    from_label: str,
    rel_type: str,
    to_node_id: str,
    to_label: str,
) -> bool:
    """
    Soft-delete a relationship by setting deleted_at timestamp.

    Preserves relationship for historical queries while filtering it out
    from active relationship queries.

    Args:
        from_node_id: Source node ID
        from_label: Source node label
        rel_type: Relationship type
        to_node_id: Target node ID
        to_label: Target node label

    Returns:
        bool: True if soft-deleted, False if not found

    Raises:
        Exception: If soft-deletion fails
    """
    if not all([from_node_id, from_label, rel_type, to_node_id, to_label]):
        raise ValueError("All parameters are required")

    try:
        from datetime import datetime, UTC
        graph = get_graph()

        deleted_at = datetime.now(UTC).isoformat()

        query = f"""
        MATCH (a:{from_label} {{id: $from_id}})-[r:{rel_type}]->(b:{to_label} {{id: $to_id}})
        SET r.deleted_at = $deleted_at
        RETURN count(r) AS updated_count
        """

        result = graph.query(
            query,
            params={"from_id": from_node_id, "to_id": to_node_id, "deleted_at": deleted_at}
        )

        updated = result.result_set[0][0] > 0 if result.result_set else False

        if updated:
            logger.info(f"Soft-deleted relationship: ({from_label})-[{rel_type}]->({to_label})")
        else:
            logger.debug(f"Relationship not found for soft-deletion")

        return updated

    except Exception as e:
        logger.error(f"Failed to soft-delete relationship: {e}")
        raise


def delete_relationship(
    from_node_id: str,
    from_label: str,
    rel_type: str,
    to_node_id: str,
    to_label: str,
) -> bool:
    """
    Delete a relationship between two nodes (hard delete).

    Note: For dependency relationships, prefer soft_delete_relationship()
    to preserve history for audit trail.

    Args:
        from_node_id: Source node ID
        from_label: Source node label
        rel_type: Relationship type
        to_node_id: Target node ID
        to_label: Target node label

    Returns:
        bool: True if deleted, False if not found

    Raises:
        Exception: If deletion fails
    """
    if not all([from_node_id, from_label, rel_type, to_node_id, to_label]):
        raise ValueError("All parameters are required")

    try:
        graph = get_graph()

        query = f"""
        MATCH (a:{from_label} {{id: $from_id}})-[r:{rel_type}]->(b:{to_label} {{id: $to_id}})
        DELETE r
        RETURN count(r) AS deleted_count
        """

        result = graph.query(
            query,
            params={"from_id": from_node_id, "to_id": to_node_id}
        )

        deleted = result.result_set[0][0] > 0 if result.result_set else False

        if deleted:
            logger.info(f"Deleted relationship: ({from_label})-[{rel_type}]->({to_label})")
        else:
            logger.debug(f"Relationship not found for deletion")

        return deleted

    except Exception as e:
        logger.error(f"Failed to delete relationship: {e}")
        raise


def delete_node(label: str, node_id: str) -> bool:
    """
    Delete a node by ID.

    Args:
        label: Node label
        node_id: Node ID property value

    Returns:
        bool: True if deleted, False if not found

    Raises:
        Exception: If deletion fails
    """
    if not label or not node_id:
        raise ValueError("Label and node_id are required")

    try:
        graph = get_graph()

        query = f"""
        MATCH (n:{label} {{id: $node_id}})
        DETACH DELETE n
        RETURN count(n) AS deleted_count
        """

        result = graph.query(query, params={"node_id": node_id})

        deleted = result.result_set[0][0] > 0 if result.result_set else False

        if deleted:
            logger.info(f"Deleted {label} node: {node_id}")
        else:
            logger.warning(f"Node not found for deletion: {label} {node_id}")

        return deleted

    except Exception as e:
        logger.error(f"Failed to delete {label} node: {e}")
        raise


def reset_graph() -> None:
    """
    Delete all nodes and relationships in the graph.

    WARNING: This is destructive and should only be used in tests.
    NOTE: This does NOT drop indexes - indexes persist across resets.
    """
    try:
        graph = get_graph()

        query = "MATCH (n) DETACH DELETE n"
        graph.query(query)

        logger.warning("Graph reset: all nodes and relationships deleted")

    except Exception as e:
        logger.error(f"Failed to reset graph: {e}")
        raise


def drop_all_indexes() -> None:
    """
    Drop all indexes from the graph.

    WARNING: This is destructive and should only be used in tests.
    """
    try:
        graph = get_graph()

        # Query existing indexes
        result = graph.query("CALL db.indexes()")

        # Drop each index
        for record in result.result_set:
            if len(record) >= 2:
                label = record[0]
                properties = record[1]

                # properties is a list like ['tenant_id']
                if isinstance(properties, list):
                    for prop in properties:
                        try:
                            # FalkorDB DROP INDEX syntax
                            drop_query = f"DROP INDEX ON :{label}({prop})"
                            graph.query(drop_query)
                            logger.info(f"Dropped index on {label}.{prop}")
                        except Exception as e:
                            logger.warning(f"Failed to drop index on {label}.{prop}: {e}")

    except Exception as e:
        logger.error(f"Failed to drop indexes: {e}")
        raise


def close_connection() -> None:
    """
    Close FalkorDB connection pool.

    Should be called on application shutdown.
    """
    global _connection_pool, _graph_instance

    if _connection_pool:
        try:
            # FalkorDB client doesn't need explicit close
            # Just reset the global variables
            logger.info("FalkorDB connection closed")
        except Exception as e:
            logger.error(f"Error closing FalkorDB connection: {e}")
        finally:
            _connection_pool = None
            _graph_instance = None
