"""
Event bus for Server-Sent Events system.

In-memory pub/sub using asyncio.Queue for tenant-scoped event distribution.
"""

import asyncio
import logging
from typing import Any

from .models import Event

logger = logging.getLogger(__name__)


class EventBus:
    """
    In-memory event bus for real-time notifications.

    Maintains per-tenant subscriber queues and publishes events to all
    active subscribers for the relevant tenant.

    Thread-safe via asyncio primitives.
    """

    def __init__(self):
        """Initialize event bus with empty subscriber registry."""
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, tenant_id: str) -> asyncio.Queue:
        """
        Subscribe to events for a tenant.

        Creates a new queue and registers it for the tenant.
        The caller is responsible for consuming events from the queue.

        Args:
            tenant_id: Tenant ID to subscribe to

        Returns:
            asyncio.Queue that will receive events
        """
        async with self._lock:
            queue = asyncio.Queue(maxsize=100)  # Buffer up to 100 events

            if tenant_id not in self._subscribers:
                self._subscribers[tenant_id] = []

            self._subscribers[tenant_id].append(queue)

            logger.info(
                f"[OPERATIONAL] SSE subscriber added for tenant {tenant_id} "
                f"(total: {len(self._subscribers[tenant_id])})"
            )

            return queue

    async def unsubscribe(self, tenant_id: str, queue: asyncio.Queue) -> None:
        """
        Unsubscribe from events for a tenant.

        Removes the queue from the subscriber registry and closes it.

        Args:
            tenant_id: Tenant ID to unsubscribe from
            queue: Queue to remove
        """
        async with self._lock:
            if tenant_id in self._subscribers:
                try:
                    self._subscribers[tenant_id].remove(queue)

                    # Clean up empty tenant lists
                    if not self._subscribers[tenant_id]:
                        del self._subscribers[tenant_id]

                    logger.info(
                        f"[OPERATIONAL] SSE subscriber removed for tenant {tenant_id} "
                        f"(remaining: {len(self._subscribers.get(tenant_id, []))})"
                    )
                except ValueError:
                    # Queue already removed, ignore
                    pass

    async def publish(
        self, event_type: str, resource: dict[str, Any], tenant_id: str
    ) -> None:
        """
        Publish event to all subscribers for a tenant.

        Enqueues event to all active queues for the tenant. If a queue is full,
        the event is dropped for that subscriber (fire-and-forget semantics).

        Args:
            event_type: Event type (from EventType enum)
            resource: Resource data or dependency info
            tenant_id: Tenant ID for event routing
        """
        # No subscribers for this tenant - silently discard
        if tenant_id not in self._subscribers:
            return

        event = Event(
            type=event_type,
            resource=resource,
            tenant_id=tenant_id,
        )

        # Publish to all subscribers for this tenant
        async with self._lock:
            subscribers = self._subscribers.get(tenant_id, [])

            for queue in subscribers:
                try:
                    # Non-blocking put - drop event if queue is full
                    queue.put_nowait(event.to_dict())
                except asyncio.QueueFull:
                    logger.warning(
                        f"[OPERATIONAL] Event queue full for tenant {tenant_id}, dropping event"
                    )

        logger.debug(
            f"[OPERATIONAL] Published {event_type} event to {len(subscribers)} subscribers for tenant {tenant_id}"
        )
