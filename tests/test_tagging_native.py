"""
Unit tests for native tagging operations.

Tests native tag dual-write (FalkorDB + MiniStack) operations.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from control_plane.tagging.native import (
    validate_aws_tag,
    add_native_tag,
    remove_native_tag,
    get_native_tags,
    sync_native_tags_from_ministack,
    _extract_resource_components,
)
from control_plane.tagging.models import (
    MAX_TAG_KEY_LENGTH,
    MAX_TAG_VALUE_LENGTH,
    AWS_RESERVED_PREFIXES,
    TAGGABLE_SERVICES,
)


class TestValidateAwsTag:
    """Test AWS tag validation."""

    def test_valid_tag(self):
        """Valid AWS tags should not raise."""
        validate_aws_tag("Name", "my-bucket", is_native=True)
        validate_aws_tag("Environment", "prod", is_native=True)
        validate_aws_tag("team_name", "backend", is_native=True)

    def test_empty_key(self):
        """Empty key should raise ValueError."""
        with pytest.raises(ValueError, match="Tag key cannot be empty"):
            validate_aws_tag("", "value", is_native=True)

    def test_key_too_long(self):
        """Key exceeding MAX_TAG_KEY_LENGTH should raise ValueError."""
        long_key = "a" * (MAX_TAG_KEY_LENGTH + 1)
        with pytest.raises(ValueError, match=f"exceeds {MAX_TAG_KEY_LENGTH}"):
            validate_aws_tag(long_key, "value", is_native=True)

    def test_value_too_long(self):
        """Value exceeding MAX_TAG_VALUE_LENGTH should raise ValueError."""
        long_value = "a" * (MAX_TAG_VALUE_LENGTH + 1)
        with pytest.raises(ValueError, match=f"exceeds {MAX_TAG_VALUE_LENGTH}"):
            validate_aws_tag("key", long_value, is_native=True)

    def test_aws_reserved_prefix_blocked(self):
        """Native tags with aws: prefix should be blocked."""
        with pytest.raises(ValueError, match="reserved prefix"):
            validate_aws_tag("aws:cloudformation:stack", "value", is_native=True)

        with pytest.raises(ValueError, match="reserved prefix"):
            validate_aws_tag("AWS:Service", "value", is_native=True)

    def test_aws_reserved_prefix_allowed_for_control_plane(self):
        """Control-plane tags can use aws: prefix (is_native=False)."""
        # Should not raise
        validate_aws_tag("aws:cloudformation:stack", "value", is_native=False)

    def test_key_with_invalid_chars(self):
        """Key with disallowed characters should raise ValueError."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_aws_tag("project$name", "value", is_native=True)

    def test_max_length_keys_values(self):
        """Keys and values at max length should be valid."""
        max_key = "a" * MAX_TAG_KEY_LENGTH
        max_value = "b" * MAX_TAG_VALUE_LENGTH

        validate_aws_tag(max_key, max_value, is_native=True)  # Should not raise


