"""
Unit tests for sync layer.

Tests:
- Sync CREATED change
- Sync UPDATED change
- Sync DELETED change
- Mark resources as stale
- Clear stale markers
- Error handling
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, UTC

from control_plane.inventory.models import Resource, Change, ChangeType
from control_plane.inventory.sync import (
    sync_changes,
    mark_resources_stale,
    clear_stale_markers,
)


def create_test_resource(
    resource_id: str,
    resource_type: str = "s3:bucket",
    name: str = None,
    state: dict = None,
) -> Resource:
    """Helper to create test resource."""
    return Resource(
        id=resource_id,
        type=resource_type,
        name=name or resource_id,
        tenant_id="123456789012",
        arn=f"arn:aws:{resource_type}:::{resource_id}",
        state=state or {},
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )


@pytest.mark.asyncio
async def test_sync_created_change():
    """Test syncing CREATED change calls create_node."""
    resource = create_test_resource("bucket-1", state={"key": "value"})
    change = Change(change_type=ChangeType.CREATED, resource=resource)

    with patch("control_plane.inventory.sync.create_node") as mock_create:
        await sync_changes([change])

        # Verify create_node was called
        assert mock_create.call_count == 1

        call_args = mock_create.call_args
        assert call_args[1]["label"] == "Resource"

        properties = call_args[1]["properties"]
        assert properties["id"] == "bucket-1"
        assert properties["type"] == "s3:bucket"
        assert properties["tenant_id"] == "123456789012"

        # State should be JSON string
        assert isinstance(properties["state"], str)
        assert json.loads(properties["state"]) == {"key": "value"}


@pytest.mark.asyncio
async def test_sync_updated_change():
    """Test syncing UPDATED change calls delete_node then create_node."""
    resource = create_test_resource("bucket-1", state={"key": "new_value"})
    change = Change(change_type=ChangeType.UPDATED, resource=resource)

    with patch("control_plane.inventory.sync.delete_node") as mock_delete, patch(
        "control_plane.inventory.sync.create_node"
    ) as mock_create:
        await sync_changes([change])

        # Verify delete_node was called first
        assert mock_delete.call_count == 1
        assert mock_delete.call_args[1]["label"] == "Resource"
        assert mock_delete.call_args[1]["node_id"] == "bucket-1"

        # Verify create_node was called second
        assert mock_create.call_count == 1
        properties = mock_create.call_args[1]["properties"]
        assert properties["id"] == "bucket-1"
        assert json.loads(properties["state"]) == {"key": "new_value"}


@pytest.mark.asyncio
async def test_sync_deleted_change():
    """Test syncing DELETED change calls delete_node."""
    change = Change(change_type=ChangeType.DELETED, resource_id="bucket-1")

    with patch("control_plane.inventory.sync.delete_node") as mock_delete:
        mock_delete.return_value = True

        await sync_changes([change])

        # Verify delete_node was called
        assert mock_delete.call_count == 1
        assert mock_delete.call_args[1]["label"] == "Resource"
        assert mock_delete.call_args[1]["node_id"] == "bucket-1"


@pytest.mark.asyncio
async def test_sync_multiple_changes():
    """Test syncing multiple changes of different types."""
    changes = [
        Change(change_type=ChangeType.CREATED, resource=create_test_resource("new-1")),
        Change(
            change_type=ChangeType.UPDATED, resource=create_test_resource("updated-1")
        ),
        Change(change_type=ChangeType.DELETED, resource_id="deleted-1"),
    ]

    with patch("control_plane.inventory.sync.create_node") as mock_create, patch(
        "control_plane.inventory.sync.delete_node"
    ) as mock_delete:
        mock_delete.return_value = True

        await sync_changes(changes)

        # Verify correct number of calls
        assert mock_create.call_count == 2  # 1 CREATED + 1 UPDATED
        assert mock_delete.call_count == 2  # 1 UPDATED + 1 DELETED


@pytest.mark.asyncio
async def test_sync_no_changes():
    """Test syncing empty changes list."""
    with patch("control_plane.inventory.sync.create_node") as mock_create, patch(
        "control_plane.inventory.sync.delete_node"
    ) as mock_delete:
        await sync_changes([])

        # No graph operations should be called
        assert mock_create.call_count == 0
        assert mock_delete.call_count == 0


@pytest.mark.asyncio
async def test_sync_change_error_continues():
    """Test that sync continues after individual change error."""
    changes = [
        Change(change_type=ChangeType.CREATED, resource=create_test_resource("good-1")),
        Change(
            change_type=ChangeType.CREATED, resource=create_test_resource("bad-1")
        ),  # Will fail
        Change(change_type=ChangeType.CREATED, resource=create_test_resource("good-2")),
    ]

    call_count = 0

    def mock_create_with_error(label, properties):
        nonlocal call_count
        call_count += 1
        if properties["id"] == "bad-1":
            raise Exception("Simulated error")

    with patch(
        "control_plane.inventory.sync.create_node", side_effect=mock_create_with_error
    ):
        # Should not raise exception - errors are logged and sync continues
        await sync_changes(changes)

        # All changes should be attempted
        assert call_count == 3


@pytest.mark.asyncio
async def test_mark_resources_stale():
    """Test marking resources as stale."""
    mock_graph = MagicMock()
    mock_result = MagicMock()
    mock_result.result_set = [[5]]  # 5 resources marked stale
    mock_graph.query.return_value = mock_result

    with patch("control_plane.inventory.sync.get_graph", return_value=mock_graph):
        await mark_resources_stale("123456789012")

        # Verify query was called with tenant_id
        assert mock_graph.query.call_count == 1
        call_args = mock_graph.query.call_args

        # Check query sets stale = true
        assert "stale" in call_args[0][0].lower()
        assert call_args[1]["params"]["tenant_id"] == "123456789012"


@pytest.mark.asyncio
async def test_clear_stale_markers():
    """Test clearing stale markers."""
    mock_graph = MagicMock()
    mock_result = MagicMock()
    mock_result.result_set = [[3]]  # 3 stale markers cleared
    mock_graph.query.return_value = mock_result

    with patch("control_plane.inventory.sync.get_graph", return_value=mock_graph):
        await clear_stale_markers("123456789012")

        # Verify query was called with tenant_id
        assert mock_graph.query.call_count == 1
        call_args = mock_graph.query.call_args

        # Check query removes stale property
        assert "remove" in call_args[0][0].lower()
        assert call_args[1]["params"]["tenant_id"] == "123456789012"
