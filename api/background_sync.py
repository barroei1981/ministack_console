"""
Background resource synchronization service.

Automatically discovers resources from MiniStack and syncs to FalkorDB.
Runs periodically without manual intervention.
"""

import asyncio
import logging
import os
from typing import Set

from api.sync_resources import sync_all_resources
from control_plane.observability import log_operational

logger = logging.getLogger(__name__)

# Configuration
SYNC_INTERVAL_SECONDS = int(os.getenv("AUTO_SYNC_INTERVAL", "300"))  # 5 minutes default
MINISTACK_ENDPOINT = os.getenv("MINISTACK_ENDPOINT", "http://mari-ann-ministack:4566")

# Track known tenants (discovered from resource creation events)
_known_tenants: Set[str] = set()


def register_tenant(tenant_id: str):
    """Register a tenant for automatic syncing."""
    _known_tenants.add(tenant_id)
    log_operational(f"Registered tenant {tenant_id} for auto-sync")


def get_known_tenants() -> Set[str]:
    """Get all tenants registered for syncing."""
    # Default tenant
    if not _known_tenants:
        return {"000000000001"}
    return _known_tenants


async def sync_tenant(tenant_id: str):
    """Sync all resources for a single tenant."""
    try:
        result = await sync_all_resources(
            endpoint_url=MINISTACK_ENDPOINT,
            tenant_id=tenant_id
        )

        total = result["total"]
        if total > 0:
            log_operational(
                f"Auto-synced {total} resources for tenant {tenant_id}",
                s3_buckets=result["s3_buckets"],
                dynamodb_tables=result["dynamodb_tables"],
                lambda_functions=result["lambda_functions"]
            )

        return result
    except Exception as e:
        log_operational(
            f"Auto-sync failed for tenant {tenant_id}: {e}",
            error=str(e)
        )
        return None


async def sync_all_tenants():
    """Sync resources for all known tenants."""
    tenants = get_known_tenants()

    if not tenants:
        log_operational("No tenants registered for auto-sync")
        return

    log_operational(f"Starting auto-sync for {len(tenants)} tenants")

    # Sync all tenants in parallel
    tasks = [sync_tenant(tenant_id) for tenant_id in tenants]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(1 for r in results if r and isinstance(r, dict))
    log_operational(
        f"Auto-sync complete: {success_count}/{len(tenants)} tenants synced successfully"
    )


async def background_sync_loop():
    """
    Background task that periodically syncs resources.

    Runs continuously, syncing all known tenants at regular intervals.
    """
    log_operational(
        f"Background sync started (interval: {SYNC_INTERVAL_SECONDS}s, endpoint: {MINISTACK_ENDPOINT})"
    )

    while True:
        try:
            await sync_all_tenants()
        except Exception as e:
            logger.error(f"Background sync error: {e}")
            log_operational(f"Background sync error: {e}")

        # Wait before next sync
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


def start_background_sync():
    """
    Start the background sync task.

    Call this from main.py startup to enable automatic resource discovery.
    """
    # Create task but don't await it (runs in background)
    asyncio.create_task(background_sync_loop())
    log_operational("Background sync task started")
