"""
Unit tests for S3Service.
"""

import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from api.models import validate_bucket_name
from api.services.s3 import S3Service


class TestBucketNameValidation:
    """Test bucket name validation."""

    def test_valid_bucket_name(self):
        """Test valid bucket names."""
        valid_names = [
            "my-bucket",
            "mybucket123",
            "my.bucket.name",
            "abc",  # minimum length
            "a" * 63,  # maximum length
        ]

        for name in valid_names:
            # Should not raise
            validate_bucket_name(name)

    def test_bucket_name_too_short(self):
        """Test bucket name too short."""
        with pytest.raises(ValueError, match="3-63 characters"):
            validate_bucket_name("ab")

    def test_bucket_name_too_long(self):
        """Test bucket name too long."""
        with pytest.raises(ValueError, match="3-63 characters"):
            validate_bucket_name("a" * 64)

    def test_bucket_name_uppercase(self):
        """Test bucket name with uppercase."""
        with pytest.raises(ValueError, match="lowercase"):
            validate_bucket_name("MyBucket")

    def test_bucket_name_invalid_chars(self):
        """Test bucket name with invalid characters."""
        with pytest.raises(ValueError, match="lowercase alphanumeric"):
            validate_bucket_name("my_bucket")  # underscore not allowed

    def test_bucket_name_starts_with_hyphen(self):
        """Test bucket name starting with hyphen."""
        with pytest.raises(ValueError, match="cannot start or end"):
            validate_bucket_name("-mybucket")

    def test_bucket_name_ends_with_hyphen(self):
        """Test bucket name ending with hyphen."""
        with pytest.raises(ValueError, match="cannot start or end"):
            validate_bucket_name("mybucket-")

    def test_bucket_name_consecutive_periods(self):
        """Test bucket name with consecutive periods."""
        with pytest.raises(ValueError, match="consecutive periods"):
            validate_bucket_name("my..bucket")

    def test_bucket_name_ip_format(self):
        """Test bucket name formatted as IP address."""
        with pytest.raises(ValueError, match="IP address"):
            validate_bucket_name("192.168.1.1")


class TestS3ServiceListBuckets:
    """Test S3Service.list_buckets()."""

    @pytest.mark.asyncio
    async def test_list_buckets_empty(self):
        """Test listing buckets when none exist."""
        with patch("api.services.s3.query_nodes") as mock_query:
            mock_query.return_value = []

            service = S3Service(tenant_id="111111111111")
            buckets = await service.list_buckets()

            assert buckets == []
            mock_query.assert_called_once_with(
                "Resource",
                filters={"tenant_id": "111111111111", "type": "s3:bucket"},
            )

    @pytest.mark.asyncio
    async def test_list_buckets_multiple(self):
        """Test listing multiple buckets."""
        with patch("api.services.s3.query_nodes") as mock_query:
            mock_query.return_value = [
                {
                    "id": "s3-bucket-bucket1",
                    "type": "s3:bucket",
                    "name": "bucket1",
                    "tenant_id": "111111111111",
                },
                {
                    "id": "s3-bucket-bucket2",
                    "type": "s3:bucket",
                    "name": "bucket2",
                    "tenant_id": "111111111111",
                },
            ]

            service = S3Service(tenant_id="111111111111")
            buckets = await service.list_buckets()

            assert len(buckets) == 2
            assert buckets[0]["name"] == "bucket1"
            assert buckets[1]["name"] == "bucket2"


class TestS3ServiceCreateBucket:
    """Test S3Service.create_bucket()."""

    @pytest.mark.asyncio
    async def test_create_bucket_basic(self):
        """Test creating a basic bucket."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.create_node") as mock_create_node,
            patch("api.services.s3.event_bus") as mock_event_bus,
        ):
            # Mock boto3 client
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            service = S3Service(tenant_id="111111111111")
            service.client = mock_client

            result = await service.create_bucket(
                name="test-bucket",
                project="myproject",
                versioning=False,
            )

            # Verify boto3 operations
            mock_client.create_bucket.assert_called_once_with(Bucket="test-bucket")

            # Verify FalkorDB node created
            assert mock_create_node.called
            call_args = mock_create_node.call_args[0]
            assert call_args[0] == "Resource"
            node_props = call_args[1]
            assert node_props["id"] == "s3-bucket-test-bucket"
            assert node_props["type"] == "s3:bucket"
            assert node_props["name"] == "test-bucket"
            assert node_props["tenant_id"] == "111111111111"
            assert node_props["project"] == "myproject"

            # Verify SSE event published
            mock_event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bucket_with_versioning(self):
        """Test creating a bucket with versioning enabled."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.create_node") as mock_create_node,
            patch("api.services.s3.event_bus") as mock_event_bus,
        ):
            # Mock boto3 client
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            service = S3Service(tenant_id="111111111111")
            service.client = mock_client

            result = await service.create_bucket(
                name="versioned-bucket",
                versioning=True,
            )

            # Verify versioning enabled
            mock_client.put_bucket_versioning.assert_called_once_with(
                Bucket="versioned-bucket",
                VersioningConfiguration={"Status": "Enabled"},
            )

            # Verify FalkorDB node has versioning state
            call_args = mock_create_node.call_args[0]
            node_props = call_args[1]
            assert node_props["state"]["versioning"] == "Enabled"


