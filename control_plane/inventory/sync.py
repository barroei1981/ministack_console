"""
Sync layer: translates changes to FalkorDB operations.

Maps Change objects to graph CRUD operations.
"""

import json
import logging

from control_plane.events import event_bus
from control_plane.graph.query import create_node, delete_node, get_graph, query_nodes
from control_plane.tenants.isolation import ensure_tenant_exists

from .models import Change, ChangeType

logger = logging.getLogger(__name__)


async def sync_changes(changes: list[Change]) -> None:
    """
    Sync changes to FalkorDB.

    For each change:
    - CREATED: create new Resource node
    - UPDATED: update existing Resource node (delete + create)
    - DELETED: delete Resource node

    Args:
        changes: List of changes to sync

    Raises:
        Exception: If graph operations fail
    """
    if not changes:
        logger.info("No changes to sync")
        return

    logger.info(f"Syncing {len(changes)} changes to FalkorDB...")

    for change in changes:
        try:
            if change.change_type == ChangeType.CREATED:
                await _sync_created(change)

            elif change.change_type == ChangeType.UPDATED:
                await _sync_updated(change)

            elif change.change_type == ChangeType.DELETED:
                await _sync_deleted(change)

        except Exception as e:
            logger.error(
                f"Failed to sync change {change.change_type.value}: {e}",
                exc_info=True,
            )
            # Continue with other changes rather than failing entire sync
            continue

    logger.info("Sync complete")


async def _sync_created(change: Change) -> None:
    """
    Sync CREATED change: create new Resource node.

    Per MSCL-3: Ensure Tenant node exists before creating Resource.

    Args:
        change: CREATED change with resource
    """
    resource = change.resource
    if not resource:
        raise ValueError("CREATED change missing resource")

    # Ensure tenant exists (idempotent) per MSCL-3
    await ensure_tenant_exists(resource.tenant_id)

    # Convert state dict to JSON string for FalkorDB storage
    properties = resource.to_dict()
    properties["state"] = json.dumps(properties["state"])

    # Create node (synchronous - FalkorDB client is not async)
    create_node(label="Resource", properties=properties)

    logger.info(f"Created Resource node: {resource.type} {resource.name} ({resource.id})")

    # Emit RESOURCE_CREATED event (MSCL-7)
    try:
        await event_bus.publish(
            event_type="RESOURCE_CREATED",
            resource=resource.to_dict(),
            tenant_id=resource.tenant_id,
        )
    except Exception as e:
        logger.error(f"[OPERATIONAL] Failed to emit RESOURCE_CREATED event: {e}")


async def _sync_updated(change: Change) -> None:
    """
    Sync UPDATED change: update existing Resource node.

    Strategy: delete old node and create new one (simpler than UPDATE query).

    Args:
        change: UPDATED change with resource
    """
    resource = change.resource
    if not resource:
        raise ValueError("UPDATED change missing resource")

    # Delete existing node
    delete_node(label="Resource", node_id=resource.id)

    # Create new node with updated properties
    properties = resource.to_dict()
    properties["state"] = json.dumps(properties["state"])

    create_node(label="Resource", properties=properties)

    logger.info(f"Updated Resource node: {resource.type} {resource.name} ({resource.id})")

    # Emit RESOURCE_UPDATED event (MSCL-7)
    try:
        await event_bus.publish(
            event_type="RESOURCE_UPDATED",
            resource=resource.to_dict(),
            tenant_id=resource.tenant_id,
        )
    except Exception as e:
        logger.error(f"[OPERATIONAL] Failed to emit RESOURCE_UPDATED event: {e}")


async def _sync_deleted(change: Change) -> None:
    """
    Sync DELETED change: delete Resource node.

    Args:
        change: DELETED change with resource_id
    """
    resource_id = change.resource_id
    if not resource_id:
        raise ValueError("DELETED change missing resource_id")

    # Need to get tenant_id before deleting the node
    # Query the node first to get tenant_id for event emission
    nodes = query_nodes("Resource", filters={"id": resource_id})
    tenant_id = nodes[0].get("tenant_id") if nodes else None
    resource_type = nodes[0].get("type") if nodes else "unknown"

    deleted = delete_node(label="Resource", node_id=resource_id)

    if deleted and tenant_id:
        logger.info(f"Deleted Resource node: {resource_id}")

        # Emit RESOURCE_DELETED event (MSCL-7)
        # Minimal payload per spec: {id, type, tenant_id}
        try:
            await event_bus.publish(
                event_type="RESOURCE_DELETED",
                resource={"id": resource_id, "type": resource_type, "tenant_id": tenant_id},
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error(f"[OPERATIONAL] Failed to emit RESOURCE_DELETED event: {e}")
    elif deleted:
        logger.warning(f"Deleted Resource node {resource_id} but no tenant_id found (skipping event)")
    else:
        logger.warning(f"Resource node not found for deletion: {resource_id}")


async def mark_resources_stale(tenant_id: str) -> None:
    """
    Mark all resources as stale for a tenant.

    Called after 3 consecutive poll failures (90 seconds).

    Args:
        tenant_id: Tenant ID to mark stale
    """
    try:
        graph = get_graph()

        # Update all Resource nodes for this tenant, adding stale flag to state
        query = """
        MATCH (r:Resource {tenant_id: $tenant_id})
        SET r.stale = true
        RETURN count(r) AS marked_count
        """

        result = graph.query(query, params={"tenant_id": tenant_id})

        count = result.result_set[0][0] if result.result_set else 0
        logger.warning(f"Marked {count} resources as stale for tenant {tenant_id}")

    except Exception as e:
        logger.error(f"Failed to mark resources as stale: {e}")
        raise


async def clear_stale_markers(tenant_id: str) -> None:
    """
    Clear stale markers for all resources in a tenant.

    Called after successful poll following failures.

    Args:
        tenant_id: Tenant ID to clear stale markers
    """
    try:
        graph = get_graph()

        # Remove stale property from all Resource nodes for this tenant
        query = """
        MATCH (r:Resource {tenant_id: $tenant_id})
        WHERE r.stale IS NOT NULL
        REMOVE r.stale
        RETURN count(r) AS cleared_count
        """

        result = graph.query(query, params={"tenant_id": tenant_id})

        count = result.result_set[0][0] if result.result_set else 0
        logger.info(f"Cleared stale markers for {count} resources in tenant {tenant_id}")

    except Exception as e:
        logger.error(f"Failed to clear stale markers: {e}")
        raise
