"""
Dependency sync manager for FalkorDB.

Orchestrates dependency detection and syncs relationships to graph database.
"""

import logging
from typing import Any

from ..graph.query import (
    create_relationship,
    query_nodes,
    query_relationships,
    soft_delete_relationship,
)
from ..ministack_client import MiniStackClient
from ..observability import log_audit, trace_operation
from .detector import (
    detect_lambda_event_sources,
    detect_lambda_s3_dependencies,
    detect_s3_iam_dependencies,
)
from .models import Dependency, DependencyType

logger = logging.getLogger(__name__)


async def sync_all_dependencies(
    resources: list[dict[str, Any]], client: MiniStackClient
) -> dict[str, int]:
    """
    Detect and sync dependencies for all resources.

    Compares detected dependencies with existing DEPENDS_ON relationships
    and creates/deletes relationships as needed.

    Args:
        resources: List of resource dicts (from poller)
        client: MiniStackClient instance

    Returns:
        Dict with sync statistics:
        {
            "dependencies_created": 5,
            "dependencies_deleted": 2,
            "resources_processed": 10,
            "errors": 0
        }
    """
    with trace_operation("sync_all_dependencies", resource_count=len(resources)):
        stats = {
            "dependencies_created": 0,
            "dependencies_deleted": 0,
            "resources_processed": 0,
            "errors": 0,
        }

        # Group resources by type for efficient processing
        lambda_resources = [r for r in resources if r.get("type") == "lambda:function"]
        s3_resources = [r for r in resources if r.get("type") == "s3:bucket"]

        logger.info(
            f"[OPERATIONAL] Starting dependency sync for {len(lambda_resources)} Lambda functions, "
            f"{len(s3_resources)} S3 buckets"
        )

        # Process Lambda dependencies
        for lambda_resource in lambda_resources:
            try:
                await _sync_resource_dependencies(
                    resource=lambda_resource,
                    resource_type="lambda",
                    detect_funcs=[detect_lambda_s3_dependencies, detect_lambda_event_sources],
                    client=client,
                    stats=stats,
                )
                stats["resources_processed"] += 1
            except Exception as e:
                logger.exception(
                    f"[OPERATIONAL] Failed to sync dependencies for Lambda {lambda_resource.get('name')}: {e}"
                )
                stats["errors"] += 1

        # Process S3 dependencies
        for s3_resource in s3_resources:
            try:
                await _sync_resource_dependencies(
                    resource=s3_resource,
                    resource_type="s3",
                    detect_funcs=[detect_s3_iam_dependencies],
                    client=client,
                    stats=stats,
                )
                stats["resources_processed"] += 1
            except Exception as e:
                logger.exception(
                    f"[OPERATIONAL] Failed to sync dependencies for S3 {s3_resource.get('name')}: {e}"
                )
                stats["errors"] += 1

        logger.info(
            f"[OPERATIONAL] Dependency sync complete: {stats['dependencies_created']} created, "
            f"{stats['dependencies_deleted']} deleted, "
            f"{stats['resources_processed']} resources processed, "
            f"{stats['errors']} errors"
        )

        return stats


