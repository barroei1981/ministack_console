"""
Main async polling loop.

Orchestrates resource polling every 30 seconds, change detection, and sync to FalkorDB.
"""

import asyncio
import os
import logging
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional

from control_plane.ministack_client import MiniStackClient
from .models import Resource, Snapshot
from .detector import detect_changes
from .sync import sync_changes, mark_resources_stale, clear_stale_markers

logger = logging.getLogger(__name__)

# Configuration
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
FAILURE_THRESHOLD = int(os.getenv("POLL_FAILURE_THRESHOLD", "3"))


class ResourcePoller:
    """
    Async resource poller.

    Polls MiniStack API every POLL_INTERVAL_SECONDS, detects changes, syncs to FalkorDB.
    """

    def __init__(self, client: Optional[MiniStackClient] = None):
        self.client = client or MiniStackClient()
        self.last_snapshot: Optional[Snapshot] = None
        self.failure_count = 0
        self.last_instance_id: Optional[str] = None
        self.running = False

    async def start(self) -> None:
        """
        Start polling loop.

        Runs indefinitely until stopped.
        """
        logger.info(
            f"Starting resource poller (interval: {POLL_INTERVAL_SECONDS}s, "
            f"failure threshold: {FAILURE_THRESHOLD})"
        )

        self.running = True

        while self.running:
            try:
                await self._poll_cycle()

            except Exception as e:
                logger.error(f"Unexpected error in poll cycle: {e}", exc_info=True)
                self.failure_count += 1

                if self.failure_count >= FAILURE_THRESHOLD:
                    logger.error(
                        f"Poll failed {self.failure_count} times consecutively - "
                        "marking resources as stale"
                    )
                    await mark_resources_stale(self.client.access_key)

            # Sleep until next poll cycle
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Stop polling loop."""
        logger.info("Stopping resource poller")
        self.running = False

    async def _poll_cycle(self) -> None:
        """
        Execute one poll cycle.

        Steps:
        1. Health check (detect MiniStack restart)
        2. Fetch all resources (S3, Lambda, DynamoDB)
        3. Detect changes (compare to last snapshot)
        4. Sync changes to FalkorDB
        5. Update last snapshot
        """
        start_time = datetime.now(UTC)
        logger.debug("Starting poll cycle")

        # Step 1: Health check
        health = await self.client.health_check()

        if not health["healthy"]:
            logger.warning(f"MiniStack unhealthy: {health['error']}")
            self.failure_count += 1

            if self.failure_count >= FAILURE_THRESHOLD:
                logger.error(
                    f"MiniStack unhealthy for {self.failure_count} consecutive cycles - "
                    "marking resources as stale"
                )
                await mark_resources_stale(self.client.access_key)

            return

        # Detect restart
        current_instance_id = health.get("instance_id")
        if (
            self.last_instance_id is not None
            and current_instance_id != self.last_instance_id
        ):
            logger.warning(
                f"MiniStack restart detected (instance ID changed: "
                f"{self.last_instance_id} → {current_instance_id}). "
                "Triggering full re-inventory..."
            )
            await self._handle_restart()

        self.last_instance_id = current_instance_id

        # Step 2: Fetch all resources
        try:
            resources = await self._fetch_all_resources()
            logger.info(f"Fetched {len(resources)} resources from MiniStack")

        except Exception as e:
            logger.error(f"Failed to fetch resources: {e}", exc_info=True)
            self.failure_count += 1

            if self.failure_count >= FAILURE_THRESHOLD:
                logger.error(
                    f"Resource fetch failed {self.failure_count} times - "
                    "marking resources as stale"
                )
                await mark_resources_stale(self.client.access_key)

            return

        # Step 3: Detect changes
        if self.last_snapshot is None:
            # First poll: all resources are new
            logger.info("First poll cycle - all resources are new")
            changes = [
                type("Change", (), {"change_type": type("ChangeType", (), {"CREATED": "CREATED"})(), "resource": r})()
                for r in resources
            ]
            # Import proper types
            from .models import Change, ChangeType
            changes = [Change(change_type=ChangeType.CREATED, resource=r) for r in resources]
        else:
            changes = detect_changes(resources, self.last_snapshot)

        # Step 4: Sync changes to FalkorDB
        try:
            await sync_changes(changes)

            # Success: clear failure count and stale markers
            if self.failure_count > 0:
                logger.info("Poll succeeded after failures - clearing stale markers")
                await clear_stale_markers(self.client.access_key)
                self.failure_count = 0

        except Exception as e:
            logger.error(f"Failed to sync changes: {e}", exc_info=True)
            self.failure_count += 1

            if self.failure_count >= FAILURE_THRESHOLD:
                logger.error(
                    f"Sync failed {self.failure_count} times - marking resources as stale"
                )
                await mark_resources_stale(self.client.access_key)

            return

        # Step 4.5: Sync dependencies
        try:
            from ..dependencies.manager import sync_all_dependencies

            # Convert Resource objects to dicts for dependency detection
            resources_dicts = [r.to_dict() for r in resources]
            dep_stats = await sync_all_dependencies(resources_dicts, self.client)
            logger.debug(
                f"Dependency sync: {dep_stats['dependencies_created']} created, "
                f"{dep_stats['dependencies_deleted']} deleted"
            )
        except Exception as e:
            # Don't fail the entire poll cycle if dependency sync fails
            logger.error(f"Dependency sync failed: {e}", exc_info=True)

        # Step 5: Update last snapshot
        self.last_snapshot = Snapshot(resources=resources)

        duration = (datetime.now(UTC) - start_time).total_seconds()
        logger.info(f"Poll cycle complete ({duration:.2f}s)")

    async def _fetch_all_resources(self) -> List[Resource]:
        """
        Fetch all resources from MiniStack API.

        Returns:
            List of Resource objects

        Raises:
            Exception: If any service fetch fails
        """
        # Fetch all services in parallel
        results = await asyncio.gather(
            self.client.get_s3_buckets(),
            self.client.get_lambda_functions(),
            self.client.get_dynamodb_tables(),
            return_exceptions=True,
        )

        resources = []

        # Process S3 buckets
        if isinstance(results[0], Exception):
            logger.error(f"Failed to fetch S3 buckets: {results[0]}")
        else:
            for bucket_dict in results[0]:
                resources.append(self._dict_to_resource(bucket_dict))

        # Process Lambda functions
        if isinstance(results[1], Exception):
            logger.error(f"Failed to fetch Lambda functions: {results[1]}")
        else:
            for func_dict in results[1]:
                resources.append(self._dict_to_resource(func_dict))

        # Process DynamoDB tables
        if isinstance(results[2], Exception):
            logger.error(f"Failed to fetch DynamoDB tables: {results[2]}")
        else:
            for table_dict in results[2]:
                resources.append(self._dict_to_resource(table_dict))

        return resources

    def _dict_to_resource(self, data: Dict[str, Any]) -> Resource:
        """Convert dict from MiniStack client to Resource object."""
        return Resource(
            id=data["id"],
            type=data["type"],
            name=data["name"],
            tenant_id=data["tenant_id"],
            arn=data["arn"],
            state=data["state"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    async def _handle_restart(self) -> None:
        """
        Handle MiniStack restart.

        Performs full re-inventory and clears stale markers.
        """
        logger.info("Handling MiniStack restart: full re-inventory")

        # Reset state
        self.last_snapshot = None
        self.failure_count = 0

        # Clear stale markers
        try:
            await clear_stale_markers(self.client.access_key)
        except Exception as e:
            logger.error(f"Failed to clear stale markers after restart: {e}")

        logger.info("Restart handling complete")


async def main():
    """Main entry point for standalone poller."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    poller = ResourcePoller()

    try:
        await poller.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        await poller.stop()


if __name__ == "__main__":
    asyncio.run(main())
