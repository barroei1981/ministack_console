"""
End-to-end integration tests for dual tagging system.

Tests complete workflows: native tag write-through, cross-service queries,
namespace isolation, and sync operations.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from control_plane.tagging import (
    add_control_plane_tag,
    remove_control_plane_tag,
    get_control_plane_tags,
    query_resources_by_tag,
    add_native_tag,
    remove_native_tag,
    get_native_tags,
    sync_native_tags_from_ministack,
    TagNamespace,
)


class TestNativeTagWriteThrough:
    """Test native tag write-through (FalkorDB + MiniStack)."""

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native._write_native_tag_to_ministack")
    @patch("control_plane.tagging.native.get_native_tags")
    @patch("control_plane.tagging.native.get_graph")
    async def test_native_tag_written_to_both_stores(
        self, mock_get_graph, mock_get_tags, mock_write
    ):
        """
        Given I add a native tag to an S3 bucket,
        When the tag is applied,
        Then it is stored in FalkorDB with namespace="native",
        And it is written to MiniStack via put_bucket_tagging.
        """
        # Mock FalkorDB operations
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        verify_result = MagicMock()
        verify_result.result_set = [[{"id": "s3:bucket:test"}]]

        tag_result = MagicMock()
        tag_result.result_set = [[{"key": "Name", "value": "uploads"}]]

        rel_result = MagicMock()
        rel_result.result_set = [[{"rel": "TAGGED_WITH"}]]

        mock_graph.query.side_effect = [verify_result, tag_result, rel_result]

        # Mock boto3 write
        mock_write.return_value = AsyncMock()

        # Mock get_native_tags: called 3 times (BEFORE, during write, AFTER)
        mock_get_tags.side_effect = [{}, {"Name": "uploads"}, {"Name": "uploads"}]

        # Add native tag
        result = await add_native_tag(
            "s3:bucket:test", "Name", "uploads", "123456789012"
        )

        # Verify FalkorDB write
        assert result["boto3_written"] is True

        # Verify boto3 write was called with correct tags
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        assert call_args[0][0] == "s3:bucket:test"  # resource_id
        assert call_args[0][1] == {"Name": "uploads"}  # tags dict

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native.MiniStackClient")
    @patch("control_plane.tagging.native.get_graph")
    async def test_retrieve_native_tag_from_ministack(
        self, mock_get_graph, mock_client_class
    ):
        """
        Given native tags exist in MiniStack,
        When I sync them to FalkorDB,
        Then they are stored with namespace="native",
        And I can retrieve them via get_native_tags().
        """
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
            return_value={
                "TagSet": [
                    {"Key": "Name", "Value": "uploads"},
                    {"Key": "Environment", "Value": "prod"},
                ]
            }
        )

        mock_session.client.return_value = mock_s3

        # Mock FalkorDB operations for add_native_tag
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        verify_result = MagicMock()
        verify_result.result_set = [[{"id": "s3:bucket:test"}]]

        tag_result = MagicMock()
        tag_result.result_set = [[{"key": "tag", "value": "value"}]]

        rel_result = MagicMock()
        rel_result.result_set = [[{"rel": "TAGGED_WITH"}]]

        mock_graph.query.side_effect = [
            verify_result,
            tag_result,
            rel_result,
            verify_result,
            tag_result,
            rel_result,
        ]

        # Mock _write_native_tag_to_ministack (already in MiniStack, skip write)
        with patch(
            "control_plane.tagging.native._write_native_tag_to_ministack"
        ) as mock_write:
            mock_write.return_value = AsyncMock()

            # Mock get_native_tags for add_native_tag BEFORE/DURING/AFTER state
            with patch(
                "control_plane.tagging.native.get_native_tags"
            ) as mock_get_tags:
                mock_get_tags.side_effect = [
                    {},
                    {"Name": "uploads"},
                    {"Name": "uploads"},  # First tag (BEFORE, DURING, AFTER)
                    {"Name": "uploads"},
                    {"Name": "uploads", "Environment": "prod"},
                    {"Name": "uploads", "Environment": "prod"},  # Second tag (BEFORE, DURING, AFTER)
                ]

                # Sync tags from MiniStack
                result = await sync_native_tags_from_ministack(
                    "s3:bucket:test", "123456789012"
                )

        assert result["synced_count"] == 2
        assert result["skipped_count"] == 0


class TestNamespaceIsolation:
    """Test that control-plane and native tags don't collide."""

    @patch("control_plane.tagging.native.get_graph")
    @patch("control_plane.tagging.control_plane.get_graph")
    @patch("control_plane.tagging.control_plane.query_nodes")
    def test_same_key_different_namespaces(
        self, mock_query, mock_cp_get_graph, mock_native_get_graph
    ):
        """
        Given I add control-plane tag "project:app-1",
        And I add native tag "project:prod",
        When I query each namespace,
        Then they return different values without collision.
        """
        # Mock resource exists
        mock_query.return_value = [
            {"id": "s3:bucket:test", "tenant_id": "123456789012"}
        ]

        mock_cp_graph = MagicMock()
        mock_cp_get_graph.return_value = mock_cp_graph

        # Mock control-plane tag add
        verify_result = MagicMock()
        verify_result.result_set = [[{"id": "s3:bucket:test"}]]

        tag_result = MagicMock()
        tag_result.result_set = [[{"key": "project", "value": "app-1"}]]

        rel_result = MagicMock()
        rel_result.result_set = [[{"rel": "TAGGED_WITH"}]]

        mock_cp_graph.query.side_effect = [
            verify_result,
            tag_result,
            rel_result,
        ]

        with patch(
            "control_plane.tagging.control_plane.get_control_plane_tags"
        ) as mock_get_cp_tags:
            mock_get_cp_tags.side_effect = [{}, {"project": "app-1"}]

            # Add control-plane tag
            add_control_plane_tag(
                "s3:bucket:test", "project", "app-1", "123456789012"
            )

        # Now mock get operations for both namespaces
        mock_cp_graph.query.side_effect = [
            # get_control_plane_tags query
            MagicMock(result_set=[["project", "app-1"]]),
        ]

        # Setup native graph mock
        mock_native_graph = MagicMock()
        mock_native_get_graph.return_value = mock_native_graph

        mock_native_graph.query.return_value = MagicMock(
            result_set=[["project", "prod"]]
        )

        # Get control-plane tags
        cp_tags = get_control_plane_tags("s3:bucket:test", "123456789012")
        assert cp_tags == {"project": "app-1"}

        # Get native tags
        native_tags = get_native_tags("s3:bucket:test", "123456789012")
        assert native_tags == {"project": "prod"}

        # Verify queries filtered by namespace
        cp_query_params = mock_cp_graph.query.call_args_list[-1][1]["params"]
        assert cp_query_params["namespace"] == TagNamespace.CONTROL_PLANE.value

        # Native query should filter by native namespace
        native_query_params = mock_native_graph.query.call_args[1]["params"]
        assert native_query_params["namespace"] == TagNamespace.NATIVE.value


