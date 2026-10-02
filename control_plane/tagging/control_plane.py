"""
Control-plane tagging operations.

Stores tags in FalkorDB only (no MiniStack write-through).
Applies to ALL resources regardless of service type.
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any

from control_plane.graph.query import (
    get_graph,
    query_nodes,
)
from control_plane.observability import log_audit, trace_operation
from control_plane.tagging.models import (
    MAX_TAG_KEY_LENGTH,
    MAX_TAG_VALUE_LENGTH,
    TagNamespace,
)
from control_plane.tenants.isolation import validate_tenant_id

logger = logging.getLogger(__name__)


def _validate_tag_key(key: str) -> None:
    """
    Validate tag key format for control-plane tags.

    Enforces:
    - Length ≤ MAX_TAG_KEY_LENGTH (128 chars)
    - Alphanumeric + allowed special chars (prevents Cypher injection)

    Args:
        key: Tag key to validate

    Raises:
        ValueError: If key is invalid
    """
    if not key:
        raise ValueError("Tag key cannot be empty")

    if len(key) > MAX_TAG_KEY_LENGTH:
        raise ValueError(
            f"Tag key exceeds {MAX_TAG_KEY_LENGTH} characters (got {len(key)})"
        )

    # Allow alphanumeric + _-.: /=+@ (extends existing validation, adds AWS-compatible chars)
    if not re.match(r"^[a-zA-Z0-9_\-.:/=+@\s]+$", key):
        raise ValueError(
            "Tag key contains invalid characters (allowed: alphanumeric, _-.: /=+@)"
        )


def _validate_tag_value(value: str) -> None:
    """
    Validate tag value format.

    Enforces:
    - Length ≤ MAX_TAG_VALUE_LENGTH (256 chars)

    Args:
        value: Tag value to validate

    Raises:
        ValueError: If value is invalid
    """
    if len(value) > MAX_TAG_VALUE_LENGTH:
        raise ValueError(
            f"Tag value exceeds {MAX_TAG_VALUE_LENGTH} characters (got {len(value)})"
        )


def add_control_plane_tag(
    resource_id: str,
    key: str,
    value: str,
    tenant_id: str,
) -> dict[str, Any]:
    """
    Add control-plane tag to a resource.

    Creates Tag node and TAGGED_WITH relationship with namespace="control_plane".
    Idempotent: if tag already exists with same value, no-op.

    Args:
        resource_id: Resource ID to tag
        key: Tag key
        value: Tag value
        tenant_id: Tenant ID for isolation

    Returns:
        Dict with tag details

    Raises:
        ValueError: If validation fails or resource doesn't exist
        Exception: If FalkorDB operation fails

    Example:
        >>> add_control_plane_tag("s3:bucket:my-bucket", "project", "app-1", "123456789012")
        {'resource_id': 's3:bucket:my-bucket', 'key': 'project', 'value': 'app-1', ...}
    """
    validate_tenant_id(tenant_id)
    _validate_tag_key(key)
    _validate_tag_value(value)

    with trace_operation(
        "add_control_plane_tag",
        resource_id=resource_id,
        key=key,
        tenant_id=tenant_id,
    ):
        # Verify resource exists and belongs to tenant
        resources = query_nodes(
            "Resource",
            filters={"id": resource_id, "tenant_id": tenant_id},
        )

        if not resources:
            raise ValueError(
                f"Resource {resource_id} not found for tenant {tenant_id}"
            )

        # Get existing tags to capture BEFORE state
        old_tags = get_control_plane_tags(resource_id, tenant_id)

        # Create Tag node (idempotent via MERGE pattern)
        graph = get_graph()

        # Create or match Tag node
        tag_query = """
        MERGE (t:Tag {key: $key, value: $value})
        RETURN t
        """
        graph.query(
            tag_query,
            params={"key": key, "value": value},
        )

        # Create TAGGED_WITH relationship (idempotent)
        # Use MERGE to avoid duplicate relationships
        rel_query = """
        MATCH (r:Resource {id: $resource_id, tenant_id: $tenant_id})
        MATCH (t:Tag {key: $key, value: $value})
        MERGE (r)-[rel:TAGGED_WITH {namespace: $namespace, key: $key, value: $value}]->(t)
        RETURN rel
        """

        result = graph.query(
            rel_query,
            params={
                "resource_id": resource_id,
                "tenant_id": tenant_id,
                "key": key,
                "value": value,
                "namespace": TagNamespace.CONTROL_PLANE.value,
            },
        )

        if not result.result_set:
            raise Exception(
                f"Failed to create TAGGED_WITH relationship for resource {resource_id}"
            )

        # Get new tags for AFTER state
        new_tags = get_control_plane_tags(resource_id, tenant_id)

        # AUDIT log
        log_audit(
            "Control-plane tag added",
            event_type="TAG_ADDED",
            actor={"id": tenant_id, "type": "TENANT"},
            target={"type": "RESOURCE", "id": resource_id},
            action="CREATE",
            status="SUCCESS",
            changes={"before": old_tags, "after": new_tags},
            namespace=TagNamespace.CONTROL_PLANE.value,
        )

        logger.info(
            f"Added control-plane tag to {resource_id}: {key}={value}"
        )

        return {
            "resource_id": resource_id,
            "key": key,
            "value": value,
            "namespace": TagNamespace.CONTROL_PLANE.value,
            "tenant_id": tenant_id,
            "created_at": datetime.now(UTC).isoformat(),
        }


def remove_control_plane_tag(
    resource_id: str,
    key: str,
    tenant_id: str,
) -> bool:
    """
    Remove control-plane tag from a resource.

    Deletes TAGGED_WITH relationship with namespace="control_plane" and matching key.
    Idempotent: returns True even if tag doesn't exist.

    Args:
        resource_id: Resource ID
        key: Tag key to remove
        tenant_id: Tenant ID for isolation

    Returns:
        bool: True if tag was removed or didn't exist

    Raises:
        ValueError: If validation fails
        Exception: If FalkorDB operation fails

    Example:
        >>> remove_control_plane_tag("s3:bucket:my-bucket", "project", "123456789012")
        True
    """
    validate_tenant_id(tenant_id)
    _validate_tag_key(key)

    with trace_operation(
        "remove_control_plane_tag",
        resource_id=resource_id,
        key=key,
        tenant_id=tenant_id,
    ):
        # Get existing tags for BEFORE state
        old_tags = get_control_plane_tags(resource_id, tenant_id)

        graph = get_graph()

        # Delete TAGGED_WITH relationship with matching namespace and key
        delete_query = """
        MATCH (r:Resource {id: $resource_id, tenant_id: $tenant_id})-[rel:TAGGED_WITH]->(t:Tag)
        WHERE rel.namespace = $namespace AND rel.key = $key
        DELETE rel
        RETURN count(rel) AS deleted_count
        """

        result = graph.query(
            delete_query,
            params={
                "resource_id": resource_id,
                "tenant_id": tenant_id,
                "namespace": TagNamespace.CONTROL_PLANE.value,
                "key": key,
            },
        )

        deleted_count = result.result_set[0][0] if result.result_set else 0

        # Get new tags for AFTER state
        new_tags = get_control_plane_tags(resource_id, tenant_id)

        # AUDIT log
        log_audit(
            "Control-plane tag removed",
            event_type="TAG_REMOVED",
            actor={"id": tenant_id, "type": "TENANT"},
            target={"type": "RESOURCE", "id": resource_id},
            action="DELETE",
            status="SUCCESS" if deleted_count > 0 else "NO_OP",
            changes={"before": old_tags, "after": new_tags},
            namespace=TagNamespace.CONTROL_PLANE.value,
            key=key,
        )

        if deleted_count > 0:
            logger.info(
                f"Removed control-plane tag from {resource_id}: {key}"
            )
        else:
            logger.debug(
                f"Control-plane tag {key} not found on {resource_id} (no-op)"
            )

        return True


def get_control_plane_tags(
    resource_id: str,
    tenant_id: str,
) -> dict[str, str]:
    """
    Get all control-plane tags for a resource.

    Args:
        resource_id: Resource ID
        tenant_id: Tenant ID for isolation

    Returns:
        Dict mapping tag keys to values

    Raises:
        ValueError: If validation fails
        Exception: If FalkorDB query fails

    Example:
        >>> get_control_plane_tags("s3:bucket:my-bucket", "123456789012")
        {'project': 'app-1', 'environment': 'dev'}
    """
    validate_tenant_id(tenant_id)

    with trace_operation(
        "get_control_plane_tags",
        resource_id=resource_id,
        tenant_id=tenant_id,
    ):
        graph = get_graph()

        query = """
        MATCH (r:Resource {id: $resource_id, tenant_id: $tenant_id})-[rel:TAGGED_WITH]->(t:Tag)
        WHERE rel.namespace = $namespace
        RETURN rel.key AS key, rel.value AS value
        """

        result = graph.query(
            query,
            params={
                "resource_id": resource_id,
                "tenant_id": tenant_id,
                "namespace": TagNamespace.CONTROL_PLANE.value,
            },
        )

        tags = {}
        for record in result.result_set:
            key = record[0]
            value = record[1]
            tags[key] = value

        logger.debug(
            f"Retrieved {len(tags)} control-plane tags for {resource_id}"
        )

        return tags


def query_resources_by_tag(
    key: str,
    value: str,
    tenant_id: str,
    resource_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Query resources by control-plane tag.

    Returns all resources with matching tag in the tenant,
    optionally filtered by resource type.

    Args:
        key: Tag key to match
        value: Tag value to match
        tenant_id: Tenant ID for isolation
        resource_type: Optional resource type filter (e.g., "s3:bucket")

    Returns:
        List of Resource node properties as dicts

    Raises:
        ValueError: If validation fails
        Exception: If FalkorDB query fails

    Example:
        >>> query_resources_by_tag("project", "app-1", "123456789012")
        [{'id': 's3:bucket:my-bucket', 'type': 's3:bucket', ...}, ...]
    """
    validate_tenant_id(tenant_id)
    _validate_tag_key(key)

    with trace_operation(
        "query_resources_by_tag",
        key=key,
        value=value,
        tenant_id=tenant_id,
        resource_type=resource_type,
    ):
        graph = get_graph()

        # Build query with optional type filter
        type_filter = "AND r.type = $resource_type" if resource_type else ""

        query = f"""
        MATCH (r:Resource {{tenant_id: $tenant_id}})-[rel:TAGGED_WITH]->(t:Tag)
        WHERE rel.namespace = $namespace
          AND rel.key = $key
          AND rel.value = $value
          {type_filter}
        RETURN r
        """

        params = {
            "tenant_id": tenant_id,
            "namespace": TagNamespace.CONTROL_PLANE.value,
            "key": key,
            "value": value,
        }

        if resource_type:
            params["resource_type"] = resource_type

        result = graph.query(query, params=params)

        resources = []
        for record in result.result_set:
            node_data = record[0]

            if hasattr(node_data, "properties"):
                resource_props = dict(node_data.properties)
            else:
                resource_props = node_data if isinstance(node_data, dict) else {}

            resources.append(resource_props)

        logger.info(
            f"Query by tag {key}={value} returned {len(resources)} resources"
            + (f" (type={resource_type})" if resource_type else "")
        )

        return resources
