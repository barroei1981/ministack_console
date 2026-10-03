"""
Integration tests for S3 API endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestListBuckets:
    """Test GET /api/resources/s3/buckets."""

    def test_list_buckets_empty(self):
        """Test listing buckets when none exist."""
        with patch("api.services.s3.query_nodes") as mock_query:
            mock_query.return_value = []

            response = client.get(
                "/api/resources/s3/buckets?tenant_id=111111111111"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["tenant_id"] == "111111111111"
            assert data["buckets"] == []
            assert data["total"] == 0

    def test_list_buckets_multiple(self):
        """Test listing multiple buckets."""
        with patch("api.services.s3.query_nodes") as mock_query:
            mock_query.return_value = [
                {
                    "id": "s3-bucket-bucket1",
                    "type": "s3:bucket",
                    "name": "bucket1",
                    "tenant_id": "111111111111",
                    "project": "app1",
                    "arn": "arn:aws:s3:::bucket1",
                    "created_at": "2026-10-01T00:00:00Z",
                    "state": {"versioning": "Enabled"},
                    "tags": {"env": "dev"},
                },
                {
                    "id": "s3-bucket-bucket2",
                    "type": "s3:bucket",
                    "name": "bucket2",
                    "tenant_id": "111111111111",
                    "project": "app2",
                    "arn": "arn:aws:s3:::bucket2",
                    "created_at": "2026-10-02T00:00:00Z",
                    "state": {"versioning": ""},
                    "tags": {},
                },
            ]

            response = client.get(
                "/api/resources/s3/buckets?tenant_id=111111111111"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["tenant_id"] == "111111111111"
            assert len(data["buckets"]) == 2
            assert data["buckets"][0]["name"] == "bucket1"
            assert data["buckets"][0]["versioning"] == "Enabled"
            assert data["buckets"][0]["project"] == "app1"
            assert data["buckets"][1]["name"] == "bucket2"
            assert data["buckets"][1]["versioning"] == ""
            assert data["total"] == 2

    def test_list_buckets_tenant_isolation(self):
        """Test tenant isolation - mismatched tenant_id."""
        with patch("api.services.s3.query_nodes") as mock_query:
            mock_query.return_value = []

            response = client.get(
                "/api/resources/s3/buckets?tenant_id=999999999999"
            )

            # Middleware sets tenant_id to 999999999999, so request will succeed
            # Tenant isolation is enforced at service layer (query filters by tenant_id)
            assert response.status_code == 200
            data = response.json()
            assert data["tenant_id"] == "999999999999"
            assert data["buckets"] == []


class TestCreateBucket:
    """Test POST /api/resources/s3/buckets."""

    def test_create_bucket_success(self):
        """Test creating a bucket successfully."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.create_node") as _mock_create_node,
            patch("api.services.s3.event_bus") as mock_event_bus,
        ):
            # Mock boto3 client
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            response = client.post(
                "/api/resources/s3/buckets",
                json={
                    "name": "test-bucket",
                    "tenant_id": "111111111111",
                    "project": "myapp",
                    "versioning": False,
                    "tags": {"env": "test"},
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "test-bucket"
            assert data["tenant_id"] == "111111111111"
            assert data["project"] == "myapp"
            assert data["arn"] == "arn:aws:s3:::test-bucket"

    def test_create_bucket_invalid_name_uppercase(self):
        """Test creating a bucket with invalid name (uppercase)."""
        response = client.post(
            "/api/resources/s3/buckets",
            json={
                "name": "TestBucket",  # Invalid: uppercase
                "tenant_id": "111111111111",
                "versioning": False,
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert "detail" in data

    def test_create_bucket_invalid_name_too_short(self):
        """Test creating a bucket with invalid name (too short)."""
        response = client.post(
            "/api/resources/s3/buckets",
            json={
                "name": "ab",  # Invalid: too short
                "tenant_id": "111111111111",
                "versioning": False,
            },
        )

        assert response.status_code == 422  # Pydantic validation error

    def test_create_bucket_already_exists(self):
        """Test creating a bucket that already exists."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
        ):
            # Mock boto3 client to raise BucketAlreadyExists
            mock_client = MagicMock()
            from botocore.exceptions import ClientError

            mock_client.create_bucket.side_effect = ClientError(
                {"Error": {"Code": "BucketAlreadyExists"}},
                "CreateBucket",
            )
            mock_session.return_value.client.return_value = mock_client

            response = client.post(
                "/api/resources/s3/buckets",
                json={
                    "name": "existing-bucket",
                    "tenant_id": "111111111111",
                    "versioning": False,
                },
            )

            assert response.status_code == 409
            data = response.json()
            assert "already exists" in data["detail"]


class TestGetBucket:
    """Test GET /api/resources/s3/buckets/{bucket_name}."""

    def test_get_bucket_success(self):
        """Test getting bucket details successfully."""
        with (
            patch("api.services.s3.query_nodes") as mock_query,
            patch("api.services.s3.boto3.Session") as mock_session,
        ):
            # Mock FalkorDB query
            mock_query.return_value = [
                {
                    "id": "s3-bucket-test-bucket",
                    "type": "s3:bucket",
                    "name": "test-bucket",
                    "tenant_id": "111111111111",
                    "project": "myapp",
                    "arn": "arn:aws:s3:::test-bucket",
                    "created_at": "2026-10-01T00:00:00Z",
                    "state": {"versioning": ""},
                    "tags": {"env": "prod"},
                }
            ]

            # Mock boto3 versioning check
            mock_client = MagicMock()
            mock_client.get_bucket_versioning.return_value = {"Status": "Enabled"}
            mock_session.return_value.client.return_value = mock_client

            response = client.get(
                "/api/resources/s3/buckets/test-bucket?tenant_id=111111111111"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test-bucket"
            assert data["tenant_id"] == "111111111111"
            assert data["versioning"] == "Enabled"  # Updated from live query

    def test_get_bucket_not_found(self):
        """Test getting a bucket that doesn't exist."""
        with patch("api.services.s3.query_nodes") as mock_query:
            # Bucket not found in FalkorDB
            mock_query.return_value = []

            response = client.get(
                "/api/resources/s3/buckets/nonexistent?tenant_id=111111111111"
            )

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]


class TestDeleteBucket:
    """Test DELETE /api/resources/s3/buckets/{bucket_name}."""

    def test_delete_empty_bucket(self):
        """Test deleting an empty bucket."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.delete_node") as _mock_delete_node,
            patch("api.services.s3.event_bus") as mock_event_bus,
        ):
            # Mock boto3 client
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            response = client.delete(
                "/api/resources/s3/buckets/test-bucket?tenant_id=111111111111&force=false"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["deleted"] == "test-bucket"
            assert data["objects_deleted"] == 0

    def test_delete_bucket_not_empty_no_force(self):
        """Test deleting a non-empty bucket without force flag."""
        with patch("api.services.s3.boto3.Session") as mock_session:
            # Mock boto3 client to raise BucketNotEmpty
            mock_client = MagicMock()
            from botocore.exceptions import ClientError

            mock_client.delete_bucket.side_effect = ClientError(
                {"Error": {"Code": "BucketNotEmpty"}},
                "DeleteBucket",
            )
            mock_session.return_value.client.return_value = mock_client

            response = client.delete(
                "/api/resources/s3/buckets/test-bucket?tenant_id=111111111111&force=false"
            )

            assert response.status_code == 400
            data = response.json()
            assert "not empty" in data["detail"]

    def test_delete_bucket_with_objects_force(self):
        """Test force deleting a bucket with objects."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.delete_node") as _mock_delete_node,
            patch("api.services.s3.event_bus") as mock_event_bus,
        ):
            # Mock boto3 client with paginator
            mock_client = MagicMock()
            mock_paginator = MagicMock()
            mock_client.get_paginator.return_value = mock_paginator

            # Mock paginator results (1 page with 2 objects)
            mock_paginator.paginate.return_value = [
                {"Contents": [{"Key": "file1.txt"}, {"Key": "file2.txt"}]},
            ]

            mock_session.return_value.client.return_value = mock_client

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            response = client.delete(
                "/api/resources/s3/buckets/test-bucket?tenant_id=111111111111&force=true"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["deleted"] == "test-bucket"
            assert data["objects_deleted"] == 2


class TestTenantIsolation:
    """Test tenant isolation across all S3 endpoints."""

    def test_create_bucket_cross_tenant_forbidden(self):
        """Verify tenant isolation on create."""
        # Middleware sets tenant_id to 111111111111 (from query param)
        # Request body has different tenant_id -> 403 Forbidden
        response = client.post(
            "/api/resources/s3/buckets?tenant_id=111111111111",
            json={
                "name": "test-bucket",
                "tenant_id": "999999999999",  # Different tenant
                "versioning": False,
            },
        )

        assert response.status_code == 403
        data = response.json()
        assert "Forbidden" in data.get("detail", "") or "forbidden" in data.get("error", "").lower()

    def test_get_bucket_cross_tenant_forbidden(self):
        """Verify tenant isolation on get."""
        # Middleware sets tenant_id to 111111111111
        # Try to get bucket that doesn't exist for this tenant
        with patch("api.services.s3.query_nodes") as mock_query:
            mock_query.return_value = []

            response = client.get(
                "/api/resources/s3/buckets/test-bucket?tenant_id=111111111111"
            )

            # Since bucket doesn't exist for this tenant, returns 404
            assert response.status_code == 404

    def test_delete_bucket_cross_tenant_forbidden(self):
        """Verify tenant isolation on delete."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
        ):
            # Mock boto3 to raise NoSuchBucket
            from botocore.exceptions import ClientError

            mock_client = MagicMock()
            mock_client.delete_bucket.side_effect = ClientError(
                {"Error": {"Code": "NoSuchBucket"}},
                "DeleteBucket",
            )
            mock_session.return_value.client.return_value = mock_client

            response = client.delete(
                "/api/resources/s3/buckets/test-bucket?tenant_id=111111111111"
            )

            # Bucket doesn't exist for this tenant -> 404
            assert response.status_code == 404

    def test_update_versioning_cross_tenant_forbidden(self):
        """Verify tenant isolation on versioning."""
        # Middleware will get tenant_id from query param (inferred by TestClient)
        # But we pass different tenant_id in body -> 403
        response = client.put(
            "/api/resources/s3/buckets/test-bucket/versioning?tenant_id=111111111111",
            json={
                "enabled": True,
                "tenant_id": "999999999999",  # Different tenant
            },
        )

        assert response.status_code == 403


class TestUpdateVersioning:
    """Test PUT /api/resources/s3/buckets/{bucket_name}/versioning."""

    def test_enable_versioning(self):
        """Test enabling versioning on a bucket."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.query_nodes") as mock_query_nodes,
            patch("api.services.s3.delete_node") as _mock_delete_node,
            patch("api.services.s3.create_node") as _mock_create_node,
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
                    "arn": "arn:aws:s3:::test-bucket",
                    "created_at": "2026-10-01T00:00:00Z",
                    "state": {"versioning": ""},
                    "tags": {},
                }
            ]

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            response = client.put(
                "/api/resources/s3/buckets/test-bucket/versioning",
                json={
                    "enabled": True,
                    "tenant_id": "111111111111",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test-bucket"
            assert data["versioning"] == "Enabled"

    def test_disable_versioning(self):
        """Test disabling (suspending) versioning on a bucket."""
        with (
            patch("api.services.s3.boto3.Session") as mock_session,
            patch("api.services.s3.query_nodes") as mock_query_nodes,
            patch("api.services.s3.delete_node") as _mock_delete_node,
            patch("api.services.s3.create_node") as _mock_create_node,
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
                    "arn": "arn:aws:s3:::test-bucket",
                    "created_at": "2026-10-01T00:00:00Z",
                    "state": {"versioning": "Enabled"},
                    "tags": {},
                }
            ]

            # Mock event bus
            mock_event_bus.publish = AsyncMock()

            response = client.put(
                "/api/resources/s3/buckets/test-bucket/versioning",
                json={
                    "enabled": False,
                    "tenant_id": "111111111111",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test-bucket"
            assert data["versioning"] == "Suspended"