class TestExtractResourceComponents:
    """Test resource ID component extraction."""

    def test_extract_s3_bucket(self):
        """Should extract s3:bucket type and bucket name."""
        result = _extract_resource_components("s3:bucket:my-bucket")

        assert result["type"] == "s3:bucket"
        assert result["name"] == "my-bucket"

    def test_extract_lambda_function(self):
        """Should extract lambda:function type and function name."""
        result = _extract_resource_components("lambda:function:handler")

        assert result["type"] == "lambda:function"
        assert result["name"] == "handler"

    def test_extract_dynamodb_table(self):
        """Should extract dynamodb:table type and table name."""
        result = _extract_resource_components("dynamodb:table:users")

        assert result["type"] == "dynamodb:table"
        assert result["name"] == "users"

    def test_invalid_format(self):
        """Invalid resource ID format should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid resource_id format"):
            _extract_resource_components("invalid")

        with pytest.raises(ValueError, match="Invalid resource_id format"):
            _extract_resource_components("s3:bucket")  # Missing name


class TestAddNativeTag:
    """Test add_native_tag() dual-write operation."""

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native._write_native_tag_to_ministack")
    @patch("control_plane.tagging.native.get_native_tags")
    @patch("control_plane.tagging.native.get_graph")
    async def test_add_tag_to_taggable_service(
        self, mock_get_graph, mock_get_tags, mock_write
    ):
        """Adding tag to S3 bucket should write to FalkorDB AND MiniStack."""
        # Mock graph operations
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        verify_result = MagicMock()
        verify_result.result_set = [[{"id": "s3:bucket:test"}]]

        tag_result = MagicMock()
        tag_result.result_set = [[{"key": "Name", "value": "uploads"}]]

        rel_result = MagicMock()
        rel_result.result_set = [[{"rel": "TAGGED_WITH"}]]

        mock_graph.query.side_effect = [verify_result, tag_result, rel_result]

        # Mock get_native_tags: called 3 times (BEFORE, during write, AFTER)
        mock_get_tags.side_effect = [{}, {"Name": "uploads"}, {"Name": "uploads"}]

        # Mock boto3 write
        mock_write.return_value = AsyncMock()

        result = await add_native_tag(
            "s3:bucket:test", "Name", "uploads", "123456789012"
        )

        assert result["resource_id"] == "s3:bucket:test"
        assert result["key"] == "Name"
        assert result["value"] == "uploads"
        assert result["boto3_written"] is True

        # Verify boto3 write was called
        mock_write.assert_called_once()

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native.get_native_tags")
    @patch("control_plane.tagging.native.get_graph")
    async def test_add_tag_to_non_taggable_service(self, mock_get_graph, mock_get_tags):
        """Adding tag to non-taggable service (SQS) should store in FalkorDB only."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        verify_result = MagicMock()
        verify_result.result_set = [[{"id": "sqs:queue:tasks"}]]

        tag_result = MagicMock()
        tag_result.result_set = [[{"key": "Name", "value": "task-queue"}]]

        rel_result = MagicMock()
        rel_result.result_set = [[{"rel": "TAGGED_WITH"}]]

        mock_graph.query.side_effect = [verify_result, tag_result, rel_result]

        # Mock get_native_tags for BEFORE/AFTER state
        mock_get_tags.side_effect = [{}, {"Name": "task-queue"}]

        result = await add_native_tag(
            "sqs:queue:tasks", "Name", "task-queue", "123456789012"
        )

        assert result["boto3_written"] is False  # Not written to MiniStack

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native._write_native_tag_to_ministack")
    @patch("control_plane.tagging.native.get_native_tags")
    @patch("control_plane.tagging.native.get_graph")
    async def test_add_tag_boto3_failure_partial_success(
        self, mock_get_graph, mock_get_tags, mock_write
    ):
        """If boto3 write fails, FalkorDB update should still succeed."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        verify_result = MagicMock()
        verify_result.result_set = [[{"id": "s3:bucket:test"}]]

        tag_result = MagicMock()
        tag_result.result_set = [[{"key": "Name", "value": "uploads"}]]

        rel_result = MagicMock()
        rel_result.result_set = [[{"rel": "TAGGED_WITH"}]]

        mock_graph.query.side_effect = [verify_result, tag_result, rel_result]

        # Mock get_native_tags: called 3 times (BEFORE, during failed write attempt, AFTER)
        mock_get_tags.side_effect = [{}, {"Name": "uploads"}, {"Name": "uploads"}]

        # Mock boto3 write failure
        mock_write.side_effect = Exception("MiniStack unavailable")

        result = await add_native_tag(
            "s3:bucket:test", "Name", "uploads", "123456789012"
        )

        assert result["boto3_written"] is False  # Partial success
        # FalkorDB update succeeded, boto3 failed

    @pytest.mark.asyncio
    async def test_add_tag_aws_reserved_prefix_blocked(self):
        """Adding native tag with aws: prefix should raise ValueError."""
        with pytest.raises(ValueError, match="reserved prefix"):
            await add_native_tag(
                "s3:bucket:test", "aws:cloudformation:stack", "value", "123456789012"
            )

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native.get_graph")
    async def test_add_tag_resource_not_found(self, mock_get_graph):
        """Adding tag to non-existent resource should raise ValueError."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        verify_result = MagicMock()
        verify_result.result_set = []  # Resource not found
        mock_graph.query.return_value = verify_result

        with pytest.raises(ValueError, match="Resource .* not found"):
            await add_native_tag(
                "s3:bucket:nonexistent", "Name", "value", "123456789012"
            )


