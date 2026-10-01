"""
Tenant isolation and management operations.

Enforces multi-tenant boundaries and provides tenant-aware operations.
Per MSCL-3: All resource queries must be tenant-scoped.
"""

import logging
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional

from control_plane.graph.query import (
    create_node,
    query_nodes,
    create_relationship,
)

logger = logging.getLogger(__name__)


def validate_tenant_id(tenant_id: str) -> None:
    """
    Validate tenant ID format.

    Args:
        tenant_id: Tenant ID to validate

    Raises:
        ValueError: If tenant_id is not 12 numeric digits
    """
    if not tenant_id:
        raise ValueError("tenant_id cannot be empty")

    if len(tenant_id) != 12:
        raise ValueError(
            f"Invalid tenant_id: {tenant_id}. Must be 12 digits (got {len(tenant_id)})"
        )

    if not tenant_id.isdigit():
        raise ValueError(f"Invalid tenant_id: {tenant_id}. Must be numeric")


async def ensure_tenant_exists(tenant_id: str) -> None:
    """
    Create Tenant node if it doesn't exist (idempotent MERGE operation).

    Per FR-3: Automatic tenant discovery and creation when first resource appears.

    Args:
        tenant_id: Tenant ID (12-digit MiniStack access key)

    Raises:
        ValueError: If tenant_id format is invalid
        Exception: If FalkorDB operation fails
    """
    validate_tenant_id(tenant_id)

    # Check if tenant already exists
    existing = query_nodes("Tenant", filters={"id": tenant_id})

    if existing:
        logger.debug(f"Tenant {tenant_id} already exists")
        return

    # Create new Tenant node
    create_node(
        "Tenant",
        {
            "id": tenant_id,
            "name": tenant_id,  # Default name is the ID
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

    logger.info(f"Created Tenant node: {tenant_id}")


def get_tenant_resources(
    tenant_id: str, resource_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all resources for a tenant, optionally filtered by type.

    Uses tenant_id index for performance per NFR-1 (<500ms for 1000 resources).

    Args:
        tenant_id: Tenant ID to query
        resource_type: Optional resource type filter (e.g., "s3:bucket")

    Returns:
        List of Resource node properties as dicts

    Raises:
        ValueError: If tenant_id format is invalid
        Exception: If FalkorDB query fails

    Example:
        >>> get_tenant_resources("123456789012")
        [{'id': 'bucket-1', 'type': 's3:bucket', ...}, ...]

        >>> get_tenant_resources("123456789012", resource_type="lambda:function")
        [{'id': 'func-1', 'type': 'lambda:function', ...}]
    """
    validate_tenant_id(tenant_id)

    filters = {"tenant_id": tenant_id}
    if resource_type:
        filters["type"] = resource_type

    resources = query_nodes("Resource", filters=filters)

    logger.debug(
        f"Retrieved {len(resources)} resources for tenant {tenant_id}"
        + (f" (type={resource_type})" if resource_type else "")
    )

    return resources


def create_project_with_ownership(
    project_name: str, tenant_id: str, description: str = ""
) -> Dict[str, Any]:
    """
    Create Project node and link to Tenant via OWNS relationship.

    Per FR-4: Projects are logical groupings within a tenant.

    Args:
        project_name: Unique project name (used as ID)
        tenant_id: Owner tenant ID
        description: Optional project description

    Returns:
        Dict with created Project node properties

    Raises:
        ValueError: If tenant doesn't exist or tenant_id format is invalid
        Exception: If FalkorDB operation fails

    Example:
        >>> create_project_with_ownership("my-app", "123456789012", "My app resources")
        {'name': 'my-app', 'tenant_id': '123456789012', ...}
    """
    validate_tenant_id(tenant_id)

    # Verify tenant exists
    tenant = query_nodes("Tenant", filters={"id": tenant_id})
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} does not exist")

    # Create Project node
    # Note: Project uses name as identifier, but also needs id for relationship matching
    project_props = {
        "id": project_name,  # Use name as id for consistency with relationship matching
        "name": project_name,
        "description": description,
        "tenant_id": tenant_id,
        "created_at": datetime.now(UTC).isoformat(),
    }

    project = create_node("Project", project_props)

    logger.info(f"Created Project node: {project_name} for tenant {tenant_id}")

    # Create OWNS relationship
    create_relationship(
        from_node_id=tenant_id,
        from_label="Tenant",
        rel_type="OWNS",
        to_node_id=project_name,
        to_label="Project",
    )

    logger.info(f"Created (Tenant)-[:OWNS]->(Project) relationship")

    return project


def list_tenants() -> List[Dict[str, Any]]:
    """
    List all tenants in the system.

    Returns:
        List of Tenant node properties as dicts

    Raises:
        Exception: If FalkorDB query fails

    Example:
        >>> list_tenants()
        [{'id': '123456789012', 'name': '123456789012', ...}, ...]
    """
    tenants = query_nodes("Tenant")

    logger.info(f"Retrieved {len(tenants)} tenants")

    return tenants
