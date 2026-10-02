"""
End-to-end integration tests for dependency detection.

Tests the full flow: resource creation → polling → dependency detection → FalkorDB storage.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from control_plane.dependencies.manager import sync_all_dependencies


@pytest.mark.asyncio
class TestDependenciesE2E:
    """End-to-end tests for dependency detection and storage."""

    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.query_nodes")
    @patch("control_plane.dependencies.manager.create_relationship")
    async def test_lambda_s3_dependency_created_on_poll(
        self, mock_create_rel, mock_query_nodes, mock_query_rels
    ):
        """
        Test AC1: Lambda with S3 env var → poll → verify DEPENDS_ON in FalkorDB.

        Given a Lambda function has environment variable "BUCKET_NAME=arn:aws:s3:::my-bucket",
        when dependency detection runs, then a (:Lambda)-[:DEPENDS_ON]->(:S3) relationship
        is created in FalkorDB.
        """
        # Setup: Lambda resource with S3 ARN in env var
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock MiniStack client responses
        mock_client = Mock()
        mock_client.get_lambda_function_config = AsyncMock(
            return_value={
                "Environment": {
                    "Variables": {
                        "BUCKET_NAME": "arn:aws:s3:::my-bucket",
                    }
                }
            }
        )
        mock_client.list_event_source_mappings = AsyncMock(return_value=[])

        # Mock FalkorDB: no existing relationships, target S3 bucket exists
        mock_query_rels.return_value = []
        mock_query_nodes.return_value = [
            {"id": "arn:aws:s3:::my-bucket", "tenant_id": "000000000000"}
        ]

        # Execute: Run dependency sync (simulates polling cycle)
        stats = await sync_all_dependencies([lambda_resource], mock_client)

        # Verify: Dependency was created
        assert stats["dependencies_created"] == 1
        assert stats["dependencies_deleted"] == 0
        assert stats["resources_processed"] == 1

        # Verify create_relationship was called with correct parameters
        mock_create_rel.assert_called_once()
        call_args = mock_create_rel.call_args
        assert call_args[1]["from_node_id"] == lambda_resource["id"]
        assert call_args[1]["to_node_id"] == "arn:aws:s3:::my-bucket"
        assert call_args[1]["rel_type"] == "DEPENDS_ON"
        assert call_args[1]["properties"]["type"] == "environment_variable"

    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.soft_delete_relationship")
    async def test_lambda_s3_dependency_deleted_on_env_var_removal(
        self, mock_soft_delete_rel, mock_query_rels
    ):
        """
        Test AC4: Lambda env var removed → poll → verify DEPENDS_ON soft-deleted.

        Given a Lambda env var referencing S3 is removed, when dependency detection runs,
        then the existing DEPENDS_ON relationship is soft-deleted from FalkorDB.
        """
        # Setup: Lambda resource with NO S3 env vars
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock MiniStack client: Lambda now has no S3 env vars
        mock_client = Mock()
        mock_client.get_lambda_function_config = AsyncMock(
            return_value={"Environment": {"Variables": {}}}
        )
        mock_client.list_event_source_mappings = AsyncMock(return_value=[])

        # Mock FalkorDB: existing DEPENDS_ON relationship exists
        mock_query_rels.return_value = [
            {
                "from_node_id": lambda_resource["id"],
                "to_node_id": "arn:aws:s3:::my-bucket",
                "rel_type": "DEPENDS_ON",
                "properties": {
                    "type": "environment_variable",
                    "metadata": {"bucket_name": "my-bucket"},
                },
            }
        ]

        # Execute: Run dependency sync (simulates polling after env var removed)
        stats = await sync_all_dependencies([lambda_resource], mock_client)

        # Verify: Dependency was soft-deleted
        assert stats["dependencies_created"] == 0
        assert stats["dependencies_deleted"] == 1
        assert stats["resources_processed"] == 1

        # Verify soft_delete_relationship was called
        mock_soft_delete_rel.assert_called_once()
        call_args = mock_soft_delete_rel.call_args
        assert call_args[1]["from_node_id"] == lambda_resource["id"]
        assert call_args[1]["to_node_id"] == "arn:aws:s3:::my-bucket"
        assert call_args[1]["rel_type"] == "DEPENDS_ON"

    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.query_nodes")
    @patch("control_plane.dependencies.manager.create_relationship")
    async def test_sqs_event_source_dependency_created(
        self, mock_create_rel, mock_query_nodes, mock_query_rels
    ):
        """
        Test AC2: Lambda with SQS event source → poll → verify DEPENDS_ON created.

        Given a Lambda function has an SQS event source mapping, when dependency
        detection runs, then a DEPENDS_ON relationship is created from Lambda to SQS
        with metadata including the mapping UUID.
        """
        # Setup: Lambda resource with SQS event source
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock MiniStack client responses
        mock_client = Mock()
        mock_client.get_lambda_function_config = AsyncMock(
            return_value={"Environment": {}}
        )
        mock_client.list_event_source_mappings = AsyncMock(
            return_value=[
                {
                    "UUID": "mapping-123",
                    "EventSourceArn": "arn:aws:sqs:us-east-1:000000000000:my-queue",
                    "State": "Enabled",
                }
            ]
        )

        # Mock FalkorDB: no existing relationships, target SQS queue exists
        mock_query_rels.return_value = []
        mock_query_nodes.return_value = [
            {"id": "arn:aws:sqs:us-east-1:000000000000:my-queue", "tenant_id": "000000000000"}
        ]

        # Execute: Run dependency sync
        stats = await sync_all_dependencies([lambda_resource], mock_client)

        # Verify: Dependency was created
        assert stats["dependencies_created"] == 1
        mock_create_rel.assert_called_once()

        call_args = mock_create_rel.call_args
        assert call_args[1]["properties"]["type"] == "event_source_mapping"
        assert call_args[1]["properties"]["metadata"]["mapping_uuid"] == "mapping-123"
