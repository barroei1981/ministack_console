"""
Unit tests for change detection algorithm.

Tests:
- Detect CREATED resources
- Detect DELETED resources
- Detect UPDATED resources
- No changes scenario
- Empty snapshots
- Mixed changes
"""

import pytest
from datetime import datetime, UTC

from control_plane.inventory.models import Resource, Snapshot, ChangeType
from control_plane.inventory.detector import detect_changes


def create_test_resource(
    resource_id: str,
    resource_type: str = "s3:bucket",
    name: str = None,
    tenant_id: str = "123456789012",
    state: dict = None,
) -> Resource:
    """Helper to create test resource."""
    return Resource(
        id=resource_id,
        type=resource_type,
        name=name or resource_id,
        tenant_id=tenant_id,
        arn=f"arn:aws:{resource_type}:::{resource_id}",
        state=state or {},
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )


def test_detect_created_resources():
    """Test detecting newly created resources."""
    # Previous snapshot: empty
    previous = Snapshot(resources=[])

    # Current: 2 resources
    current = [
        create_test_resource("bucket-1"),
        create_test_resource("bucket-2"),
    ]

    changes = detect_changes(current, previous)

    assert len(changes) == 2
    assert all(c.change_type == ChangeType.CREATED for c in changes)
    assert {c.resource.id for c in changes} == {"bucket-1", "bucket-2"}


def test_detect_deleted_resources():
    """Test detecting deleted resources."""
    # Previous snapshot: 2 resources
    previous = Snapshot(
        resources=[
            create_test_resource("bucket-1"),
            create_test_resource("bucket-2"),
        ]
    )

    # Current: empty
    current = []

    changes = detect_changes(current, previous)

    assert len(changes) == 2
    assert all(c.change_type == ChangeType.DELETED for c in changes)
    assert {c.resource_id for c in changes} == {"bucket-1", "bucket-2"}


def test_detect_updated_resources():
    """Test detecting updated resources."""
    # Previous snapshot
    previous = Snapshot(
        resources=[
            create_test_resource("bucket-1", state={"versioning": False}),
            create_test_resource("bucket-2", state={"versioning": False}),
        ]
    )

    # Current: bucket-1 updated, bucket-2 unchanged
    current = [
        create_test_resource("bucket-1", state={"versioning": True}),  # UPDATED
        create_test_resource("bucket-2", state={"versioning": False}),  # No change
    ]

    changes = detect_changes(current, previous)

    # Only bucket-1 should be detected as updated
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.UPDATED
    assert changes[0].resource.id == "bucket-1"
    assert changes[0].resource.state["versioning"] is True


def test_no_changes():
    """Test no changes detected when resources are identical."""
    resource = create_test_resource("bucket-1", state={"key": "value"})

    previous = Snapshot(resources=[resource])
    current = [resource]

    changes = detect_changes(current, previous)

    assert len(changes) == 0


def test_mixed_changes():
    """Test detecting mixed CREATED/UPDATED/DELETED changes."""
    # Previous snapshot: 3 resources
    previous = Snapshot(
        resources=[
            create_test_resource("bucket-1", state={"tag": "old"}),  # Will be updated
            create_test_resource("bucket-2"),  # Will be deleted
            create_test_resource("bucket-3"),  # Unchanged
        ]
    )

    # Current: 3 resources (1 updated, 1 deleted, 1 new, 1 unchanged)
    current = [
        create_test_resource("bucket-1", state={"tag": "new"}),  # UPDATED
        create_test_resource("bucket-3"),  # Unchanged
        create_test_resource("bucket-4"),  # CREATED
    ]

    changes = detect_changes(current, previous)

    # Should detect: 1 CREATED, 1 UPDATED, 1 DELETED
    assert len(changes) == 3

    created = [c for c in changes if c.change_type == ChangeType.CREATED]
    updated = [c for c in changes if c.change_type == ChangeType.UPDATED]
    deleted = [c for c in changes if c.change_type == ChangeType.DELETED]

    assert len(created) == 1
    assert created[0].resource.id == "bucket-4"

    assert len(updated) == 1
    assert updated[0].resource.id == "bucket-1"
    assert updated[0].resource.state["tag"] == "new"

    assert len(deleted) == 1
    assert deleted[0].resource_id == "bucket-2"


def test_empty_current_and_previous():
    """Test with both empty current and previous snapshots."""
    previous = Snapshot(resources=[])
    current = []

    changes = detect_changes(current, previous)

    assert len(changes) == 0


def test_updated_resource_different_timestamps():
    """Test that different timestamps alone don't trigger UPDATED."""
    # Resource with same properties but different updated_at timestamp
    resource_old = create_test_resource("bucket-1", state={"key": "value"})

    # Simulate time passing
    import time

    time.sleep(0.01)

    resource_new = create_test_resource("bucket-1", state={"key": "value"})
    # Note: created_at and updated_at will be different due to time.sleep

    previous = Snapshot(resources=[resource_old])
    current = [resource_new]

    changes = detect_changes(current, previous)

    # Timestamps differ but state is same - should NOT detect as UPDATED
    # because Resource.__eq__ doesn't compare timestamps (intentionally)
    # Timestamps changing is expected during normal polling
    assert len(changes) == 0


def test_multiple_resource_types():
    """Test change detection across different resource types."""
    previous = Snapshot(
        resources=[
            create_test_resource("bucket-1", resource_type="s3:bucket"),
            create_test_resource("func-1", resource_type="lambda:function"),
        ]
    )

    current = [
        create_test_resource("bucket-1", resource_type="s3:bucket"),  # Unchanged
        create_test_resource("func-2", resource_type="lambda:function"),  # New
        create_test_resource("table-1", resource_type="dynamodb:table"),  # New
    ]

    changes = detect_changes(current, previous)

    created = [c for c in changes if c.change_type == ChangeType.CREATED]
    deleted = [c for c in changes if c.change_type == ChangeType.DELETED]

    assert len(created) == 2
    assert {c.resource.id for c in created} == {"func-2", "table-1"}

    assert len(deleted) == 1
    assert deleted[0].resource_id == "func-1"