class TestRemoveNativeTag:
    """Test remove_native_tag() dual-delete operation."""

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native._write_native_tag_to_ministack")
    @patch("control_plane.tagging.native.get_native_tags")
    @patch("control_plane.tagging.native.get_graph")
    async def test_remove_tag_success(self, mock_get_graph, mock_get_tags, mock_write):
        """Removing tag should delete from FalkorDB AND update MiniStack."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        delete_result = MagicMock()
        delete_result.result_set = [[1]]  # Deleted count = 1
        mock_graph.query.return_value = delete_result

        # Mock get_native_tags: called 3 times (BEFORE, during write, AFTER)
        mock_get_tags.side_effect = [{"Name": "uploads"}, {}, {}]

        # Mock boto3 write
        mock_write.return_value = AsyncMock()

        result = await remove_native_tag("s3:bucket:test", "Name", "123456789012")

        assert result is True
        # Verify boto3 write was called with remaining tags (empty in this case)
        mock_write.assert_called_once()

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native.get_native_tags")
    @patch("control_plane.tagging.native.get_graph")
    async def test_remove_tag_idempotent(self, mock_get_graph, mock_get_tags):
        """Removing non-existent tag should be idempotent."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        delete_result = MagicMock()
        delete_result.result_set = [[0]]  # Deleted count = 0
        mock_graph.query.return_value = delete_result

        # Mock get_native_tags for BEFORE/AFTER state
        mock_get_tags.side_effect = [{}, {}]  # no tags before or after

        result = await remove_native_tag("s3:bucket:test", "Name", "123456789012")

        assert result is True  # Idempotent

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native._write_native_tag_to_ministack")
    @patch("control_plane.tagging.native.get_native_tags")
    @patch("control_plane.tagging.native.get_graph")
    async def test_remove_tag_boto3_failure_partial_success(
        self, mock_get_graph, mock_get_tags, mock_write
    ):
        """If boto3 update fails, FalkorDB deletion should still succeed."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        delete_result = MagicMock()
        delete_result.result_set = [[1]]  # Deleted count = 1
        mock_graph.query.return_value = delete_result

        # Mock get_native_tags: called 3 times (BEFORE, during failed write attempt, AFTER)
        mock_get_tags.side_effect = [{"Name": "uploads"}, {}, {}]

        # Mock boto3 write failure
        mock_write.side_effect = Exception("MiniStack unavailable")

        result = await remove_native_tag("s3:bucket:test", "Name", "123456789012")

        assert result is True  # FalkorDB deletion succeeded


class TestGetNativeTags:
    """Test get_native_tags() operation."""

    @patch("control_plane.tagging.native.get_graph")
    def test_get_tags_success(self, mock_get_graph):
        """Getting native tags should return dict of key-value pairs."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = [
            ["Name", "uploads"],
            ["Environment", "prod"],
        ]
        mock_graph.query.return_value = mock_result

        result = get_native_tags("s3:bucket:test", "123456789012")

        assert result == {"Name": "uploads", "Environment": "prod"}

    @patch("control_plane.tagging.native.get_graph")
    def test_get_tags_no_tags(self, mock_get_graph):
        """Getting tags for resource with no native tags should return empty dict."""
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        mock_result = MagicMock()
        mock_result.result_set = []
        mock_graph.query.return_value = mock_result

        result = get_native_tags("s3:bucket:test", "123456789012")

        assert result == {}


