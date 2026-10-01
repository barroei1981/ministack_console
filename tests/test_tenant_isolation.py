"""
Unit tests for tenant isolation operations.

Tests tenant management functions from control_plane.tenants.isolation.
"""

import pytest
from unittest.mock import patch, MagicMock

from control_plane.tenants.isolation import (
    validate_tenant_id,
    ensure_tenant_exists,
    get_tenant_resources,
    create_project_with_ownership,
    list_tenants,
)


class TestValidateTenantId:
    """Test tenant ID validation."""

    def test_valid_tenant_id(self):
        """Valid 12-digit tenant ID should not raise."""
        validate_tenant_id("123456789012")  # Should not raise

    def test_empty_tenant_id(self):
        """Empty tenant ID should raise ValueError."""
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            validate_tenant_id("")

    def test_short_tenant_id(self):
        """Tenant ID with fewer than 12 digits should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            validate_tenant_id("123")

    def test_long_tenant_id(self):
        """Tenant ID with more than 12 digits should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            validate_tenant_id("1234567890123")

    def test_non_numeric_tenant_id(self):
        """Non-numeric tenant ID should raise ValueError."""
        with pytest.raises(ValueError, match="Must be numeric"):
            validate_tenant_id("12345678901a")


class TestEnsureTenantExists:
    """Test ensure_tenant_exists() idempotent tenant creation."""

    @pytest.mark.asyncio
    @patch("control_plane.tenants.isolation.query_nodes")
    async def test_tenant_already_exists(self, mock_query):
        """If tenant exists, should not create new node."""
        mock_query.return_value = [{"id": "123456789012"}]

        await ensure_tenant_exists("123456789012")

        mock_query.assert_called_once_with("Tenant", filters={"id": "123456789012"})

    @pytest.mark.asyncio
    @patch("control_plane.tenants.isolation.create_node")
    @patch("control_plane.tenants.isolation.query_nodes")
    async def test_create_new_tenant(self, mock_query, mock_create):
        """If tenant doesn't exist, should create new Tenant node."""
        mock_query.return_value = []  # Tenant doesn't exist

        await ensure_tenant_exists("123456789012")

        mock_query.assert_called_once_with("Tenant", filters={"id": "123456789012"})
        mock_create.assert_called_once()

        # Check properties passed to create_node
        call_args = mock_create.call_args
        assert call_args[0][0] == "Tenant"
        props = call_args[0][1]
        assert props["id"] == "123456789012"
        assert props["name"] == "123456789012"
        assert "created_at" in props

    @pytest.mark.asyncio
    async def test_invalid_tenant_id_format(self):
        """Invalid tenant ID should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            await ensure_tenant_exists("abc")


class TestGetTenantResources:
    """Test get_tenant_resources() tenant-scoped queries."""

    @patch("control_plane.tenants.isolation.query_nodes")
    def test_get_all_resources_for_tenant(self, mock_query):
        """Should query resources filtered by tenant_id."""
        mock_query.return_value = [
            {"id": "bucket-1", "type": "s3:bucket", "tenant_id": "123456789012"},
            {"id": "func-1", "type": "lambda:function", "tenant_id": "123456789012"},
        ]

        result = get_tenant_resources("123456789012")

        mock_query.assert_called_once_with(
            "Resource", filters={"tenant_id": "123456789012"}
        )
        assert len(result) == 2
        assert result[0]["id"] == "bucket-1"
        assert result[1]["id"] == "func-1"

    @patch("control_plane.tenants.isolation.query_nodes")
    def test_get_resources_filtered_by_type(self, mock_query):
        """Should query resources filtered by tenant_id AND type."""
        mock_query.return_value = [
            {"id": "bucket-1", "type": "s3:bucket", "tenant_id": "123456789012"}
        ]

        result = get_tenant_resources("123456789012", resource_type="s3:bucket")

        mock_query.assert_called_once_with(
            "Resource", filters={"tenant_id": "123456789012", "type": "s3:bucket"}
        )
        assert len(result) == 1
        assert result[0]["type"] == "s3:bucket"

    @patch("control_plane.tenants.isolation.query_nodes")
    def test_no_resources_for_tenant(self, mock_query):
        """Should return empty list if tenant has no resources."""
        mock_query.return_value = []

        result = get_tenant_resources("123456789012")

        assert result == []

    def test_invalid_tenant_id(self):
        """Invalid tenant ID should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            get_tenant_resources("abc")


class TestCreateProjectWithOwnership:
    """Test create_project_with_ownership() project creation with relationship."""

    @patch("control_plane.tenants.isolation.create_relationship")
    @patch("control_plane.tenants.isolation.create_node")
    @patch("control_plane.tenants.isolation.query_nodes")
    def test_create_project_success(self, mock_query, mock_create, mock_create_rel):
        """Should create Project node and OWNS relationship."""
        mock_query.return_value = [{"id": "123456789012"}]  # Tenant exists
        mock_create.return_value = {
            "name": "my-project",
            "tenant_id": "123456789012",
        }

        result = create_project_with_ownership(
            "my-project", "123456789012", "Test project"
        )

        # Verify tenant existence check
        mock_query.assert_called_once_with("Tenant", filters={"id": "123456789012"})

        # Verify Project node creation
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "Project"
        props = call_args[0][1]
        assert props["name"] == "my-project"
        assert props["tenant_id"] == "123456789012"
        assert props["description"] == "Test project"

        # Verify OWNS relationship creation
        mock_create_rel.assert_called_once_with(
            from_node_id="123456789012",
            from_label="Tenant",
            rel_type="OWNS",
            to_node_id="my-project",
            to_label="Project",
        )

        assert result["name"] == "my-project"

    @patch("control_plane.tenants.isolation.query_nodes")
    def test_create_project_tenant_not_exists(self, mock_query):
        """Should raise ValueError if tenant doesn't exist."""
        mock_query.return_value = []  # Tenant doesn't exist

        with pytest.raises(ValueError, match="Tenant 123456789012 does not exist"):
            create_project_with_ownership("my-project", "123456789012")

    def test_create_project_invalid_tenant_id(self):
        """Invalid tenant ID should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            create_project_with_ownership("my-project", "abc")


class TestListTenants:
    """Test list_tenants() retrieval."""

    @patch("control_plane.tenants.isolation.query_nodes")
    def test_list_all_tenants(self, mock_query):
        """Should return all tenants."""
        mock_query.return_value = [
            {"id": "123456789012", "name": "123456789012"},
            {"id": "999888777666", "name": "999888777666"},
        ]

        result = list_tenants()

        mock_query.assert_called_once_with("Tenant")
        assert len(result) == 2
        assert result[0]["id"] == "123456789012"
        assert result[1]["id"] == "999888777666"

    @patch("control_plane.tenants.isolation.query_nodes")
    def test_list_no_tenants(self, mock_query):
        """Should return empty list if no tenants exist."""
        mock_query.return_value = []

        result = list_tenants()

        assert result == []
