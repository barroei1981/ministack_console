"""
Tests for tenant endpoints.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_list_tenants_empty():
    """Test listing tenants when none exist."""
    with patch("api.routes.tenants.query_nodes") as mock_query:
        mock_query.return_value = []

        response = client.get("/api/tenants?tenant_id=000000000000")

        assert response.status_code == 200
        data = response.json()
        assert data == []


def test_list_tenants_multiple():
    """Test listing multiple tenants."""
    with patch("api.routes.tenants.query_nodes") as mock_query:
        # First call returns tenants, subsequent calls return resources per tenant
        mock_query.side_effect = [
            # Tenant list
            [
                {
                    "id": "111111111111",
                    "name": "tenant-1",
                    "created_at": "2026-10-01T00:00:00Z",
                },
                {
                    "id": "222222222222",
                    "name": "tenant-2",
                    "created_at": "2026-10-02T00:00:00Z",
                },
            ],
            # Resources for tenant-1
            [{"id": "res1"}, {"id": "res2"}],
            # Resources for tenant-2
            [{"id": "res3"}],
        ]

        response = client.get("/api/tenants?tenant_id=000000000000")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "111111111111"
        assert data[0]["resource_count"] == 2
        assert data[1]["id"] == "222222222222"
        assert data[1]["resource_count"] == 1


def test_list_tenant_resources_invalid_tenant():
    """Test listing resources for non-existent tenant."""
    with patch("api.routes.tenants.query_nodes") as mock_query:
        # Tenant not found
        mock_query.return_value = []

        response = client.get("/api/tenants/999999999999/resources?tenant_id=999999999999")

        assert response.status_code == 404
        data = response.json()
        assert "Tenant 999999999999 not found" in data["detail"]


def test_list_tenant_resources_valid_tenant():
    """Test listing resources for valid tenant."""
    with patch("api.routes.tenants.query_nodes") as mock_query:
        mock_query.side_effect = [
            # Tenant exists
            [{"id": "111111111111", "name": "tenant-1"}],
            # Resources for tenant
            [
                {
                    "id": "arn:aws:s3:::bucket1",
                    "type": "s3:bucket",
                    "name": "bucket1",
                    "tenant_id": "111111111111",
                    "project": "app1",
                    "tags": {"env": "dev"},
                    "created_at": "2026-10-01T00:00:00Z",
                    "state": {"status": "active"},
                },
                {
                    "id": "arn:aws:lambda:us-east-1:111111111111:function:func1",
                    "type": "lambda:function",
                    "name": "func1",
                    "tenant_id": "111111111111",
                    "project": "app1",
                    "tags": {},
                    "created_at": "2026-10-02T00:00:00Z",
                    "state": {"runtime": "python3.11"},
                },
            ],
        ]

        response = client.get("/api/tenants/111111111111/resources?tenant_id=111111111111")

        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
        assert "pagination" in data
        assert len(data["resources"]) == 2
        assert data["resources"][0]["id"] == "arn:aws:s3:::bucket1"
        assert data["resources"][0]["type"] == "s3:bucket"
        assert data["resources"][0]["state_summary"]["status"] == "active"
        assert data["resources"][1]["state_summary"]["runtime"] == "python3.11"
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total"] == 2
        assert data["pagination"]["next"] is None


def test_list_tenant_resources_pagination():
    """Test pagination of tenant resources."""
    with patch("api.routes.tenants.query_nodes") as mock_query:
        # Generate 150 resources
        resources = [
            {
                "id": f"arn:aws:s3:::bucket{i}",
                "type": "s3:bucket",
                "name": f"bucket{i}",
                "tenant_id": "111111111111",
                "project": "app1",
                "tags": {},
                "created_at": "2026-10-01T00:00:00Z",
                "state": {},
            }
            for i in range(150)
        ]

        mock_query.side_effect = [
            # Tenant exists
            [{"id": "111111111111"}],
            # All resources
            resources,
        ]

        response = client.get(
            "/api/tenants/111111111111/resources?tenant_id=111111111111&page=1&limit=100"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["resources"]) == 100
        assert data["pagination"]["total"] == 150
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["next"] is not None
        assert "page=2" in data["pagination"]["next"]


def test_list_tenant_resources_page_beyond_end():
    """Test requesting page beyond available data."""
    with patch("api.routes.tenants.query_nodes") as mock_query:
        mock_query.side_effect = [
            # Tenant exists
            [{"id": "111111111111"}],
            # 5 resources
            [
                {
                    "id": f"arn:aws:s3:::bucket{i}",
                    "type": "s3:bucket",
                    "name": f"bucket{i}",
                    "tenant_id": "111111111111",
                    "tags": {},
                    "created_at": "2026-10-01T00:00:00Z",
                    "state": {},
                }
                for i in range(5)
            ],
        ]

        response = client.get(
            "/api/tenants/111111111111/resources?tenant_id=111111111111&page=999&limit=100"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["resources"]) == 0
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["page"] == 999


@pytest.mark.skip(reason="TestClient doesn't handle middleware exceptions properly in Python 3.14 - covered by e2e test")
def test_tenant_resources_missing_tenant_id():
    """Test that tenant_id is required."""
    response = client.get("/api/tenants/111111111111/resources")

    assert response.status_code == 400
    data = response.json()
    assert "tenant_id required" in data["detail"]