class TestSyncNativeTagsFromMinistack:
    """Test sync_native_tags_from_ministack() operation."""

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native.add_native_tag")
    @patch("control_plane.tagging.native.MiniStackClient")
    async def test_sync_s3_bucket_tags(self, mock_client_class, mock_add_tag):
        """Syncing S3 bucket should read from MiniStack and write to FalkorDB."""
        # Mock MiniStack client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_session = MagicMock()
        mock_client._get_session.return_value = mock_session

        # Mock S3 get_bucket_tagging response
        mock_s3 = MagicMock()
        mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_s3.__aexit__ = AsyncMock(return_value=None)
        mock_s3.get_bucket_tagging = AsyncMock(
            return_value={"TagSet": [{"Key": "Name", "Value": "uploads"}]}
        )

        mock_session.client.return_value = mock_s3

        # Mock add_native_tag
        mock_add_tag.return_value = {"resource_id": "s3:bucket:test"}

        result = await sync_native_tags_from_ministack(
            "s3:bucket:test", "123456789012"
        )

        assert result["synced_count"] == 1
        assert result["skipped_count"] == 0
        assert result["error"] is None

        # Verify add_native_tag was called
        mock_add_tag.assert_called_once_with(
            "s3:bucket:test", "Name", "uploads", "123456789012"
        )

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native.add_native_tag")
    @patch("control_plane.tagging.native.MiniStackClient")
    async def test_sync_with_invalid_keys_skipped(self, mock_client_class, mock_add_tag):
        """Syncing should skip invalid keys from MiniStack and continue."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_session = MagicMock()
        mock_client._get_session.return_value = mock_session

        # Mock S3 response with mixed valid/invalid tags
        mock_s3 = MagicMock()
        mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_s3.__aexit__ = AsyncMock(return_value=None)
        mock_s3.get_bucket_tagging = AsyncMock(
            return_value={
                "TagSet": [
                    {"Key": "Name", "Value": "uploads"},
                    {"Key": "invalid$key", "Value": "value"},  # Invalid
                    {"Key": "Environment", "Value": "prod"},
                ]
            }
        )

        mock_session.client.return_value = mock_s3

        # Mock add_native_tag: success for valid, ValueError for invalid
        def add_tag_side_effect(resource_id, key, value, tenant_id):
            if "$" in key:
                raise ValueError("invalid characters")
            return {"resource_id": resource_id}

        mock_add_tag.side_effect = add_tag_side_effect

        result = await sync_native_tags_from_ministack(
            "s3:bucket:test", "123456789012"
        )

        assert result["synced_count"] == 2  # Name and Environment
        assert result["skipped_count"] == 1  # invalid$key
        assert "invalid$key" in result["skipped_keys"]
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_sync_non_taggable_service(self):
        """Syncing non-taggable service should raise ValueError."""
        with pytest.raises(ValueError, match="does not support native tagging"):
            await sync_native_tags_from_ministack("sqs:queue:tasks", "123456789012")

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native.MiniStackClient")
    async def test_sync_ministack_error(self, mock_client_class):
        """Syncing with MiniStack error should return error in result."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_session = MagicMock()
        mock_client._get_session.return_value = mock_session

        # Mock S3 error
        mock_s3 = MagicMock()
        mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_s3.__aexit__ = AsyncMock(return_value=None)
        mock_s3.get_bucket_tagging = AsyncMock(
            side_effect=Exception("MiniStack unavailable")
        )

        mock_session.client.return_value = mock_s3

        result = await sync_native_tags_from_ministack(
            "s3:bucket:test", "123456789012"
        )

        assert result["synced_count"] == 0
        assert result["error"] is not None
        assert "MiniStack unavailable" in result["error"]
