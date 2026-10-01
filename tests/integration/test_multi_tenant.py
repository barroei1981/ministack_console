"""
Integration test for multi-tenant isolation.

Tests that resources from different tenants are properly isolated
and cannot be accessed across tenant boundaries.
"""

import pytest
import asyncio
from datetime import datetime, UTC

from control_plane.graph.query import (
    get_graph,
    reset_graph,
    create_node,
)
from control_plane.graph.schema import initialize_schema
from control_plane.tenants.isolation import (
    ensure_tenant_exists,
    get_tenant_resources,
    create_project_with_ownership,
    list_tenants,
)
from control_plane.inventory.models import Resource
from control_plane.inventory.sync import sync_changes
from control_plane.inventory.models import Change, ChangeType


@pytest.fixture(scope="module")
def graph():
    """Initialize FalkorDB with schema for testing."""
    graph = get_graph()
    reset_graph()  # Clean slate for tests
    initialize_schema(graph)
    return graph


@pytest.fixture
def clean_graph(graph):
    """Reset graph before each test."""
    reset_graph()
    initialize_schema(graph)
    yield graph


class TestMultiTenantIsolation:
    """Test multi-tenant isolation end-to-end."""

    @pytest.mark.asyncio
    async def test_two_tenants_with_resources(self, clean_graph):
        """
        Create resources for two tenants and verify isolation.

        Scenario:
        - Tenant A (123456789012) creates 3 resources
        - Tenant B (999888777666) creates 2 resources
        - Query tenant A returns only A's resources
        - Query tenant B returns only B's resources
        """
        tenant_a = "123456789012"
        tenant_b = "999888777666"

        # Create resources for tenant A
        resources_a = [
            Resource(
                id="bucket-a-1",
                type="s3:bucket",
                name="bucket-a-1",
                tenant_id=tenant_a,
                arn=f"arn:aws:s3:::{tenant_a}:bucket-a-1",
                state={"region": "us-east-1"},
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            ),
            Resource(
                id="func-a-1",
                type="lambda:function",
                name="func-a-1",
                tenant_id=tenant_a,
                arn=f"arn:aws:lambda:::{tenant_a}:function:func-a-1",
                state={"runtime": "python3.11"},
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            ),
            Resource(
                id="queue-a-1",
                type="sqs:queue",
                name="queue-a-1",
                tenant_id=tenant_a,
                arn=f"arn:aws:sqs:::{tenant_a}:queue-a-1",
                state={"visibility_timeout": 30},
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            ),
        ]

        # Create resources for tenant B
        resources_b = [
            Resource(
                id="bucket-b-1",
                type="s3:bucket",
                name="bucket-b-1",
                tenant_id=tenant_b,
                arn=f"arn:aws:s3:::{tenant_b}:bucket-b-1",
                state={"region": "us-west-2"},
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            ),
            Resource(
                id="func-b-1",
                type="lambda:function",
                name="func-b-1",
                tenant_id=tenant_b,
                arn=f"arn:aws:lambda:::{tenant_b}:function:func-b-1",
                state={"runtime": "nodejs20.x"},
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            ),
        ]

        # Sync resources (this should auto-create Tenant nodes)
        changes_a = [Change(ChangeType.CREATED, resource=r) for r in resources_a]
        changes_b = [Change(ChangeType.CREATED, resource=r) for r in resources_b]

        await sync_changes(changes_a)
        await sync_changes(changes_b)

        # Verify tenant A's resources
        tenant_a_resources = get_tenant_resources(tenant_a)
        assert len(tenant_a_resources) == 3

        tenant_a_ids = {r["id"] for r in tenant_a_resources}
        assert tenant_a_ids == {"bucket-a-1", "func-a-1", "queue-a-1"}

        # Verify NO resources from tenant B appear in tenant A's results
        for resource in tenant_a_resources:
            assert resource["tenant_id"] == tenant_a
            assert not resource["id"].endswith("-b-1")

        # Verify tenant B's resources
        tenant_b_resources = get_tenant_resources(tenant_b)
        assert len(tenant_b_resources) == 2

        tenant_b_ids = {r["id"] for r in tenant_b_resources}
        assert tenant_b_ids == {"bucket-b-1", "func-b-1"}

        # Verify NO resources from tenant A appear in tenant B's results
        for resource in tenant_b_resources:
            assert resource["tenant_id"] == tenant_b
            assert not resource["id"].endswith("-a-1")

    @pytest.mark.asyncio
    async def test_tenant_filtered_by_resource_type(self, clean_graph):
        """
        Verify resource type filtering works within tenant scope.

        Scenario:
        - Tenant creates S3 bucket and Lambda function
        - Query for s3:bucket returns only bucket
        - Query for lambda:function returns only function
        """
        tenant_id = "123456789012"

        resources = [
            Resource(
                id="bucket-1",
                type="s3:bucket",
                name="bucket-1",
                tenant_id=tenant_id,
                arn=f"arn:aws:s3:::{tenant_id}:bucket-1",
                state={},
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            ),
            Resource(
                id="func-1",
                type="lambda:function",
                name="func-1",
                tenant_id=tenant_id,
                arn=f"arn:aws:lambda:::{tenant_id}:function:func-1",
                state={},
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            ),
        ]

        changes = [Change(ChangeType.CREATED, resource=r) for r in resources]
        await sync_changes(changes)

        # Query for S3 buckets only
        s3_resources = get_tenant_resources(tenant_id, resource_type="s3:bucket")
        assert len(s3_resources) == 1
        assert s3_resources[0]["id"] == "bucket-1"
        assert s3_resources[0]["type"] == "s3:bucket"

        # Query for Lambda functions only
        lambda_resources = get_tenant_resources(tenant_id, resource_type="lambda:function")
        assert len(lambda_resources) == 1
        assert lambda_resources[0]["id"] == "func-1"
        assert lambda_resources[0]["type"] == "lambda:function"

    @pytest.mark.asyncio
    async def test_tenant_auto_creation(self, clean_graph):
        """
        Verify Tenant nodes are created automatically when first resource appears.

        Scenario:
        - No tenants exist initially
        - Create resource for tenant A
        - Tenant A node should exist
        - list_tenants() should return tenant A
        """
        tenant_id = "123456789012"

        # Verify no tenants exist initially
        assert len(list_tenants()) == 0

        # Create resource for tenant
        resource = Resource(
            id="bucket-1",
            type="s3:bucket",
            name="bucket-1",
            tenant_id=tenant_id,
            arn=f"arn:aws:s3:::{tenant_id}:bucket-1",
            state={},
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )

        changes = [Change(ChangeType.CREATED, resource=resource)]
        await sync_changes(changes)

        # Verify tenant was auto-created
        tenants = list_tenants()
        assert len(tenants) == 1
        assert tenants[0]["id"] == tenant_id

    @pytest.mark.asyncio
    async def test_project_ownership_isolation(self, clean_graph):
        """
        Verify projects are owned by correct tenant.

        Scenario:
        - Create project for tenant A
        - Verify (Tenant A)-[:OWNS]->(Project) relationship exists
        - Verify project has correct tenant_id
        """
        tenant_id = "123456789012"

        # Create tenant first
        await ensure_tenant_exists(tenant_id)

        # Create project for tenant
        project = create_project_with_ownership(
            "my-project", tenant_id, "Test project"
        )

        assert project["name"] == "my-project"
        assert project["tenant_id"] == tenant_id

        # Verify relationship exists (query for project via tenant)
        from control_plane.graph.query import get_graph

        graph = get_graph()
        query = """
        MATCH (t:Tenant {id: $tenant_id})-[:OWNS]->(p:Project {name: $project_name})
        RETURN p
        """
        result = graph.query(
            query, params={"tenant_id": tenant_id, "project_name": "my-project"}
        )

        assert len(result.result_set) == 1
        project_node = result.result_set[0][0]
        assert project_node.properties["name"] == "my-project"

    @pytest.mark.asyncio
    async def test_empty_tenant_query(self, clean_graph):
        """
        Verify querying nonexistent tenant returns empty list.

        Scenario:
        - Query resources for tenant that has no resources
        - Should return empty list (not error)
        """
        tenant_id = "999999999999"

        # Query tenant with no resources
        resources = get_tenant_resources(tenant_id)

        assert resources == []
        assert isinstance(resources, list)
