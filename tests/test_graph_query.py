"""
Integration tests for FalkorDB CRUD operations.

Tests:
- Create node
- Create relationship
- Query by tenant_id, type, name
- Health check
"""

import pytest
from datetime import datetime, UTC
from control_plane.graph.query import (
    get_graph,
    health_check,
    create_node,
    create_relationship,
    query_nodes,
    delete_node,
    reset_graph,
)
from control_plane.graph.schema import initialize_schema


@pytest.fixture(scope="module")
def graph():
    """Provide FalkorDB graph instance with initialized schema."""
    try:
        g = get_graph()
        initialize_schema(g)
        yield g
    finally:
        # Clean up after all tests
        reset_graph()


@pytest.fixture(autouse=True)
def reset_before_test(graph):
    """Reset graph before each test to ensure clean state."""
    reset_graph()
    initialize_schema(graph)
    yield


def test_health_check():
    """Test FalkorDB health check function."""
    assert health_check() is True


def test_create_tenant_node(graph):
    """Test creating a Tenant node."""
    tenant_props = {
        "id": "123456789012",
        "name": "test-tenant",
        "created_at": datetime.now(UTC).isoformat(),
    }

    created = create_node("Tenant", tenant_props)

    assert created["id"] == tenant_props["id"]
    assert created["name"] == tenant_props["name"]

    # Verify node was created by querying
    results = query_nodes("Tenant", filters={"id": "123456789012"})
    assert len(results) == 1
    assert results[0]["id"] == "123456789012"


def test_create_project_node(graph):
    """Test creating a Project node."""
    project_props = {
        "name": "microservice-a",
        "description": "Test microservice project",
        "tenant_id": "123456789012",
        "created_at": datetime.now(UTC).isoformat(),
    }

    created = create_node("Project", project_props)

    assert created["name"] == project_props["name"]
    assert created["tenant_id"] == project_props["tenant_id"]