class TestS3ServiceDeleteBucket:
    """Test S3Service.delete_bucket()."""

    @pytest.mark.asyncio
    async def test_delete_empty_bucket(self):
        """Test deleting an empty bucket."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.delete_node") as mock_delete_node,
            patch("api.services.s3.event_bus") as mock_event_bus,
        ):
            # Mock boto3 client
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            service = S3Service(tenant_id="111111111111")
            service.client = mock_client

            result = await service.delete_bucket("test-bucket", force=False)

            # Verify boto3 operations
            mock_client.delete_bucket.assert_called_once_with(Bucket="test-bucket")

            # Verify FalkorDB node deleted
            mock_delete_node.assert_called_once_with(
                "Resource", "s3-bucket-test-bucket"
            )

            # Verify SSE event published
            mock_event_bus.publish.assert_called_once()

            # Verify result
            assert result["deleted"] == "test-bucket"
            assert result["objects_deleted"] == 0

    @pytest.mark.asyncio
    async def test_delete_bucket_with_objects_force(self):
        """Test force deleting a bucket with objects."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.delete_node") as mock_delete_node,
            patch("api.services.s3.event_bus") as mock_event_bus,
        ):
            # Mock boto3 client with paginator
            mock_client = MagicMock()
            mock_paginator = MagicMock()
            mock_client.get_paginator.return_value = mock_paginator

            # Mock paginator results (2 pages with objects)
            mock_paginator.paginate.return_value = [
                {"Contents": [{"Key": "file1.txt"}, {"Key": "file2.txt"}]},
                {"Contents": [{"Key": "file3.txt"}]},
            ]

            mock_session.return_value.client.return_value = mock_client

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            service = S3Service(tenant_id="111111111111")
            service.client = mock_client

            result = await service.delete_bucket("test-bucket", force=True)

            # Verify objects deleted
            assert mock_client.delete_objects.call_count == 2

            # Verify bucket deleted
            mock_client.delete_bucket.assert_called_once_with(Bucket="test-bucket")

            # Verify result
            assert result["deleted"] == "test-bucket"
            assert result["objects_deleted"] == 3


class TestS3ServiceUpdateVersioning:
    """Test S3Service.update_versioning()."""

    @pytest.mark.asyncio
    async def test_enable_versioning(self):
        """Test enabling versioning on a bucket."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.query_nodes") as mock_query_nodes,
            patch("api.services.s3.delete_node") as mock_delete_node,
            patch("api.services.s3.create_node") as mock_create_node,
            patch("api.services.s3.event_bus") as mock_event_bus,
        ):
            # Mock boto3 client
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client

            # Mock existing bucket in FalkorDB
            mock_query_nodes.return_value = [
                {
                    "id": "s3-bucket-test-bucket",
                    "type": "s3:bucket",
                    "name": "test-bucket",
                    "tenant_id": "111111111111",
                    "state": {"versioning": ""},
                }
            ]

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            service = S3Service(tenant_id="111111111111")
            service.client = mock_client

            result = await service.update_versioning("test-bucket", enabled=True)

            # Verify versioning enabled in MiniStack
            mock_client.put_bucket_versioning.assert_called_once_with(
                Bucket="test-bucket",
                VersioningConfiguration={"Status": "Enabled"},
            )

            # Verify FalkorDB updated (delete old, create updated)
            mock_delete_node.assert_called_once()
            mock_create_node.assert_called_once()

            # Verify result has updated versioning status
            assert result["state"]["versioning"] == "Enabled"
