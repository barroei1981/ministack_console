"""
Tests for health check endpoint.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_check_both_healthy():
    """Test health check when both services are healthy."""
    with patch("api.routes.health.graph_health_check") as mock_graph, patch(
        "api.routes.health.MiniStackClient"
    ) as mock_ministack_class:
        # Mock FalkorDB healthy
        mock_graph.return_value = True

        # Mock MiniStack healthy
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {
            "healthy": True,
            "instance_id": "test-instance",
            "error": None,
        }
        mock_ministack_class.return_value = mock_client

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["falkordb"]["connected"] is True
        assert data["ministack"]["connected"] is True
        assert data["ministack"]["instance_id"] == "test-instance"


def test_health_check_falkordb_down():
    """Test health check when FalkorDB is down."""
    with patch("api.routes.health.graph_health_check") as mock_graph, patch(
        "api.routes.health.MiniStackClient"
    ) as mock_ministack_class:
        # Mock FalkorDB down
        mock_graph.return_value = False

        # Mock MiniStack healthy
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {
            "healthy": True,
            "instance_id": "test-instance",
            "error": None,
        }
        mock_ministack_class.return_value = mock_client

        response = client.get("/api/health")

        # Should return 503 when unhealthy
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["falkordb"]["connected"] is False
        assert data["falkordb"]["error"] == "Connection failed"
        assert data["ministack"]["connected"] is True


def test_health_check_ministack_down():
    """Test health check when MiniStack is down."""
    with patch("api.routes.health.graph_health_check") as mock_graph, patch(
        "api.routes.health.MiniStackClient"
    ) as mock_ministack_class:
        # Mock FalkorDB healthy
        mock_graph.return_value = True

        # Mock MiniStack down
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {
            "healthy": False,
            "instance_id": None,
            "error": "Connection timeout",
        }
        mock_ministack_class.return_value = mock_client

        response = client.get("/api/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["falkordb"]["connected"] is True
        assert data["ministack"]["connected"] is False
        assert data["ministack"]["error"] == "Connection timeout"


def test_health_check_both_down():
    """Test health check when both services are down."""
    with patch("api.routes.health.graph_health_check") as mock_graph, patch(
        "api.routes.health.MiniStackClient"
    ) as mock_ministack_class:
        # Mock both down
        mock_graph.return_value = False

        mock_client = AsyncMock()
        mock_client.health_check.return_value = {
            "healthy": False,
            "instance_id": None,
            "error": "Connection refused",
        }
        mock_ministack_class.return_value = mock_client

        response = client.get("/api/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["falkordb"]["connected"] is False
        assert data["ministack"]["connected"] is False
