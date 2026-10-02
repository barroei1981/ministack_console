"""
Tests for graph query endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_query_dependencies_found():
    """Test querying dependencies when relationships exist."""
    with patch("api.routes.graph.query_relationships") as mock_query:
        mock_query.return_value = [
            {
                "from_node_id": "arn:aws:lambda:us-east-1:111111111111:function:func1",
                "to_node_id": "arn:aws:s3:::bucket1",
                "rel_type": "DEPENDS_ON",
                "properties": {"dependency_type": "environment_variable"},
            },
            {
                "from_node_id": "arn:aws:lambda:us-east-1:111111111111:function:func1",
                "to_node_id": "arn:aws:sqs:us-east-1:111111111111:queue1",
                "rel_type": "DEPENDS_ON",
                "properties": {"dependency_type": "event_source"},
            },
        ]

        response = client.get(
            "/api/graph/dependencies?resource_id=arn:aws:lambda:us-east-1:111111111111:function:func1&tenant_id=111111111111"
        )

        assert response.status_code == 200
        data = response.json()
        assert "dependencies" in data
        assert len(data["dependencies"]) == 2
        assert data["dependencies"][0]["to_node_id"] == "arn:aws:s3:::bucket1"
        assert data["dependencies"][0]["metadata"]["dependency_type"] == "environment_variable"
        assert data["dependencies"][1]["to_node_id"] == "arn:aws:sqs:us-east-1:111111111111:queue1"


def test_query_dependencies_not_found():
    """Test querying dependencies when none exist."""
    with patch("api.routes.graph.query_relationships") as mock_query:
        mock_query.return_value = []

        response = client.get(
            "/api/graph/dependencies?resource_id=arn:aws:s3:::bucket1&tenant_id=111111111111"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["dependencies"] == []
        assert data["resource_id"] == "arn:aws:s3:::bucket1"


def test_query_dependencies_missing_resource_id():
    """Test that resource_id query param is required."""
    response = client.get("/api/graph/dependencies?tenant_id=111111111111")

    assert response.status_code == 422  # Pydantic validation error
    data = response.json()
    assert "detail" in data


def test_query_dependents_found():
    """Test querying dependents when relationships exist."""
    with patch("api.routes.graph.query_reverse_relationships") as mock_query:
        mock_query.return_value = [
            {
                "from_node_id": "arn:aws:lambda:us-east-1:111111111111:function:func1",
                "to_node_id": "arn:aws:s3:::bucket1",
                "rel_type": "DEPENDS_ON",
                "properties": {"dependency_type": "environment_variable"},
            },
            {
                "from_node_id": "arn:aws:lambda:us-east-1:111111111111:function:func2",
                "to_node_id": "arn:aws:s3:::bucket1",
                "rel_type": "DEPENDS_ON",
                "properties": {"dependency_type": "event_source"},
            },
        ]

        response = client.get(
            "/api/graph/dependents?resource_id=arn:aws:s3:::bucket1&tenant_id=111111111111"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["dependencies"]) == 2
        assert (
            data["dependencies"][0]["from_node_id"]
            == "arn:aws:lambda:us-east-1:111111111111:function:func1"
        )
        assert data["dependencies"][0]["to_node_id"] == "arn:aws:s3:::bucket1"


def test_query_dependents_not_found():
    """Test querying dependents when none exist."""
    with patch("api.routes.graph.query_reverse_relationships") as mock_query:
        mock_query.return_value = []

        response = client.get(
            "/api/graph/dependents?resource_id=arn:aws:s3:::bucket1&tenant_id=111111111111"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["dependencies"] == []


def test_query_dependents_missing_resource_id():
    """Test that resource_id query param is required."""
    response = client.get("/api/graph/dependents?tenant_id=111111111111")

    assert response.status_code == 422  # Pydantic validation error