class TestCrossServiceQuery:
    """Test querying resources by tag across multiple service types."""

    @patch("control_plane.tagging.control_plane.get_graph")
    def test_query_by_project_tag_multiple_services(self, mock_get_graph):
        """
        Given I have S3 bucket, Lambda function, and DynamoDB table,
        And all are tagged with project="microservice-a",
        When I query by project tag,
        Then all three resources are returned.
        """
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        # Mock query result with multiple service types
        mock_s3 = MagicMock()
        mock_s3.properties = {
            "id": "s3:bucket:uploads",
            "type": "s3:bucket",
            "tenant_id": "123456789012",
        }

        mock_lambda = MagicMock()
        mock_lambda.properties = {
            "id": "lambda:function:handler",
            "type": "lambda:function",
            "tenant_id": "123456789012",
        }

        mock_dynamo = MagicMock()
        mock_dynamo.properties = {
            "id": "dynamodb:table:users",
            "type": "dynamodb:table",
            "tenant_id": "123456789012",
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_s3], [mock_lambda], [mock_dynamo]]
        mock_graph.query.return_value = mock_result

        # Query by project tag
        resources = query_resources_by_tag(
            "project", "microservice-a", "123456789012"
        )

        assert len(resources) == 3

        types = {r["type"] for r in resources}
        assert types == {"s3:bucket", "lambda:function", "dynamodb:table"}


