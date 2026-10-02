"""
Integration tests for SSE endpoint.

Tests SSE endpoint streaming, reconnection, concurrent connections.

Note: These tests verify the EventBus → SSE pipeline. Full end-to-end SSE streaming
tests are challenging in pytest due to infinite stream blocking. The unit tests in
test_event_bus.py provide comprehensive coverage of the event bus logic.
"""

import asyncio
import json

import pytest

from control_plane.events import event_bus

# Mark as integration test
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_event_bus_integration_with_sse():
    """
    Integration test: EventBus publishes events that would be streamed via SSE.

    This tests the pub/sub mechanism that SSE endpoint relies on.
    Full HTTP streaming tests require a running server and real browser EventSource client.
    """
    tenant_id = "123456789012"

    # Subscribe (simulates SSE endpoint subscribing)
    queue = await event_bus.subscribe(tenant_id)

    # Publish various event types (simulates sync.py and manager.py emitting events)
    await event_bus.publish(
        event_type="RESOURCE_CREATED",
        resource={
            "id": "arn:aws:s3:::test-bucket",
            "type": "s3:bucket",
            "name": "test-bucket",
            "tenant_id": tenant_id,
        },
        tenant_id=tenant_id,
    )

    await event_bus.publish(
        event_type="RESOURCE_UPDATED",
        resource={
            "id": "arn:aws:lambda:us-east-1:123456789012:function:my-func",
            "type": "lambda:function",
            "name": "my-func",
        },
        tenant_id=tenant_id,
    )

    await event_bus.publish(
        event_type="DEPENDENCY_ADDED",
        resource={
            "source_id": "arn:aws:lambda:::function:my-func",
            "target_id": "arn:aws:s3:::my-bucket",
            "type": "ENVIRONMENT_VARIABLE",
        },
        tenant_id=tenant_id,
    )

    # Verify all events received in order
    event1 = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event1["type"] == "RESOURCE_CREATED"
    assert event1["resource"]["type"] == "s3:bucket"

    event2 = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event2["type"] == "RESOURCE_UPDATED"
    assert event2["resource"]["type"] == "lambda:function"

    event3 = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event3["type"] == "DEPENDENCY_ADDED"
    assert "source_id" in event3["resource"]

    # Clean up
    await event_bus.unsubscribe(tenant_id, queue)


@pytest.mark.asyncio
async def test_event_format_matches_sse_spec():
    """
    Verify event format matches SSE protocol requirements.

    Events must have: type, resource, timestamp, tenant_id.
    This is what the SSE endpoint will serialize as "data: {json}\\n\\n".
    """
    tenant_id = "123456789012"
    queue = await event_bus.subscribe(tenant_id)

    await event_bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "test-resource", "type": "s3:bucket"},
        tenant_id=tenant_id,
    )

    event = await asyncio.wait_for(queue.get(), timeout=1.0)

    # Verify all required fields present
    assert "type" in event
    assert "resource" in event
    assert "timestamp" in event
    assert "tenant_id" in event

    # Verify event can be JSON serialized (SSE endpoint does this)
    json_str = json.dumps(event)
    assert json_str is not None

    # Verify deserialization works
    deserialized = json.loads(json_str)
    assert deserialized["type"] == "RESOURCE_CREATED"

    await event_bus.unsubscribe(tenant_id, queue)


@pytest.mark.asyncio
async def test_multiple_subscribers_concurrent():
    """
    Test that multiple SSE connections (subscribers) receive events concurrently.

    Simulates 10 concurrent SSE connections per spec's NFR.
    """
    tenant_id = "123456789012"
    num_subscribers = 10

    # Create 10 subscribers (simulates 10 open SSE connections)
    queues = []
    for _ in range(num_subscribers):
        queue = await event_bus.subscribe(tenant_id)
        queues.append(queue)

    # Publish event
    await event_bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "shared-resource"},
        tenant_id=tenant_id,
    )

    # All 10 subscribers should receive the event
    for i, queue in enumerate(queues):
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event["type"] == "RESOURCE_CREATED"
        assert event["resource"]["id"] == "shared-resource"

    # Clean up
    for queue in queues:
        await event_bus.unsubscribe(tenant_id, queue)


@pytest.mark.asyncio
async def test_tenant_isolation_integration():
    """
    Integration test for tenant isolation in event bus.

    Verifies that events are only routed to subscribers of the same tenant.
    """
    tenant1 = "111111111111"
    tenant2 = "222222222222"

    queue1 = await event_bus.subscribe(tenant1)
    queue2 = await event_bus.subscribe(tenant2)

    # Publish event to tenant1
    await event_bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "tenant1-resource"},
        tenant_id=tenant1,
    )

    # Only tenant1's queue should receive event
    event = await asyncio.wait_for(queue1.get(), timeout=1.0)
    assert event["tenant_id"] == tenant1

    # tenant2's queue should be empty
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue2.get(), timeout=0.1)

    # Clean up
    await event_bus.unsubscribe(tenant1, queue1)
    await event_bus.unsubscribe(tenant2, queue2)


@pytest.mark.asyncio
async def test_reconnection_scenario():
    """
    Test reconnection scenario: unsubscribe, then resubscribe.

    Simulates SSE client disconnecting and reconnecting.
    Per spec: no event replay, new subscription starts fresh.
    """
    tenant_id = "123456789012"

    # First connection
    queue1 = await event_bus.subscribe(tenant_id)

    await event_bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "resource-1"},
        tenant_id=tenant_id,
    )

    event1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
    assert event1["resource"]["id"] == "resource-1"

    # Disconnect
    await event_bus.unsubscribe(tenant_id, queue1)

    # Publish event while disconnected (should be lost)
    await event_bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "resource-missed"},
        tenant_id=tenant_id,
    )

    # Reconnect
    queue2 = await event_bus.subscribe(tenant_id)

    # Publish new event after reconnection
    await event_bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "resource-2"},
        tenant_id=tenant_id,
    )

    # Should only receive new event (missed event not replayed)
    event2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
    assert event2["resource"]["id"] == "resource-2"

    # No more events in queue
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue2.get(), timeout=0.1)

    await event_bus.unsubscribe(tenant_id, queue2)
