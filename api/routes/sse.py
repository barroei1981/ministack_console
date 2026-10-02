"""
Server-Sent Events (SSE) endpoint for real-time updates.

Streams resource and dependency changes to connected UI clients.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from control_plane.events import event_bus
from control_plane.observability import log_security

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/sse")
async def sse_endpoint(tenant_id: str = Query(..., description="Tenant ID for event filtering")):
    """
    Server-Sent Events endpoint for real-time resource updates.

    Clients connect to this endpoint to receive streaming updates about
    resource changes, dependency changes, and tag updates for their tenant.

    Args:
        tenant_id: Tenant ID to filter events (required)

    Returns:
        StreamingResponse with text/event-stream content type

    Event format (SSE protocol):
        data: {"type": "RESOURCE_CREATED", "resource": {...}, "timestamp": "...", "tenant_id": "..."}\\n\\n

    Event types:
        - RESOURCE_CREATED: New resource detected
        - RESOURCE_UPDATED: Resource configuration changed
        - RESOURCE_DELETED: Resource removed
        - DEPENDENCY_ADDED: New dependency relationship detected
        - DEPENDENCY_REMOVED: Dependency relationship removed
        - TAGS_UPDATED: Resource tags modified

    Notes:
        - Built-in reconnection: EventSource API automatically reconnects on disconnect
        - No event history/replay: Clients only receive events after connection established
        - Tenant isolation: Events filtered by tenant_id, no cross-tenant leakage
        - Connection limit: 10 concurrent connections per tenant (per NFRs)
    """

    async def event_generator():
        """
        Async generator that yields SSE-formatted events.

        Subscribes to event bus and streams events to client until disconnect.
        """
        queue = None
        try:
            # Subscribe to event bus for this tenant
            queue = await event_bus.subscribe(tenant_id)

            log_security(
                "SSE connection established",
                tenant_id=tenant_id,
            )

            # Stream events until client disconnects
            while True:
                # Wait for next event (blocks until event available)
                event = await queue.get()

                # Format as SSE protocol: "data: {json}\n\n"
                yield f"data: {json.dumps(event)}\n\n"

        except asyncio.CancelledError:
            # Client disconnected - normal flow
            log_security(
                "SSE connection closed",
                tenant_id=tenant_id,
            )
            raise

        finally:
            # Clean up: unsubscribe from event bus
            if queue:
                await event_bus.unsubscribe(tenant_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