def test_create_resource_node(graph):
    """Test creating a Resource node with all required properties."""
    resource_props = {
        "id": "s3-bucket-test-bucket",
        "type": "s3:bucket",
        "name": "test-bucket",
        "tenant_id": "123456789012",
        "arn": "arn:aws:s3:::test-bucket",
        "state": '{"versioning": "Enabled", "region": "us-east-1"}',
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    created = create_node("Resource", resource_props)

    assert created["id"] == resource_props["id"]
    assert created["type"] == resource_props["type"]
    assert created["name"] == resource_props["name"]
    assert created["tenant_id"] == resource_props["tenant_id"]
    assert created["arn"] == resource_props["arn"]


def test_query_resources_by_tenant_id(graph):
    """Test querying resources filtered by tenant_id."""
    # Create resources in two different tenants
    tenant1_resource = {
        "id": "resource-1",
        "type": "s3:bucket",
        "name": "bucket-1",
        "tenant_id": "111111111111",
        "arn": "arn:aws:s3:::bucket-1",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    tenant2_resource = {
        "id": "resource-2",
        "type": "s3:bucket",
        "name": "bucket-2",
        "tenant_id": "222222222222",
        "arn": "arn:aws:s3:::bucket-2",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    create_node("Resource", tenant1_resource)
    create_node("Resource", tenant2_resource)

    # Query by tenant_id
    tenant1_results = query_nodes("Resource", filters={"tenant_id": "111111111111"})
    assert len(tenant1_results) == 1
    assert tenant1_results[0]["id"] == "resource-1"

    tenant2_results = query_nodes("Resource", filters={"tenant_id": "222222222222"})
    assert len(tenant2_results) == 1
    assert tenant2_results[0]["id"] == "resource-2"


def test_query_resources_by_type(graph):
    """Test querying resources filtered by type."""
    # Create resources of different types
    s3_resource = {
        "id": "s3-bucket-1",
        "type": "s3:bucket",
        "name": "my-bucket",
        "tenant_id": "123456789012",
        "arn": "arn:aws:s3:::my-bucket",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    lambda_resource = {
        "id": "lambda-function-1",
        "type": "lambda:function",
        "name": "my-function",
        "tenant_id": "123456789012",
        "arn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    create_node("Resource", s3_resource)
    create_node("Resource", lambda_resource)

    # Query by type
    s3_results = query_nodes("Resource", filters={"type": "s3:bucket"})
    assert len(s3_results) == 1
    assert s3_results[0]["type"] == "s3:bucket"

    lambda_results = query_nodes("Resource", filters={"type": "lambda:function"})
    assert len(lambda_results) == 1
    assert lambda_results[0]["type"] == "lambda:function"


def test_query_resources_by_name(graph):
    """Test querying resources filtered by name."""
    resource = {
        "id": "s3-bucket-unique",
        "type": "s3:bucket",
        "name": "unique-bucket-name",
        "tenant_id": "123456789012",
        "arn": "arn:aws:s3:::unique-bucket-name",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    create_node("Resource", resource)

    # Query by name
    results = query_nodes("Resource", filters={"name": "unique-bucket-name"})
    assert len(results) == 1
    assert results[0]["name"] == "unique-bucket-name"


def test_query_with_limit(graph):
    """Test querying with result limit."""
    # Create multiple resources
    for i in range(5):
        resource = {
            "id": f"resource-{i}",
            "type": "s3:bucket",
            "name": f"bucket-{i}",
            "tenant_id": "123456789012",
            "arn": f"arn:aws:s3:::bucket-{i}",
            "state": "{}",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        create_node("Resource", resource)

    # Query with limit
    results = query_nodes("Resource", limit=3)
    assert len(results) == 3


def test_create_owns_relationship(graph):
    """Test creating OWNS relationship between Tenant and Project."""
    # Create nodes
    tenant = {
        "id": "123456789012",
        "name": "test-tenant",
        "created_at": datetime.now(UTC).isoformat(),
    }
    project = {
        "name": "microservice-a",
        "id": "project-a",
        "description": "Test project",
        "tenant_id": "123456789012",
        "created_at": datetime.now(UTC).isoformat(),
    }

    create_node("Tenant", tenant)
    create_node("Project", project)

    # Create relationship
    rel = create_relationship(
        from_node_id="123456789012",
        from_label="Tenant",
        rel_type="OWNS",
        to_node_id="project-a",
        to_label="Project",
    )

    assert rel["rel_type"] == "OWNS"
    assert rel["from_node_id"] == "123456789012"
    assert rel["to_node_id"] == "project-a"


def test_create_contains_relationship(graph):
    """Test creating CONTAINS relationship between Project and Resource."""
    # Create nodes
    project = {
        "id": "project-a",
        "name": "microservice-a",
        "description": "Test project",
        "tenant_id": "123456789012",
        "created_at": datetime.now(UTC).isoformat(),
    }
    resource = {
        "id": "s3-bucket-1",
        "type": "s3:bucket",
        "name": "my-bucket",
        "tenant_id": "123456789012",
        "arn": "arn:aws:s3:::my-bucket",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    create_node("Project", project)
    create_node("Resource", resource)

    # Create relationship
    rel = create_relationship(
        from_node_id="project-a",
        from_label="Project",
        rel_type="CONTAINS",
        to_node_id="s3-bucket-1",
        to_label="Resource",
    )

    assert rel["rel_type"] == "CONTAINS"


def test_create_depends_on_relationship(graph):
    """Test creating DEPENDS_ON relationship between Resources."""
    # Create nodes
    lambda_resource = {
        "id": "lambda-function-1",
        "type": "lambda:function",
        "name": "my-function",
        "tenant_id": "123456789012",
        "arn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    s3_resource = {
        "id": "s3-bucket-1",
        "type": "s3:bucket",
        "name": "my-bucket",
        "tenant_id": "123456789012",
        "arn": "arn:aws:s3:::my-bucket",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    create_node("Resource", lambda_resource)
    create_node("Resource", s3_resource)

    # Create DEPENDS_ON relationship (Lambda depends on S3)
    rel = create_relationship(
        from_node_id="lambda-function-1",
        from_label="Resource",
        rel_type="DEPENDS_ON",
        to_node_id="s3-bucket-1",
        to_label="Resource",
    )

    assert rel["rel_type"] == "DEPENDS_ON"


def test_delete_node(graph):
    """Test deleting a node."""
    resource = {
        "id": "resource-to-delete",
        "type": "s3:bucket",
        "name": "delete-me",
        "tenant_id": "123456789012",
        "arn": "arn:aws:s3:::delete-me",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    create_node("Resource", resource)

    # Verify node exists
    results = query_nodes("Resource", filters={"id": "resource-to-delete"})
    assert len(results) == 1

    # Delete node
    deleted = delete_node("Resource", "resource-to-delete")
    assert deleted is True

    # Verify node no longer exists
    results = query_nodes("Resource", filters={"id": "resource-to-delete"})
    assert len(results) == 0


def test_delete_nonexistent_node(graph):
    """Test deleting a node that doesn't exist."""
    deleted = delete_node("Resource", "nonexistent-id")
    assert deleted is False


def test_create_node_missing_properties(graph):
    """Test that creating a node with missing properties raises error."""
    with pytest.raises(ValueError):
        create_node("Resource", {})


def test_create_node_missing_label(graph):
    """Test that creating a node without label raises error."""
    with pytest.raises(ValueError):
        create_node("", {"id": "test"})


def test_create_relationship_missing_params(graph):
    """Test that creating a relationship with missing params raises error."""
    with pytest.raises(ValueError):
        create_relationship(
            from_node_id="",
            from_label="Tenant",
            rel_type="OWNS",
            to_node_id="project-1",
            to_label="Project",
        )
