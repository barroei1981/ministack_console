"""
Unit tests for control-plane tagging operations.

Tests control-plane tag CRUD operations with FalkorDB storage.
"""

import pytest
from unittest.mock import patch, MagicMock

from control_plane.tagging.control_plane import (
    add_control_plane_tag,
    remove_control_plane_tag,
    get_control_plane_tags,
    query_resources_by_tag,
    _validate_tag_key,
    _validate_tag_value,
)
from control_plane.tagging.models import (
    TagNamespace,
    MAX_TAG_KEY_LENGTH,
    MAX_TAG_VALUE_LENGTH,
)


class TestValidateTagKey:
    """Test tag key validation for control-plane tags."""

    def test_valid_key(self):
        """Valid keys should not raise."""
        _validate_tag_key("project")
        _validate_tag_key("environment")
        _validate_tag_key("team_name")
        _validate_tag_key("app-version")
        _validate_tag_key("aws:cloudformation:stack-name")  # AWS-compatible chars

    def test_empty_key(self):
        """Empty key should raise ValueError."""
        with pytest.raises(ValueError, match="Tag key cannot be empty"):
            _validate_tag_key("")

    def test_key_too_long(self):
        """Key exceeding MAX_TAG_KEY_LENGTH should raise ValueError."""
        long_key = "a" * (MAX_TAG_KEY_LENGTH + 1)
        with pytest.raises(ValueError, match=f"exceeds {MAX_TAG_KEY_LENGTH}"):
            _validate_tag_key(long_key)

    def test_key_with_invalid_chars(self):
        """Key with disallowed characters should raise ValueError."""
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_tag_key("project$name")

        with pytest.raises(ValueError, match="invalid characters"):
            _validate_tag_key("project<tag>")

    def test_key_max_length(self):
        """Key at exactly MAX_TAG_KEY_LENGTH should be valid."""
        max_key = "a" * MAX_TAG_KEY_LENGTH
        _validate_tag_key(max_key)  # Should not raise


class TestValidateTagValue:
    """Test tag value validation."""

    def test_valid_value(self):
        """Valid values should not raise."""
        _validate_tag_value("app-1")
        _validate_tag_value("production")
        _validate_tag_value("")  # Empty value is valid

    def test_value_too_long(self):
        """Value exceeding MAX_TAG_VALUE_LENGTH should raise ValueError."""
        long_value = "a" * (MAX_TAG_VALUE_LENGTH + 1)
        with pytest.raises(ValueError, match=f"exceeds {MAX_TAG_VALUE_LENGTH}"):
            _validate_tag_value(long_value)

    def test_value_max_length(self):
        """Value at exactly MAX_TAG_VALUE_LENGTH should be valid."""
        max_value = "a" * MAX_TAG_VALUE_LENGTH
        _validate_tag_value(max_value)  # Should not raise


class TestAddControlPlaneTag:
    """Test add_control_plane_tag() operation."""

    @patch("control_plane.tagging.control_plane.get_graph")
    @patch("control_plane.tagging.control_plane.query_nodes")
    @patch("control_plane.tagging.control_plane.get_control_plane_tags")
    def test_add_tag_success(self, mock_get_tags, mock_query, mock_get_graph):
        """Adding a valid tag should create Tag node and TAGGED_WITH relationship."""
        # Mock resource exists
        mock_query.return_value = [
            {"id": "s3:bucket:test", "tenant_id": "123456789012"}
        ]

        # Mock graph operations
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = [[{"key": "project", "value": "app-1"}]]
        mock_graph.query.return_value = mock_result

        # Mock get_control_plane_tags for BEFORE/AFTER state
        mock_get_tags.side_effect = [{}, {"project": "app-1"}]  # before, after

        result = add_control_plane_tag(
            "s3:bucket:test", "project", "app-1", "123456789012"
        )

        assert result["resource_id"] == "s3:bucket:test"
        assert result["key"] == "project"
        assert result["value"] == "app-1"
        assert result["namespace"] == TagNamespace.CONTROL_PLANE.value

        # Verify graph queries were called
        assert mock_graph.query.call_count >= 2  # Tag node + relationship

    @patch("control_plane.tagging.control_plane.query_nodes")
    def test_add_tag_resource_not_found(self, mock_query):
        """Adding tag to non-existent resource should raise ValueError."""
        mock_query.return_value = []  # Resource not found

        with pytest.raises(ValueError, match="Resource .* not found"):
            add_control_plane_tag(
                "s3:bucket:nonexistent", "project", "app-1", "123456789012"
            )

    def test_add_tag_invalid_tenant_id(self):
        """Adding tag with invalid tenant_id should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            add_control_plane_tag("s3:bucket:test", "project", "app-1", "invalid")

    @patch("control_plane.tagging.control_plane.query_nodes")
    def test_add_tag_invalid_key(self, mock_query):
        """Adding tag with invalid key should raise ValueError."""
        mock_query.return_value = [{"id": "s3:bucket:test"}]

        with pytest.raises(ValueError, match="invalid characters"):
            add_control_plane_tag(
                "s3:bucket:test", "project$name", "app-1", "123456789012"
            )

    @patch("control_plane.tagging.control_plane.get_graph")
    @patch("control_plane.tagging.control_plane.query_nodes")
    @patch("control_plane.tagging.control_plane.get_control_plane_tags")
    def test_add_multiple_tags_to_resource(
        self, mock_get_tags, mock_query, mock_get_graph
    ):
        """Should be able to add multiple tags to same resource."""
        mock_query.return_value = [{"id": "s3:bucket:test"}]
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = [[{"key": "tag", "value": "value"}]]
        mock_graph.query.return_value = mock_result

        # Mock get_control_plane_tags for BEFORE/AFTER state
        mock_get_tags.side_effect = [
            {},
            {"project": "app-1"},
            {"project": "app-1"},
            {"project": "app-1", "environment": "dev"},
        ]

        # Add first tag
        result1 = add_control_plane_tag(
            "s3:bucket:test", "project", "app-1", "123456789012"
        )
        assert result1["key"] == "project"

        # Add second tag
        result2 = add_control_plane_tag(
            "s3:bucket:test", "environment", "dev", "123456789012"
        )
        assert result2["key"] == "environment"


class TestRemoveControlPlaneTag:
    """Test remove_control_plane_tag() operation."""

    @patch("control_plane.tagging.control_plane.get_graph")
    @patch("control_plane.tagging.control_plane.get_control_plane_tags")
    def test_remove_tag_success(self, mock_get_tags, mock_get_graph):
        """Removing existing tag should delete TAGGED_WITH relationship."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = [[1]]  # Deleted count = 1
        mock_graph.query.return_value = mock_result

        # Mock get_control_plane_tags for BEFORE/AFTER state
        mock_get_tags.side_effect = [{"project": "app-1"}, {}]  # before, after

        result = remove_control_plane_tag("s3:bucket:test", "project", "123456789012")

        assert result is True
        mock_graph.query.assert_called_once()

    @patch("control_plane.tagging.control_plane.get_graph")
    @patch("control_plane.tagging.control_plane.get_control_plane_tags")
    def test_remove_nonexistent_tag_idempotent(self, mock_get_tags, mock_get_graph):
        """Removing non-existent tag should be idempotent (no error)."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = [[0]]  # Deleted count = 0
        mock_graph.query.return_value = mock_result

        # Mock get_control_plane_tags for BEFORE/AFTER state
        mock_get_tags.side_effect = [{}, {}]  # no tags before or after

        result = remove_control_plane_tag("s3:bucket:test", "project", "123456789012")

        assert result is True  # Idempotent

    def test_remove_tag_invalid_tenant_id(self):
        """Removing tag with invalid tenant_id should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            remove_control_plane_tag("s3:bucket:test", "project", "invalid")


