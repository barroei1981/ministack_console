"""
S3 service layer for MiniStack operations.

Handles boto3 operations, dual-write to FalkorDB, and SSE event emission.
"""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from control_plane.events import event_bus
from control_plane.graph.query import create_node, delete_node, query_nodes
from control_plane.observability import (
    log_audit,
    log_operational,
    log_security,
    trace_operation,
)


class S3Service:
    """
    S3 service layer for tenant-scoped bucket operations.

    Each instance is scoped to a single tenant. Uses boto3 to interact with
    MiniStack and maintains resource state in FalkorDB.
    """

    def __init__(self, tenant_id: str):
        """
        Initialize S3 service for a tenant.

        Args:
            tenant_id: 12-digit tenant ID (MiniStack access key)

        Raises:
            ValueError: If tenant_id is invalid
        """
        if not tenant_id or not re.match(r"^\d{12}$", tenant_id):
            raise ValueError("Tenant ID must be exactly 12 digits")

        self.tenant_id = tenant_id
        self.client = self._create_client()

    def _create_client(self) -> Any:
        """
        Create boto3 S3 client for MiniStack.

        Returns:
            boto3 S3 client configured for MiniStack endpoint
        """
        session = boto3.Session(
            aws_access_key_id=self.tenant_id,  # 12-digit tenant ID
            aws_secret_access_key="dummy",  # MiniStack ignores secret
            region_name="us-east-1",
        )
        return session.client("s3", endpoint_url="http://localhost:4566")

    async def list_buckets(self) -> list[dict[str, Any]]:
        """
        List all S3 buckets for this tenant.

        Queries FalkorDB for bucket metadata (source of truth for control-plane state).

        Returns:
            List of bucket dicts with metadata

        Raises:
            Exception: If query fails
        """
        with trace_operation("list_s3_buckets", tenant_id=self.tenant_id):
            try:
                # Query FalkorDB for bucket resources
                bucket_nodes = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"tenant_id": self.tenant_id, "type": "s3:bucket"},
                )

                log_operational(
                    "Listed S3 buckets",
                    tenant_id=self.tenant_id,
                    count=len(bucket_nodes),
                )

                return bucket_nodes

            except Exception as e:
                log_operational(
                    "Failed to list S3 buckets",
                    tenant_id=self.tenant_id,
                    error=str(e),
                )
                raise

    async def get_bucket(self, name: str) -> dict[str, Any] | None:
        """
        Get bucket details by name.

        Args:
            name: Bucket name

        Returns:
            Bucket dict with metadata or None if not found

        Raises:
            Exception: If query fails
        """
        with trace_operation("get_s3_bucket", tenant_id=self.tenant_id, bucket=name):
            try:
                # Query FalkorDB for specific bucket
                bucket_id = f"s3-bucket-{name}"
                buckets = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={
                        "id": bucket_id,
                        "tenant_id": self.tenant_id,
                        "type": "s3:bucket",
                    },
                )

                if not buckets:
                    return None

                bucket = buckets[0]

                # Fetch live versioning status from MiniStack
                try:
                    versioning_response = await asyncio.to_thread(
                        self.client.get_bucket_versioning, Bucket=name
                    )
                    versioning_status = versioning_response.get("Status", "")
                except ClientError:
                    versioning_status = ""

                # Update bucket state with live data (defensive checks)
                if "state" not in bucket:
                    bucket["state"] = {}

                bucket["versioning"] = versioning_status
                bucket["state"]["versioning"] = versioning_status

                log_operational(
                    "Retrieved S3 bucket",
                    tenant_id=self.tenant_id,
                    bucket=name,
                )

                return bucket

            except Exception as e:
                log_operational(
                    "Failed to get S3 bucket",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    error=str(e),
                )
                raise

    async def create_bucket(
        self,
        name: str,
        project: str | None = None,
        versioning: bool = False,
        tags: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create an S3 bucket.

        Dual-write pattern: Create in MiniStack first, then FalkorDB, then emit SSE event.

        Args:
            name: Bucket name
            project: Control-plane project tag
            versioning: Enable versioning on bucket
            tags: Control-plane tags

        Returns:
            Created bucket dict with metadata

        Raises:
            ClientError: If bucket creation fails in MiniStack
            Exception: If FalkorDB write or SSE publish fails
        """
        with trace_operation(
            "create_s3_bucket", tenant_id=self.tenant_id, bucket=name
        ):
            try:
                # 1. Create in MiniStack
                await asyncio.to_thread(self.client.create_bucket, Bucket=name)

                log_operational(
                    "Created S3 bucket in MiniStack",
                    tenant_id=self.tenant_id,
                    bucket=name,
                )

                # 2. Enable versioning if requested
                versioning_status = ""
                if versioning:
                    try:
                        await asyncio.to_thread(
                            self.client.put_bucket_versioning,
                            Bucket=name,
                            VersioningConfiguration={"Status": "Enabled"},
                        )
                        versioning_status = "Enabled"
                    except Exception as e:
                        # Rollback: delete bucket
                        log_operational(
                            "Failed to enable versioning, rolling back bucket",
                            tenant_id=self.tenant_id,
                            bucket=name,
                            error=str(e),
                        )
                        await asyncio.to_thread(self.client.delete_bucket, Bucket=name)
                        raise

                # 3. Add to FalkorDB
                resource = {
                    "id": f"s3-bucket-{name}",
                    "type": "s3:bucket",
                    "name": name,
                    "tenant_id": self.tenant_id,
                    "project": project or "",
                    "arn": f"arn:aws:s3:::{name}",
                    "state": {
                        "versioning": versioning_status,
                        "region": "us-east-1",
                    },
                    "tags": tags or {},
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }

                try:
                    await asyncio.to_thread(create_node, "Resource", resource)
                except Exception as e:
                    # Rollback: delete bucket from MiniStack
                    log_operational(
                        "Failed to add bucket to FalkorDB, rolling back",
                        tenant_id=self.tenant_id,
                        bucket=name,
                        error=str(e),
                    )
                    await asyncio.to_thread(self.client.delete_bucket, Bucket=name)
                    raise

                log_operational(
                    "Added S3 bucket to FalkorDB",
                    tenant_id=self.tenant_id,
                    bucket=name,
                )

                # 4. Emit SSE event
                await event_bus.publish(
                    "RESOURCE_CREATED", resource, self.tenant_id
                )

                log_security(
                    "S3 bucket created",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    project=project,
                )

                # Audit log for compliance
                log_audit(
                    "S3 bucket created",
                    event_type="BUCKET_CREATED",
                    actor={"id": self.tenant_id, "type": "TENANT"},
                    target={"type": "s3:bucket", "id": name},
                    action="CREATE",
                    status="SUCCESS",
                    changes={"before": None, "after": resource},
                )

                return resource

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")

                if error_code == "BucketAlreadyExists":
                    log_security(
                        "S3 bucket creation failed - already exists",
                        tenant_id=self.tenant_id,
                        bucket=name,
                        error_code=error_code,
                    )
                    raise ValueError(f"Bucket {name} already exists") from e

                log_operational(
                    "Failed to create S3 bucket in MiniStack",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    error=str(e),
                    error_code=error_code,
                )
                raise

            except Exception as e:
                log_operational(
                    "Failed to create S3 bucket",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    error=str(e),
                )
                raise

    async def delete_bucket(
        self, name: str, force: bool = False
    ) -> dict[str, Any]:
        """
        Delete an S3 bucket.

        Dual-write pattern: Delete from MiniStack first, then FalkorDB, then emit SSE event.

        Args:
            name: Bucket name
            force: If True, delete all objects before deleting bucket

        Returns:
            Dict with deletion summary: {deleted: name, objects_deleted: count}

        Raises:
            ValueError: If bucket not empty and force=False
            ClientError: If bucket deletion fails in MiniStack
            Exception: If FalkorDB delete or SSE publish fails
        """
        with trace_operation(
            "delete_s3_bucket", tenant_id=self.tenant_id, bucket=name, force=force
        ):
            try:
                objects_deleted = 0

                # If force=true, delete all objects first
                if force:
                    # List and delete all objects
                    paginator = self.client.get_paginator("list_objects_v2")
                    pages = await asyncio.to_thread(
                        paginator.paginate, Bucket=name
                    )

                    for page in pages:
                        objects = page.get("Contents", [])
                        if objects:
                            delete_keys = [{"Key": obj["Key"]} for obj in objects]
                            await asyncio.to_thread(
                                self.client.delete_objects,
                                Bucket=name,
                                Delete={"Objects": delete_keys},
                            )
                            objects_deleted += len(delete_keys)

                    log_operational(
                        "Deleted objects from S3 bucket",
                        tenant_id=self.tenant_id,
                        bucket=name,
                        objects_deleted=objects_deleted,
                    )

                # 1. Delete bucket from MiniStack
                try:
                    await asyncio.to_thread(self.client.delete_bucket, Bucket=name)
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "Unknown")

                    if error_code == "BucketNotEmpty":
                        raise ValueError(
                            f"Bucket {name} not empty. Use force=true to delete all objects first"
                        ) from e
                    elif error_code == "NoSuchBucket":
                        raise ValueError(f"Bucket {name} not found") from e

                    raise

                log_operational(
                    "Deleted S3 bucket from MiniStack",
                    tenant_id=self.tenant_id,
                    bucket=name,
                )

                # 2. Delete from FalkorDB
                bucket_id = f"s3-bucket-{name}"
                await asyncio.to_thread(delete_node, "Resource", bucket_id)

                log_operational(
                    "Removed S3 bucket from FalkorDB",
                    tenant_id=self.tenant_id,
                    bucket=name,
                )

                # 3. Emit SSE event
                await event_bus.publish(
                    "RESOURCE_DELETED",
                    {"id": bucket_id, "name": name, "type": "s3:bucket"},
                    self.tenant_id,
                )

                log_security(
                    "S3 bucket deleted",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    objects_deleted=objects_deleted,
                )

                return {"deleted": name, "objects_deleted": objects_deleted}

            except Exception as e:
                log_operational(
                    "Failed to delete S3 bucket",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    error=str(e),
                )
                raise

    async def update_versioning(
        self, name: str, enabled: bool
    ) -> dict[str, Any]:
        """
        Update bucket versioning status.

        Dual-write pattern: Update in MiniStack first, then FalkorDB, then emit SSE event.

        Args:
            name: Bucket name
            enabled: Enable or suspend versioning

        Returns:
            Updated bucket dict with metadata

        Raises:
            ClientError: If versioning update fails in MiniStack
            Exception: If FalkorDB update or SSE publish fails
        """
        with trace_operation(
            "update_s3_bucket_versioning",
            tenant_id=self.tenant_id,
            bucket=name,
            enabled=enabled,
        ):
            try:
                # 1. Update versioning in MiniStack
                status = "Enabled" if enabled else "Suspended"
                await asyncio.to_thread(
                    self.client.put_bucket_versioning,
                    Bucket=name,
                    VersioningConfiguration={"Status": status},
                )

                log_operational(
                    "Updated S3 bucket versioning in MiniStack",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    status=status,
                )

                # 2. Update state in FalkorDB
                # Query current bucket node
                bucket_id = f"s3-bucket-{name}"
                buckets = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"id": bucket_id, "tenant_id": self.tenant_id},
                )

                if not buckets:
                    raise ValueError(f"Bucket {name} not found in FalkorDB")

                bucket = buckets[0]

                # Defensive state check
                if "state" not in bucket:
                    bucket["state"] = {}

                bucket["state"]["versioning"] = status
                bucket["updated_at"] = datetime.now(UTC).isoformat()

                # Delete old node and create updated one (FalkorDB pattern)
                await asyncio.to_thread(delete_node, "Resource", bucket_id)
                await asyncio.to_thread(create_node, "Resource", bucket)

                log_operational(
                    "Updated S3 bucket versioning in FalkorDB",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    status=status,
                )

                # 3. Emit SSE event
                await event_bus.publish(
                    "RESOURCE_UPDATED", bucket, self.tenant_id
                )

                log_security(
                    "S3 bucket versioning updated",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    versioning=status,
                )

                return bucket

            except Exception as e:
                log_operational(
                    "Failed to update S3 bucket versioning",
                    tenant_id=self.tenant_id,
                    bucket=name,
                    error=str(e),
                )
                raise

    async def list_objects(
        self, bucket_name: str, prefix: str = "", max_keys: int = 1000
    ) -> dict[str, Any]:
        """
        List objects in bucket with optional prefix filter.

        Args:
            bucket_name: Bucket name
            prefix: Prefix filter (for folder navigation)
            max_keys: Maximum objects to return (pagination)

        Returns:
            Dict with objects list, common_prefixes (folders), is_truncated, next_token
        """
        with trace_operation(
            "list_s3_objects",
            tenant_id=self.tenant_id,
            bucket=bucket_name,
            prefix=prefix,
        ):
            try:
                response = await asyncio.to_thread(
                    self.client.list_objects_v2,
                    Bucket=bucket_name,
                    Prefix=prefix,
                    MaxKeys=max_keys,
                    Delimiter="/",  # Group by folders
                )

                # Parse objects
                objects = []
                for obj in response.get("Contents", []):
                    objects.append(
                        {
                            "key": obj["Key"],
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"].isoformat(),
                            "storage_class": obj.get("StorageClass", "STANDARD"),
                            "etag": obj.get("ETag", "").strip('"'),
                        }
                    )

                # Parse common prefixes (folders)
                folders = []
                for prefix_obj in response.get("CommonPrefixes", []):
                    folders.append({"key": prefix_obj["Prefix"]})

                result = {
                    "objects": objects,
                    "folders": folders,
                    "is_truncated": response.get("IsTruncated", False),
                    "next_token": response.get("NextContinuationToken"),
                    "prefix": prefix,
                }

                log_operational(
                    "Listed S3 objects",
                    tenant_id=self.tenant_id,
                    bucket=bucket_name,
                    prefix=prefix,
                    object_count=len(objects),
                    folder_count=len(folders),
                )

                return result

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NoSuchBucket":
                    raise ValueError(f"Bucket {bucket_name} not found") from e
                raise

    async def upload_object(
        self,
        bucket_name: str,
        key: str,
        file_content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload object to S3 bucket.

        Args:
            bucket_name: Bucket name
            key: Object key (path)
            file_content: File content as bytes
            metadata: Optional object metadata

        Returns:
            Dict with upload result: {bucket, key, size, etag}
        """
        with trace_operation(
            "upload_s3_object",
            tenant_id=self.tenant_id,
            bucket=bucket_name,
            key=key,
        ):
            try:
                extra_args = {}
                if metadata:
                    extra_args["Metadata"] = metadata

                response = await asyncio.to_thread(
                    self.client.put_object,
                    Bucket=bucket_name,
                    Key=key,
                    Body=file_content,
                    **extra_args,
                )

                result = {
                    "bucket": bucket_name,
                    "key": key,
                    "size": len(file_content),
                    "etag": response.get("ETag", "").strip('"'),
                }

                log_operational(
                    "Uploaded S3 object",
                    tenant_id=self.tenant_id,
                    bucket=bucket_name,
                    key=key,
                    size=len(file_content),
                )

                # Emit SSE event for object creation
                await event_bus.publish(
                    "RESOURCE_CREATED",
                    {
                        "type": "s3:object",
                        "bucket": bucket_name,
                        "key": key,
                        "size": len(file_content),
                    },
                    self.tenant_id,
                )

                log_audit(
                    "S3 object uploaded",
                    event_type="OBJECT_UPLOADED",
                    actor={"id": self.tenant_id, "type": "TENANT"},
                    target={"type": "s3:object", "id": f"{bucket_name}/{key}"},
                    action="CREATE",
                    status="SUCCESS",
                    changes={"before": None, "after": result},
                )

                return result

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NoSuchBucket":
                    raise ValueError(f"Bucket {bucket_name} not found") from e
                raise

    async def download_object(self, bucket_name: str, key: str) -> str:
        """
        Generate presigned URL for object download.

        Args:
            bucket_name: Bucket name
            key: Object key

        Returns:
            Presigned URL (expires in 1 hour)
        """
        with trace_operation(
            "download_s3_object",
            tenant_id=self.tenant_id,
            bucket=bucket_name,
            key=key,
        ):
            try:
                url = await asyncio.to_thread(
                    self.client.generate_presigned_url,
                    "get_object",
                    Params={"Bucket": bucket_name, "Key": key},
                    ExpiresIn=3600,  # 1 hour
                )

                log_operational(
                    "Generated presigned URL for S3 object",
                    tenant_id=self.tenant_id,
                    bucket=bucket_name,
                    key=key,
                )

                return url

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NoSuchBucket":
                    raise ValueError(f"Bucket {bucket_name} not found") from e
                elif error_code == "NoSuchKey":
                    raise ValueError(f"Object {key} not found") from e
                raise

    async def delete_objects(
        self, bucket_name: str, keys: list[str]
    ) -> dict[str, Any]:
        """
        Delete multiple objects from bucket.

        Args:
            bucket_name: Bucket name
            keys: List of object keys to delete

        Returns:
            Dict with deletion result: {deleted_count, errors}
        """
        with trace_operation(
            "delete_s3_objects",
            tenant_id=self.tenant_id,
            bucket=bucket_name,
            key_count=len(keys),
        ):
            try:
                objects_to_delete = [{"Key": key} for key in keys]

                response = await asyncio.to_thread(
                    self.client.delete_objects,
                    Bucket=bucket_name,
                    Delete={"Objects": objects_to_delete},
                )

                deleted = response.get("Deleted", [])
                errors = response.get("Errors", [])

                result = {"deleted_count": len(deleted), "errors": errors}

                log_operational(
                    "Deleted S3 objects",
                    tenant_id=self.tenant_id,
                    bucket=bucket_name,
                    deleted_count=len(deleted),
                    error_count=len(errors),
                )

                # Emit SSE events for each deleted object
                for obj in deleted:
                    await event_bus.publish(
                        "RESOURCE_DELETED",
                        {
                            "type": "s3:object",
                            "bucket": bucket_name,
                            "key": obj["Key"],
                        },
                        self.tenant_id,
                    )

                log_audit(
                    "S3 objects deleted",
                    event_type="OBJECTS_DELETED",
                    actor={"id": self.tenant_id, "type": "TENANT"},
                    target={"type": "s3:object", "id": f"{bucket_name}/*"},
                    action="DELETE",
                    status="SUCCESS",
                    changes={"before": keys, "after": None},
                )

                return result

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NoSuchBucket":
                    raise ValueError(f"Bucket {bucket_name} not found") from e
                raise
