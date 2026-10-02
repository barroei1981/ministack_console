"""
Unit tests for dependency manager.

Tests dependency sync logic and tenant isolation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from control_plane.dependencies.manager import sync_all_dependencies
from control_plane.dependencies.models import Dependency, DependencyType


@pytest.mark.asyncio
class TestDependencySync:
    """Test dependency sync logic."""

    @patch("control_plane.dependencies.manager.detect_lambda_s3_dependencies")
    @patch("control_plane.dependencies.manager.detect_lambda_event_sources")
    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.query_nodes")
    @patch("control_plane.dependencies.manager.create_relationship")
    async def test_sync_creates_new_dependency(
        self,
        mock_create_rel,
        mock_query_nodes,
        mock_query_rels,
        mock_detect_events,
        mock_detect_s3,
    ):
        """Test that sync creates new dependencies."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock detection: Lambda depends on S3
        mock_detect_s3.return_value = [
            Dependency(
                source_id=lambda_resource["id"],
                target_id="arn:aws:s3:::my-bucket",
                type=DependencyType.ENVIRONMENT_VARIABLE,
                metadata={"env_var_name": "BUCKET", "bucket_name": "my-bucket"},
            )
        ]
        mock_detect_events.return_value = []

        # Mock existing: no existing dependencies
        mock_query_rels.return_value = []

        # Mock target node exists with same tenant
        mock_query_nodes.return_value = [
            {"id": "arn:aws:s3:::my-bucket", "tenant_id": "000000000000"}
        ]

        mock_client = Mock()
        resources = [lambda_resource]

        stats = await sync_all_dependencies(resources, mock_client)

        # Should create the new dependency
        assert stats["dependencies_created"] == 1
        assert stats["dependencies_deleted"] == 0
        assert stats["resources_processed"] == 1
        mock_create_rel.assert_called_once()

    @patch("control_plane.dependencies.manager.detect_lambda_s3_dependencies")
    @patch("control_plane.dependencies.manager.detect_lambda_event_sources")
    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.soft_delete_relationship")
    async def test_sync_deletes_stale_dependency(
        self,
        mock_soft_delete_rel,
        mock_query_rels,
        mock_detect_events,
        mock_detect_s3,
    ):
        """Test that sync soft-deletes stale dependencies."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock detection: no dependencies found
        mock_detect_s3.return_value = []
        mock_detect_events.return_value = []

        # Mock existing: one stale dependency
        mock_query_rels.return_value = [
            {
                "from_node_id": lambda_resource["id"],
                "to_node_id": "arn:aws:s3:::old-bucket",
                "rel_type": "DEPENDS_ON",
                "properties": {
                    "type": "environment_variable",
                    "metadata": {"bucket_name": "old-bucket"},
                },
            }
        ]

        mock_client = Mock()
        resources = [lambda_resource]

        stats = await sync_all_dependencies(resources, mock_client)

        # Should soft-delete the stale dependency
        assert stats["dependencies_created"] == 0
        assert stats["dependencies_deleted"] == 1
        mock_soft_delete_rel.assert_called_once()

    @patch("control_plane.dependencies.manager.detect_lambda_s3_dependencies")
    @patch("control_plane.dependencies.manager.detect_lambda_event_sources")
    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.query_nodes")
    @patch("control_plane.dependencies.manager.create_relationship")
    async def test_sync_blocks_cross_tenant_dependency(
        self,
        mock_create_rel,
        mock_query_nodes,
        mock_query_rels,
        mock_detect_events,
        mock_detect_s3,
    ):
        """Test that cross-tenant dependencies are blocked."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock detection: Lambda depends on S3 in different tenant
        mock_detect_s3.return_value = [
            Dependency(
                source_id=lambda_resource["id"],
                target_id="arn:aws:s3:::other-bucket",
                type=DependencyType.ENVIRONMENT_VARIABLE,
                metadata={"env_var_name": "BUCKET", "bucket_name": "other-bucket"},
            )
        ]
        mock_detect_events.return_value = []

        # Mock existing: no existing dependencies
        mock_query_rels.return_value = []

        # Mock target node exists but with DIFFERENT tenant
        mock_query_nodes.return_value = [
            {"id": "arn:aws:s3:::other-bucket", "tenant_id": "111111111111"}
        ]

        mock_client = Mock()
        resources = [lambda_resource]

        stats = await sync_all_dependencies(resources, mock_client)

        # Should NOT create the cross-tenant dependency
        assert stats["dependencies_created"] == 0
        mock_create_rel.assert_not_called()

    @patch("control_plane.dependencies.manager.detect_lambda_s3_dependencies")
    @patch("control_plane.dependencies.manager.detect_lambda_event_sources")
    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.query_nodes")
    @patch("control_plane.dependencies.manager.create_relationship")
    async def test_sync_skips_missing_target(
        self,
        mock_create_rel,
        mock_query_nodes,
        mock_query_rels,
        mock_detect_events,
        mock_detect_s3,
    ):
        """Test that dependencies to missing targets are skipped."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock detection: Lambda depends on S3 that doesn't exist
        mock_detect_s3.return_value = [
            Dependency(
                source_id=lambda_resource["id"],
                target_id="arn:aws:s3:::missing-bucket",
                type=DependencyType.ENVIRONMENT_VARIABLE,
                metadata={"env_var_name": "BUCKET", "bucket_name": "missing-bucket"},
            )
        ]
        mock_detect_events.return_value = []

        # Mock existing: no existing dependencies
        mock_query_rels.return_value = []

        # Mock target node NOT found
        mock_query_nodes.return_value = []

        mock_client = Mock()
        resources = [lambda_resource]

        stats = await sync_all_dependencies(resources, mock_client)

        # Should NOT create dependency to missing target
        assert stats["dependencies_created"] == 0
        mock_create_rel.assert_not_called()

    @patch("control_plane.dependencies.manager.detect_lambda_s3_dependencies")
    @patch("control_plane.dependencies.manager.detect_lambda_event_sources")
    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.query_nodes")
    @patch("control_plane.dependencies.manager.create_relationship")
    async def test_sync_preserves_existing_dependency(
        self,
        mock_create_rel,
        mock_query_nodes,
        mock_query_rels,
        mock_detect_events,
        mock_detect_s3,
    ):
        """Test that existing dependencies are preserved if still detected."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock detection: Lambda still depends on S3
        mock_detect_s3.return_value = [
            Dependency(
                source_id=lambda_resource["id"],
                target_id="arn:aws:s3:::my-bucket",
                type=DependencyType.ENVIRONMENT_VARIABLE,
                metadata={"env_var_name": "BUCKET", "bucket_name": "my-bucket"},
            )
        ]
        mock_detect_events.return_value = []

        # Mock existing: same dependency already exists
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

        mock_client = Mock()
        resources = [lambda_resource]

        stats = await sync_all_dependencies(resources, mock_client)

        # Should not create or delete anything
        assert stats["dependencies_created"] == 0
        assert stats["dependencies_deleted"] == 0
        mock_create_rel.assert_not_called()

    @patch("control_plane.dependencies.manager.detect_s3_iam_dependencies")
    @patch("control_plane.dependencies.manager.query_relationships")
    @patch("control_plane.dependencies.manager.query_nodes")
    @patch("control_plane.dependencies.manager.create_relationship")
    async def test_sync_s3_dependencies(
        self,
        mock_create_rel,
        mock_query_nodes,
        mock_query_rels,
        mock_detect_iam,
    ):
        """Test syncing S3→IAM dependencies."""
        s3_resource = {
            "id": "arn:aws:s3:::my-bucket",
            "name": "my-bucket",
            "type": "s3:bucket",
            "tenant_id": "000000000000",
        }

        # Mock detection: S3 depends on IAM role
        mock_detect_iam.return_value = [
            Dependency(
                source_id=s3_resource["id"],
                target_id="arn:aws:iam::000000000000:role/MyRole",
                type=DependencyType.BUCKET_POLICY,
                metadata={"role_name": "MyRole", "effect": "Allow"},
            )
        ]

        # Mock existing: no existing dependencies
        mock_query_rels.return_value = []

        # Mock target node exists with same tenant
        mock_query_nodes.return_value = [
            {"id": "arn:aws:iam::000000000000:role/MyRole", "tenant_id": "000000000000"}
        ]

        mock_client = Mock()
        resources = [s3_resource]

        stats = await sync_all_dependencies(resources, mock_client)

        # Should create the new dependency
        assert stats["dependencies_created"] == 1
        assert stats["resources_processed"] == 1
        mock_create_rel.assert_called_once()

    @patch("control_plane.dependencies.manager.detect_lambda_s3_dependencies")
    async def test_sync_handles_detection_error(
        self,
        mock_detect_s3,
    ):
        """Test that sync handles detection errors gracefully."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
            "tenant_id": "000000000000",
        }

        # Mock detection failure
        mock_detect_s3.side_effect = Exception("API error")

        mock_client = Mock()
        resources = [lambda_resource]

        stats = await sync_all_dependencies(resources, mock_client)

        # Should increment error count but not crash
        assert stats["errors"] == 1
        assert stats["resources_processed"] == 0
