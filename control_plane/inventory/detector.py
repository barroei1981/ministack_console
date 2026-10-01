"""
Change detection algorithm.

Compares current resource state to previous snapshot and produces list of changes.
"""

import logging
from typing import List

from .models import Resource, Change, ChangeType, Snapshot

logger = logging.getLogger(__name__)


def detect_changes(current: List[Resource], previous: Snapshot) -> List[Change]:
    """
    Detect changes between current resources and previous snapshot.

    Algorithm:
    1. Build sets of current and previous resource IDs
    2. CREATED: IDs in current but not in previous
    3. DELETED: IDs in previous but not in current
    4. UPDATED: IDs in both, but resource properties changed

    Args:
        current: List of current resources from MiniStack API
        previous: Previous snapshot of resources

    Returns:
        List of detected changes (CREATED/UPDATED/DELETED)
    """
    current_ids = {r.id for r in current}
    previous_ids = previous.get_ids()

    changes = []

    # Detect CREATED resources
    created_ids = current_ids - previous_ids
    for resource in current:
        if resource.id in created_ids:
            changes.append(Change(change_type=ChangeType.CREATED, resource=resource))
            logger.debug(f"CREATED: {resource.type} {resource.name} ({resource.id})")

    # Detect DELETED resources
    deleted_ids = previous_ids - current_ids
    for resource_id in deleted_ids:
        changes.append(Change(change_type=ChangeType.DELETED, resource_id=resource_id))
        logger.debug(f"DELETED: {resource_id}")

    # Detect UPDATED resources
    for resource in current:
        if resource.id in previous_ids:
            previous_resource = previous.get(resource.id)

            # Compare resource properties (using __eq__ from Resource)
            if resource != previous_resource:
                changes.append(
                    Change(change_type=ChangeType.UPDATED, resource=resource)
                )
                logger.debug(
                    f"UPDATED: {resource.type} {resource.name} ({resource.id})"
                )

    logger.info(
        f"Change detection: {len([c for c in changes if c.change_type == ChangeType.CREATED])} created, "
        f"{len([c for c in changes if c.change_type == ChangeType.UPDATED])} updated, "
        f"{len([c for c in changes if c.change_type == ChangeType.DELETED])} deleted"
    )

    return changes