async def _sync_resource_dependencies(
    resource: dict[str, Any],
    resource_type: str,
    detect_funcs: list,
    client: MiniStackClient,
    stats: dict[str, int],
) -> None:
    """
    Sync dependencies for a single resource (extracted common logic).

    Args:
        resource: Resource dict
        resource_type: Resource type label (for logging)
        detect_funcs: List of detection functions to run
        client: MiniStackClient instance
        stats: Stats dict to update
    """
    # Field validation
    required_fields = ["id", "name", "tenant_id"]
    for field in required_fields:
        if field not in resource:
            logger.error(f"[OPERATIONAL] Resource missing required field '{field}': {resource}")
            stats["errors"] += 1
            return

    resource_arn = resource["id"]
    tenant_id = resource["tenant_id"]

    with trace_operation(f"sync_{resource_type}_dependencies", resource_id=resource_arn):
        # Detect all dependencies
        detected_deps = []
        for detect_func in detect_funcs:
            deps = await detect_func(resource, client)
            detected_deps.extend(deps)

        # Get existing dependencies from FalkorDB
        existing_rels = query_relationships(
            from_node_id=resource_arn,
            from_label="Resource",
            rel_type="DEPENDS_ON",
        )

        # Convert existing relationships to Dependency objects for comparison
        existing_deps = []
        for rel in existing_rels:
            # Reconstruct dependency type from properties
            rel_props = rel.get("properties", {})
            dep_type_str = rel_props.get("type")

            try:
                dep_type = DependencyType(dep_type_str)
            except ValueError:
                logger.warning(f"[OPERATIONAL] Unknown dependency type: {dep_type_str}")
                continue

            existing_deps.append(
                Dependency(
                    source_id=rel["from_node_id"],
                    target_id=rel["to_node_id"],
                    type=dep_type,
                    metadata=rel_props.get("metadata", {}),
                )
            )

        # Sync: create new dependencies
        for dep in detected_deps:
            if dep not in existing_deps:
                # Verify target resource exists and has same tenant_id
                target_nodes = query_nodes("Resource", filters={"id": dep.target_id})

                if not target_nodes:
                    logger.warning(
                        f"[OPERATIONAL] Target resource not found in FalkorDB: {dep.target_id}. "
                        "Skipping dependency creation."
                    )
                    continue

                target_tenant = target_nodes[0].get("tenant_id")
                if target_tenant != tenant_id:
                    # SECURITY log for cross-tenant block
                    logger.warning(
                        f"[SECURITY] Cross-tenant dependency blocked: {resource_arn} → {dep.target_id} "
                        f"(tenant {tenant_id} → {target_tenant})"
                    )
                    continue

                try:
                    create_relationship(
                        from_node_id=dep.source_id,
                        from_label="Resource",
                        rel_type="DEPENDS_ON",
                        to_node_id=dep.target_id,
                        to_label="Resource",
                        properties=dep.to_properties(),
                    )
                    stats["dependencies_created"] += 1

                    # AUDIT log for dependency creation
                    log_audit(
                        message=f"Dependency created: {resource_arn} → {dep.target_id}",
                        event_type="DEPENDENCY_CREATED",
                        actor={"id": tenant_id, "type": "SYSTEM"},
                        target={"type": "DEPENDS_ON", "id": f"{dep.source_id}→{dep.target_id}"},
                        action="CREATE",
                        status="SUCCESS",
                        changes={"before": {}, "after": dep.to_properties()},
                    )

                    logger.debug(f"[OPERATIONAL] Created dependency: {resource_arn} → {dep.target_id}")
                except Exception as e:
                    logger.error(f"[OPERATIONAL] Failed to create dependency: {e}")
                    stats["errors"] += 1

        # Sync: soft-delete stale dependencies (preserves history)
        for dep in existing_deps:
            if dep not in detected_deps:
                try:
                    soft_delete_relationship(
                        from_node_id=dep.source_id,
                        from_label="Resource",
                        rel_type="DEPENDS_ON",
                        to_node_id=dep.target_id,
                        to_label="Resource",
                    )
                    stats["dependencies_deleted"] += 1

                    # AUDIT log for dependency soft-deletion
                    log_audit(
                        message=f"Dependency soft-deleted: {resource_arn} → {dep.target_id}",
                        event_type="DEPENDENCY_DELETED",
                        actor={"id": tenant_id, "type": "SYSTEM"},
                        target={"type": "DEPENDS_ON", "id": f"{dep.source_id}→{dep.target_id}"},
                        action="DELETE",
                        status="SUCCESS",
                        changes={"before": dep.to_properties(), "after": {"deleted_at": "set"}},
                    )

                    logger.debug(f"[OPERATIONAL] Soft-deleted stale dependency: {resource_arn} → {dep.target_id}")
                except Exception as e:
                    logger.error(f"[OPERATIONAL] Failed to soft-delete dependency: {e}")
                    stats["errors"] += 1
