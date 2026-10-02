"""
Unit tests for EventBus.

Tests subscribe/publish, multiple subscribers, unsubscribe cleanup, tenant isolation.
"""

import asyncio

import pytest

from control_plane.events.bus import EventBus


@pytest.mark.asyncio
async def test_subscribe_creates_queue():
    """Test that subscribe creates a new queue for a tenant."""
    bus = EventBus()
    queue = await bus.subscribe("tenant-1")

    assert queue is not None
    assert isinstance(queue, asyncio.Queue)


@pytest.mark.asyncio
async def test_publish_to_single_subscriber():
    """Test publishing event to a single subscriber."""
    bus = EventBus()
    queue = await bus.subscribe("tenant-1")

    # Publish event
    await bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "res-1", "type": "s3:bucket"},
        tenant_id="tenant-1",
    )

    # Subscriber should receive the event
    event = await asyncio.wait_for(queue.get(), timeout=1.0)

    assert event["type"] == "RESOURCE_CREATED"
    assert event["resource"]["id"] == "res-1"
    assert event["tenant_id"] == "tenant-1"
    assert "timestamp" in event


@pytest.mark.asyncio
async def test_publish_to_multiple_subscribers():
    """Test publishing event to multiple subscribers for same tenant."""
    bus = EventBus()
    queue1 = await bus.subscribe("tenant-1")
    queue2 = await bus.subscribe("tenant-1")
    queue3 = await bus.subscribe("tenant-1")

    # Publish event
    await bus.publish(
        event_type="RESOURCE_UPDATED",
        resource={"id": "res-2", "type": "lambda:function"},
        tenant_id="tenant-1",
    )

    # All subscribers should receive the event
    event1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
    event2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
    event3 = await asyncio.wait_for(queue3.get(), timeout=1.0)

    assert event1["type"] == "RESOURCE_UPDATED"
    assert event2["type"] == "RESOURCE_UPDATED"
    assert event3["type"] == "RESOURCE_UPDATED"


@pytest.mark.asyncio
async def test_tenant_isolation():
    """Test that events are only sent to subscribers of the same tenant."""
    bus = EventBus()
    queue1 = await bus.subscribe("tenant-1")
    queue2 = await bus.subscribe("tenant-2")

    # Publish event to tenant-1
    await bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "res-1"},
        tenant_id="tenant-1",
    )

    # Only tenant-1 subscriber should receive event
    event1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
    assert event1["tenant_id"] == "tenant-1"

    # tenant-2 subscriber should not receive event (queue should be empty)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue2.get(), timeout=0.1)


@pytest.mark.asyncio
async def test_unsubscribe_removes_queue():
    """Test that unsubscribe removes queue from subscribers."""
    bus = EventBus()
    queue = await bus.subscribe("tenant-1")

    # Unsubscribe
    await bus.unsubscribe("tenant-1", queue)

    # Publish event - subscriber should not receive it
    await bus.publish(
        event_type="RESOURCE_DELETED",
        resource={"id": "res-3"},
        tenant_id="tenant-1",
    )

    # Queue should be empty (no event received after unsubscribe)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.1)


@pytest.mark.asyncio
async def test_publish_with_no_subscribers():
    """Test that publish with no subscribers doesn't error (silent discard)."""
    bus = EventBus()

    # Publish without any subscribers - should not raise error
    await bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "res-4"},
        tenant_id="tenant-1",
    )


@pytest.mark.asyncio
async def test_queue_full_drops_event():
    """Test that events are dropped when queue is full (fire-and-forget)."""
    bus = EventBus()
    queue = await bus.subscribe("tenant-1")

    # Fill queue to capacity (100 events per EventBus implementation)
    for i in range(100):
        await bus.publish(
            event_type="RESOURCE_CREATED",
            resource={"id": f"res-{i}"},
            tenant_id="tenant-1",
        )

    # Queue should be full now - next event should be dropped
    await bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "res-dropped"},
        tenant_id="tenant-1",
    )

    # Drain queue and verify last event was dropped
    received_ids = []
    for _ in range(100):
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        received_ids.append(event["resource"]["id"])

    # Should not contain the dropped event
    assert "res-dropped" not in received_ids


@pytest.mark.asyncio
async def test_multiple_tenants_concurrent():
    """Test concurrent subscribers across multiple tenants."""
    bus = EventBus()

    # Subscribe 2 clients per tenant
    tenant1_q1 = await bus.subscribe("tenant-1")
    tenant1_q2 = await bus.subscribe("tenant-1")
    tenant2_q1 = await bus.subscribe("tenant-2")
    tenant2_q2 = await bus.subscribe("tenant-2")

    # Publish events to both tenants
    await bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "t1-res"},
        tenant_id="tenant-1",
    )
    await bus.publish(
        event_type="RESOURCE_CREATED",
        resource={"id": "t2-res"},
        tenant_id="tenant-2",
    )

    # Verify tenant-1 subscribers only received tenant-1 event
    t1_event1 = await asyncio.wait_for(tenant1_q1.get(), timeout=1.0)
    t1_event2 = await asyncio.wait_for(tenant1_q2.get(), timeout=1.0)
    assert t1_event1["resource"]["id"] == "t1-res"
    assert t1_event2["resource"]["id"] == "t1-res"

    # Verify tenant-2 subscribers only received tenant-2 event
    t2_event1 = await asyncio.wait_for(tenant2_q1.get(), timeout=1.0)
    t2_event2 = await asyncio.wait_for(tenant2_q2.get(), timeout=1.0)
    assert t2_event1["resource"]["id"] == "t2-res"
    assert t2_event2["resource"]["id"] == "t2-res"


@pytest.mark.asyncio
async def test_dependency_events():
    """Test publishing DEPENDENCY_ADDED and DEPENDENCY_REMOVED events."""
    bus = EventBus()
    queue = await bus.subscribe("tenant-1")

    # Publish dependency added event
    await bus.publish(
        event_type="DEPENDENCY_ADDED",
        resource={
            "source_id": "lambda-1",
            "target_id": "s3-bucket-1",
            "type": "ENVIRONMENT_VARIABLE",
            "metadata": {"variable": "BUCKET_NAME"},
        },
        tenant_id="tenant-1",
    )

    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["type"] == "DEPENDENCY_ADDED"
    assert event["resource"]["source_id"] == "lambda-1"
    assert event["resource"]["target_id"] == "s3-bucket-1"


@pytest.mark.asyncio
async def test_unsubscribe_idempotent():
    """Test that unsubscribe is idempotent (can be called multiple times)."""
    bus = EventBus()
    queue = await bus.subscribe("tenant-1")

    # Unsubscribe twice - should not error
    await bus.unsubscribe("tenant-1", queue)
    await bus.unsubscribe("tenant-1", queue)