class TestGetControlPlaneTags:
    """Test get_control_plane_tags() operation."""

    @patch("control_plane.tagging.control_plane.get_graph")
    def test_get_tags_success(self, mock_get_graph):
        """Getting tags should return dict of key-value pairs."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = [
            ["project", "app-1"],
            ["environment", "dev"],
        ]
        mock_graph.query.return_value = mock_result

        result = get_control_plane_tags("s3:bucket:test", "123456789012")

        assert result == {"project": "app-1", "environment": "dev"}

    @patch("control_plane.tagging.control_plane.get_graph")
    def test_get_tags_no_tags(self, mock_get_graph):
        """Getting tags for resource with no tags should return empty dict."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = []
        mock_graph.query.return_value = mock_result

        result = get_control_plane_tags("s3:bucket:test", "123456789012")

        assert result == {}

    def test_get_tags_invalid_tenant_id(self):
        """Getting tags with invalid tenant_id should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            get_control_plane_tags("s3:bucket:test", "invalid")


class TestQueryResourcesByTag:
    """Test query_resources_by_tag() operation."""

    @patch("control_plane.tagging.control_plane.get_graph")
    def test_query_by_tag_success(self, mock_get_graph):
        """Querying by tag should return matching resources."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        # Mock result with resource nodes
        mock_node1 = MagicMock()
        mock_node1.properties = {
            "id": "s3:bucket:test",
            "type": "s3:bucket",
            "tenant_id": "123456789012",
        }

        mock_node2 = MagicMock()
        mock_node2.properties = {
            "id": "lambda:function:handler",
            "type": "lambda:function",
            "tenant_id": "123456789012",
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node1], [mock_node2]]
        mock_graph.query.return_value = mock_result

        result = query_resources_by_tag("project", "app-1", "123456789012")

        assert len(result) == 2
        assert result[0]["id"] == "s3:bucket:test"
        assert result[1]["id"] == "lambda:function:handler"

    @patch("control_plane.tagging.control_plane.get_graph")
    def test_query_by_tag_with_type_filter(self, mock_get_graph):
        """Querying by tag with type filter should apply type constraint."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_node = MagicMock()
        mock_node.properties = {
            "id": "s3:bucket:test",
            "type": "s3:bucket",
            "tenant_id": "123456789012",
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock_graph.query.return_value = mock_result

        result = query_resources_by_tag(
            "project", "app-1", "123456789012", resource_type="s3:bucket"
        )

        assert len(result) == 1
        assert result[0]["type"] == "s3:bucket"

        # Verify query includes type filter
        call_args = mock_graph.query.call_args
        assert "resource_type" in call_args[1]["params"]

    @patch("control_plane.tagging.control_plane.get_graph")
    def test_query_by_tag_no_matches(self, mock_get_graph):
        """Querying by tag with no matches should return empty list."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = []
        mock_graph.query.return_value = mock_result

        result = query_resources_by_tag("project", "nonexistent", "123456789012")

        assert result == []

    def test_query_by_tag_invalid_tenant_id(self):
        """Querying by tag with invalid tenant_id should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            query_resources_by_tag("project", "app-1", "invalid")