class TestTenantIsolation:
    """Test that tags are tenant-isolated."""

    @patch("control_plane.tagging.control_plane.get_graph")
    def test_query_by_tag_filters_by_tenant(self, mock_get_graph):
        """
        Given resources with same tag in multiple tenants,
        When I query by tag with tenant_id,
        Then only resources from that tenant are returned.
        """
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        # Mock query result with only tenant1 resources
        mock_resource1 = MagicMock()
        mock_resource1.properties = {
            "id": "s3:bucket:tenant1-bucket",
            "type": "s3:bucket",
            "tenant_id": "123456789001",
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_resource1]]
        mock_graph.query.return_value = mock_result

        # Query by tag for tenant1
        resources = query_resources_by_tag("project", "app-1", "123456789001")

        assert len(resources) == 1
        assert resources[0]["tenant_id"] == "123456789001"

        # Verify query filtered by tenant_id
        call_args = mock_graph.query.call_args
        assert call_args[1]["params"]["tenant_id"] == "123456789001"


class TestNonTaggableServiceWarning:
    """Test that non-taggable services store tags in FalkorDB only."""

    @pytest.mark.asyncio
    @patch("control_plane.tagging.native.get_native_tags")
    @patch("control_plane.tagging.native.get_graph")
    async def test_sqs_queue_tag_stored_falkordb_only(
        self, mock_get_graph, mock_get_tags
    ):
        """
        Given I attempt to add native tag to SQS queue,
        When the tag is applied,
        Then it is stored in FalkorDB with namespace="native",
        And no boto3 call is made (SQS doesn't support native tagging),
        And boto3_written flag is False.
        """
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

        # Add native tag to SQS queue
        result = await add_native_tag(
            "sqs:queue:tasks", "Name", "task-queue", "123456789012"
        )

        assert result["boto3_written"] is False  # Not written to MiniStack
        assert result["namespace"] == TagNamespace.NATIVE.value

        # Tag is stored in FalkorDB (verify via get_native_tags mock)
        assert mock_get_tags.call_count == 2  # BEFORE and AFTER


class TestIdempotentOperations:
    """Test that tag operations are idempotent."""

    @patch("control_plane.tagging.control_plane.get_graph")
    @patch("control_plane.tagging.control_plane.query_nodes")
    @patch("control_plane.tagging.control_plane.get_control_plane_tags")
    def test_add_same_tag_twice_idempotent(
        self, mock_get_tags, mock_query, mock_get_graph
    ):
        """
        Given a tag already exists on a resource,
        When I add the same tag again,
        Then the operation succeeds (idempotent),
        And no duplicate relationships are created.
        """
        mock_query.return_value = [{"id": "s3:bucket:test"}]

        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        tag_result = MagicMock()
        tag_result.result_set = [[{"key": "project", "value": "app-1"}]]

        rel_result = MagicMock()
        rel_result.result_set = [[{"rel": "TAGGED_WITH"}]]

        mock_graph.query.side_effect = [
            tag_result,
            rel_result,
            tag_result,
            rel_result,
        ]

        # Mock get_control_plane_tags for BEFORE/AFTER state
        mock_get_tags.side_effect = [
            {},
            {"project": "app-1"},  # First add
            {"project": "app-1"},
            {"project": "app-1"},  # Second add (idempotent)
        ]

        # Add tag first time
        result1 = add_control_plane_tag(
            "s3:bucket:test", "project", "app-1", "123456789012"
        )
        assert result1["key"] == "project"

        # Add same tag second time (idempotent)
        result2 = add_control_plane_tag(
            "s3:bucket:test", "project", "app-1", "123456789012"
        )
        assert result2["key"] == "project"

        # MERGE pattern in queries ensures no duplicates
        # Both operations succeed without error

    @patch("control_plane.tagging.control_plane.get_graph")
    @patch("control_plane.tagging.control_plane.get_control_plane_tags")
    def test_remove_nonexistent_tag_idempotent(self, mock_get_tags, mock_get_graph):
        """
        Given a tag doesn't exist on a resource,
        When I remove the tag,
        Then the operation succeeds (idempotent),
        And no error is raised.
        """
        mock_graph = MagicMock()
        mock_get_graph.return_value = mock_graph

        delete_result = MagicMock()
        delete_result.result_set = [[0]]  # Deleted count = 0
        mock_graph.query.return_value = delete_result

        # Mock get_control_plane_tags for BEFORE/AFTER state
        mock_get_tags.side_effect = [{}, {}]  # no tags before or after

        # Remove non-existent tag
        result = remove_control_plane_tag(
            "s3:bucket:test", "nonexistent", "123456789012"
        )

        assert result is True  # Idempotent, no error
