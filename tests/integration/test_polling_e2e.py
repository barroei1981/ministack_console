"""
End-to-end integration test for polling system.

Tests the full flow:
1. Poller starts
2. Fetches resources from MiniStack (mocked)
3. Detects changes
4. Syncs to FalkorDB
5. Verifies resources appear in FalkorDB

Requires FalkorDB to be running for integration.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from control_plane.inventory.poller import ResourcePoller
from control_plane.graph.query import query_nodes, reset_graph, get_graph
from control_plane.graph.schema import initialize_schema


@pytest.fixture(scope="module")
def graph():
    """Provide FalkorDB graph instance with initialized schema."""
    try:
        g = get_graph()
        initialize_schema(g)
        yield g
    finally:
        reset_graph()


@pytest.fixture(autouse=True)
def reset_before_test(graph):
    """Reset graph before each test."""
    reset_graph()
    initialize_schema(graph)
    yield


@pytest.fixture
def mock_ministack_client():
    """Create mock MiniStack client with test data."""
    client = MagicMock()

    # Mock health check
    client.health_check = AsyncMock(
        return_value={
            "healthy": True,
            "instance_id": "test-instance-123",
            "error": None,
        }
    )

    # Mock S3 buckets
    client.get_s3_buckets = AsyncMock(
        return_value=[
            {
                "id": "arn:aws:s3:::test-bucket-1",
                "type": "s3:bucket",
                "name": "test-bucket-1",
                "tenant_id": "123456789012",
                "arn": "arn:aws:s3:::test-bucket-1",
                "state": {"creation_date": "2026-10-01T00:00:00Z"},
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            },
            {
                "id": "arn:aws:s3:::test-bucket-2",
                "type": "s3:bucket",
                "name": "test-bucket-2",
                "tenant_id": "123456789012",
                "arn": "arn:aws:s3:::test-bucket-2",
                "state": {"creation_date": "2026-10-01T00:00:00Z"},
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            },
        ]
    )

    # Mock Lambda functions
    client.get_lambda_functions = AsyncMock(
        return_value=[
            {
                "id": "arn:aws:lambda:us-east-1:123456789012:function:test-func",
                "type": "lambda:function",
                "name": "test-func",
                "tenant_id": "123456789012",
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:test-func",
                "state": {"runtime": "python3.11"},
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            }
        ]
    )

    # Mock DynamoDB tables
    client.get_dynamodb_tables = AsyncMock(
        return_value=[
            {
                "id": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
                "type": "dynamodb:table",
                "name": "test-table",
                "tenant_id": "123456789012",
                "arn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
                "state": {"status": "ACTIVE"},
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            }
        ]
    )

    client.access_key = "123456789012"

    return client


@pytest.mark.asyncio
async def test_first_poll_creates_resources(graph, mock_ministack_client):
    """Test that first poll cycle creates all resources in FalkorDB."""
    poller = ResourcePoller(client=mock_ministack_client)

    # Run one poll cycle
    await poller._poll_cycle()

    # Verify resources were created in FalkorDB
    all_resources = query_nodes(label="Resource")

    assert len(all_resources) == 4  # 2 buckets + 1 function + 1 table

    # Verify S3 buckets
    s3_resources = query_nodes(label="Resource", filters={"type": "s3:bucket"})
    assert len(s3_resources) == 2
    assert {r["name"] for r in s3_resources} == {"test-bucket-1", "test-bucket-2"}

    # Verify Lambda functions
    lambda_resources = query_nodes(label="Resource", filters={"type": "lambda:function"})
    assert len(lambda_resources) == 1
    assert lambda_resources[0]["name"] == "test-func"

    # Verify DynamoDB tables
    dynamodb_resources = query_nodes(
        label="Resource", filters={"type": "dynamodb:table"}
    )
    assert len(dynamodb_resources) == 1
    assert dynamodb_resources[0]["name"] == "test-table"


@pytest.mark.asyncio
async def test_second_poll_detects_new_resource(graph, mock_ministack_client):
    """Test that second poll cycle detects new resources."""
    poller = ResourcePoller(client=mock_ministack_client)

    # First poll
    await poller._poll_cycle()

    initial_count = len(query_nodes(label="Resource"))
    assert initial_count == 4

    # Add new bucket to mock
    mock_ministack_client.get_s3_buckets = AsyncMock(
        return_value=[
            {
                "id": "arn:aws:s3:::test-bucket-1",
                "type": "s3:bucket",
                "name": "test-bucket-1",
                "tenant_id": "123456789012",
                "arn": "arn:aws:s3:::test-bucket-1",
                "state": {"creation_date": "2026-10-01T00:00:00Z"},
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            },
            {
                "id": "arn:aws:s3:::test-bucket-2",
                "type": "s3:bucket",
                "name": "test-bucket-2",
                "tenant_id": "123456789012",
                "arn": "arn:aws:s3:::test-bucket-2",
                "state": {"creation_date": "2026-10-01T00:00:00Z"},
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            },
            {
                "id": "arn:aws:s3:::test-bucket-3",
                "type": "s3:bucket",
                "name": "test-bucket-3",
                "tenant_id": "123456789012",
                "arn": "arn:aws:s3:::test-bucket-3",
                "state": {"creation_date": "2026-10-02T00:00:00Z"},
                "created_at": "2026-10-02T00:00:00Z",
                "updated_at": "2026-10-02T00:00:00Z",
            },
        ]
    )

    # Second poll
    await poller._poll_cycle()

    # Verify new bucket was added
    all_resources = query_nodes(label="Resource")
    assert len(all_resources) == 5

    s3_resources = query_nodes(label="Resource", filters={"type": "s3:bucket"})
    assert len(s3_resources) == 3
    assert "test-bucket-3" in {r["name"] for r in s3_resources}


@pytest.mark.asyncio
async def test_poll_detects_deleted_resource(graph, mock_ministack_client):
    """Test that poll cycle detects deleted resources."""
    poller = ResourcePoller(client=mock_ministack_client)

    # First poll
    await poller._poll_cycle()

    assert len(query_nodes(label="Resource")) == 4

    # Remove bucket from mock
    mock_ministack_client.get_s3_buckets = AsyncMock(
        return_value=[
            {
                "id": "arn:aws:s3:::test-bucket-1",
                "type": "s3:bucket",
                "name": "test-bucket-1",
                "tenant_id": "123456789012",
                "arn": "arn:aws:s3:::test-bucket-1",
                "state": {"creation_date": "2026-10-01T00:00:00Z"},
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            }
            # test-bucket-2 removed
        ]
    )

    # Second poll
    await poller._poll_cycle()

    # Verify bucket was deleted
    all_resources = query_nodes(label="Resource")
    assert len(all_resources) == 3

    s3_resources = query_nodes(label="Resource", filters={"type": "s3:bucket"})
    assert len(s3_resources) == 1
    assert s3_resources[0]["name"] == "test-bucket-1"


@pytest.mark.asyncio
async def test_poll_handles_ministack_failure(graph, mock_ministack_client):
    """Test that poll handles MiniStack health check failure."""
    poller = ResourcePoller(client=mock_ministack_client)

    # Mock unhealthy MiniStack
    mock_ministack_client.health_check = AsyncMock(
        return_value={
            "healthy": False,
            "instance_id": None,
            "error": "Connection refused",
        }
    )

    # Run poll cycle
    await poller._poll_cycle()

    # Verify failure count incremented
    assert poller.failure_count == 1

    # Verify no resources created (poll cycle aborted)
    all_resources = query_nodes(label="Resource")
    assert len(all_resources) == 0


@pytest.mark.asyncio
async def test_poll_marks_stale_after_threshold(graph, mock_ministack_client):
    """Test that resources are marked stale after failure threshold."""
    poller = ResourcePoller(client=mock_ministack_client)

    # First successful poll
    await poller._poll_cycle()

    assert len(query_nodes(label="Resource")) == 4
    assert poller.failure_count == 0

    # Mock unhealthy MiniStack
    mock_ministack_client.health_check = AsyncMock(
        return_value={
            "healthy": False,
            "instance_id": None,
            "error": "Connection refused",
        }
    )

    # Run 3 failed poll cycles (reaches threshold)
    for _ in range(3):
        await poller._poll_cycle()

    # Verify failure threshold reached
    assert poller.failure_count == 3

    # Verify resources marked as stale
    graph_instance = get_graph()
    result = graph_instance.query(
        "MATCH (r:Resource {tenant_id: $tenant_id}) WHERE r.stale = true RETURN count(r) AS stale_count",
        params={"tenant_id": "123456789012"},
    )

    stale_count = result.result_set[0][0] if result.result_set else 0
    assert stale_count == 4


@pytest.mark.asyncio
async def test_poll_clears_stale_after_recovery(graph, mock_ministack_client):
    """Test that stale markers are cleared after successful poll."""
    poller = ResourcePoller(client=mock_ministack_client)

    # First successful poll
    await poller._poll_cycle()

    # Simulate failures
    mock_ministack_client.health_check = AsyncMock(
        return_value={"healthy": False, "instance_id": None, "error": "Connection refused"}
    )

    for _ in range(3):
        await poller._poll_cycle()

    # Verify resources marked stale
    assert poller.failure_count == 3

    # Restore healthy MiniStack
    mock_ministack_client.health_check = AsyncMock(
        return_value={
            "healthy": True,
            "instance_id": "test-instance-123",
            "error": None,
        }
    )

    # Successful poll
    await poller._poll_cycle()

    # Verify failure count cleared
    assert poller.failure_count == 0

    # Verify stale markers cleared
    graph_instance = get_graph()
    result = graph_instance.query(
        "MATCH (r:Resource {tenant_id: $tenant_id}) WHERE r.stale = true RETURN count(r) AS stale_count",
        params={"tenant_id": "123456789012"},
    )

    stale_count = result.result_set[0][0] if result.result_set else 0
    assert stale_count == 0
