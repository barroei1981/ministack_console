"""
End-to-end integration tests for REST API.

Requires FalkorDB running (docker-compose up).
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from control_plane.graph.query import (
    reset_graph,
    create_node,
    create_relationship,
    health_check,
)

client = TestClient(app)

# Mark as integration test
pytestmark = pytest.mark.integration


@pytest.fixture(scope="function")
def setup_graph():
    """Set up test graph data."""
    # Check FalkorDB is available
    if not health_check():
        pytest.skip("FalkorDB not available")

    # Reset graph
    reset_graph()

    # Create tenant
    create_node("Tenant", {"id": "111111111111", "name": "test-tenant", "created_at": "2026-10-01T00:00:00Z"})

    # Create resources
    create_node(
        "Resource",
        {
            "id": "arn:aws:s3:::bucket1",
            "type": "s3:bucket",
            "name": "bucket1",
            "tenant_id": "111111111111",
            "project": "app1",
            "tags": "{}",
            "created_at": "2026-10-01T00:00:00Z",
            "state": "{}",
        },
    )

    create_node(
        "Resource",
        {
            "id": "arn:aws:lambda:us-east-1:111111111111:function:func1",
            "type": "lambda:function",
            "name": "func1",
            "tenant_id": "111111111111",
            "project": "app1",
            "tags": "{}",
            "created_at": "2026-10-02T00:00:00Z",
            "state": '{"runtime": "python3.11"}',
        },
    )

    # Create dependency
    create_relationship(
        from_node_id="arn:aws:lambda:us-east-1:111111111111:function:func1",
        from_label="Resource",
        rel_type="DEPENDS_ON",
        to_node_id="arn:aws:s3:::bucket1",
        to_label="Resource",
        properties={"dependency_type": "environment_variable"},
    )

    yield

    # Cleanup
    reset_graph()


def test_e2e_health_check():
    """Test health check endpoint."""
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "falkordb" in data
    assert "ministack" in data


def test_e2e_list_tenants(setup_graph):
    """Test listing tenants end-to-end."""
    response = client.get("/api/tenants?tenant_id=111111111111")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "111111111111"
    assert data[0]["resource_count"] == 2


def test_e2e_list_tenant_resources(setup_graph):
    """Test listing tenant resources end-to-end."""
    response = client.get(
        "/api/tenants/111111111111/resources?tenant_id=111111111111&page=1&limit=10"
    )

    assert response.status_code == 200
    data = response.json()
    assert "resources" in data
    assert "pagination" in data
    assert len(data["resources"]) == 2
    assert data["pagination"]["total"] == 2
    assert data["pagination"]["page"] == 1


def test_e2e_list_tenant_projects(setup_graph):
    """Test listing tenant projects end-to-end."""
    response = client.get("/api/tenants/111111111111/projects?tenant_id=111111111111")

    assert response.status_code == 200
    data = response.json()
    assert "projects" in data
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "app1"
    assert data["projects"][0]["resource_count"] == 2


def test_e2e_query_dependencies(setup_graph):
    """Test querying dependencies end-to-end."""
    response = client.get(
        "/api/graph/dependencies?resource_id=arn:aws:lambda:us-east-1:111111111111:function:func1&tenant_id=111111111111"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["dependencies"]) == 1
    assert data["dependencies"][0]["to_node_id"] == "arn:aws:s3:::bucket1"
    assert data["dependencies"][0]["metadata"]["dependency_type"] == "environment_variable"


def test_e2e_query_dependents(setup_graph):
    """Test querying dependents end-to-end."""
    response = client.get(
        "/api/graph/dependents?resource_id=arn:aws:s3:::bucket1&tenant_id=111111111111"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["dependencies"]) == 1
    assert (
        data["dependencies"][0]["from_node_id"]
        == "arn:aws:lambda:us-east-1:111111111111:function:func1"
    )


def test_e2e_pagination(setup_graph):
    """Test pagination with multiple resources."""
    # Create more resources
    for i in range(10):
        create_node(
            "Resource",
            {
                "id": f"arn:aws:s3:::bucket{i+2}",
                "type": "s3:bucket",
                "name": f"bucket{i+2}",
                "tenant_id": "111111111111",
                "project": "app1",
                "tags": "{}",
                "created_at": "2026-10-01T00:00:00Z",
                "state": "{}",
            },
        )

    # Query page 1
    response = client.get(
        "/api/tenants/111111111111/resources?tenant_id=111111111111&page=1&limit=5"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["resources"]) == 5
    assert data["pagination"]["total"] == 12
    assert data["pagination"]["next"] is not None
    assert "page=2" in data["pagination"]["next"]

    # Query page 2
    response = client.get(
        "/api/tenants/111111111111/resources?tenant_id=111111111111&page=2&limit=5"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["resources"]) == 5
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["prev"] is not None
    assert "page=1" in data["pagination"]["prev"]


def test_e2e_invalid_tenant_id():
    """Test that invalid tenant_id format is rejected."""
    response = client.get("/api/tenants?tenant_id=invalid")

    assert response.status_code == 400
    data = response.json()
    assert "Invalid tenant_id format" in data["detail"]


def test_e2e_missing_tenant_id():
    """Test that missing tenant_id is rejected."""
    response = client.get("/api/tenants")

    assert response.status_code == 400
    data = response.json()
    assert "tenant_id required" in data["detail"]
