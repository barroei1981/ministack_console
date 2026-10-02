"""
Native tagging operations with dual-write (FalkorDB + MiniStack).

Stores tags in FalkorDB AND writes to MiniStack via boto3 APIs.
Only applies to taggable services (S3, Lambda, DynamoDB).
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any

from control_plane.graph.query import get_graph
from control_plane.ministack_client import MiniStackClient
from control_plane.observability import log_audit, trace_operation
from control_plane.tagging.models import (
    AWS_RESERVED_PREFIXES,
    MAX_TAG_KEY_LENGTH,
    MAX_TAG_VALUE_LENGTH,
    TAGGABLE_SERVICES,
    TagNamespace,
)
from control_plane.tenants.isolation import validate_tenant_id

logger = logging.getLogger(__name__)


def validate_aws_tag(key: str, value: str, is_native: bool = False) -> None:
    """
    Validate tag according to AWS constraints.

    Enforces:
    - Key length ≤ 128 chars
    - Value length ≤ 256 chars
    - Key contains only allowed characters
    - For native tags: block reserved AWS prefixes (aws:, AWS:)

    Args:
        key: Tag key
        value: Tag value
        is_native: Whether this is a native tag (enforces reserved prefix check)

    Raises:
        ValueError: If validation fails
    """
    if not key:
        raise ValueError("Tag key cannot be empty")

    if len(key) > MAX_TAG_KEY_LENGTH:
        raise ValueError(
            f"Tag key exceeds {MAX_TAG_KEY_LENGTH} characters (got {len(key)})"
        )

    if len(value) > MAX_TAG_VALUE_LENGTH:
        raise ValueError(
            f"Tag value exceeds {MAX_TAG_VALUE_LENGTH} characters (got {len(value)})"
        )

    # Allow alphanumeric + _-.: /=+@ (AWS-compatible chars)
    if not re.match(r"^[a-zA-Z0-9_\-.:/=+@\s]+$", key):
        raise ValueError(
            "Tag key contains invalid characters (allowed: alphanumeric, _-.: /=+@)"
        )

    # Block reserved prefixes for native tags
    if is_native:
        for prefix in AWS_RESERVED_PREFIXES:
            if key.startswith(prefix):
                raise ValueError(
                    f"Native tags cannot use reserved prefix '{prefix}' (reserved prefixes: {AWS_RESERVED_PREFIXES})"
                )


def _extract_resource_components(resource_id: str) -> dict[str, str]:
    """
    Extract service type and name from resource ID.

    Args:
        resource_id: Resource ID (format: "service:type:name")

    Returns:
        Dict with 'type' (e.g., "s3:bucket") and 'name' keys

    Raises:
        ValueError: If resource_id format is invalid
    """
    parts = resource_id.split(":", 2)

    if len(parts) < 3:
        raise ValueError(
            f"Invalid resource_id format: {resource_id} (expected 'service:type:name')"
        )

    resource_type = f"{parts[0]}:{parts[1]}"
    resource_name = parts[2]

    return {"type": resource_type, "name": resource_name}


async def _write_native_tag_to_ministack(
    resource_id: str,
    tags: dict[str, str],
    tenant_id: str,
) -> None:
    """
    Write tags to MiniStack via boto3 API.

    Handles service-specific tagging APIs:
    - S3: put_bucket_tagging (replaces all tags)
    - Lambda: tag_resource (merges with existing)
    - DynamoDB: tag_resource (merges with existing)

    Args:
        resource_id: Resource ID
        tags: Complete tag dict to write
        tenant_id: Tenant ID (used as access key)

    Raises:
        Exception: If boto3 operation fails
    """
    components = _extract_resource_components(resource_id)
    resource_type = components["type"]
    resource_name = components["name"]

    client = MiniStackClient(access_key=tenant_id)

    if resource_type == "s3:bucket":
        # S3 requires TagSet format
        tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]

        session = client._get_session()
        async with session.client("s3", endpoint_url=client.endpoint_url) as s3:
            await s3.put_bucket_tagging(
                Bucket=resource_name,
                Tagging={"TagSet": tag_set},
            )

        logger.debug(f"Wrote {len(tags)} tags to S3 bucket {resource_name}")

    elif resource_type == "lambda:function":
        # Lambda requires ARN and Tags dict
        # Construct ARN from resource_id (already in ARN format if from MiniStack)
        # or build it from components
        if resource_id.startswith("arn:"):
            arn = resource_id
        else:
            # Build ARN: arn:aws:lambda:region:account:function:name
            arn = f"arn:aws:lambda:us-east-1:{tenant_id}:function:{resource_name}"

        session = client._get_session()
        async with session.client(
            "lambda", endpoint_url=client.endpoint_url
        ) as lambda_client:
            await lambda_client.tag_resource(
                Resource=arn,
                Tags=tags,
            )

        logger.debug(f"Wrote {len(tags)} tags to Lambda function {resource_name}")

    elif resource_type == "dynamodb:table":
        # DynamoDB requires ARN and Tags list
        if resource_id.startswith("arn:"):
            arn = resource_id
        else:
            # Build ARN: arn:aws:dynamodb:region:account:table/name
            arn = f"arn:aws:dynamodb:us-east-1:{tenant_id}:table/{resource_name}"

        tag_list = [{"Key": k, "Value": v} for k, v in tags.items()]

        session = client._get_session()
        async with session.client(
            "dynamodb", endpoint_url=client.endpoint_url
        ) as dynamodb:
            await dynamodb.tag_resource(
                ResourceArn=arn,
                Tags=tag_list,
            )

        logger.debug(f"Wrote {len(tags)} tags to DynamoDB table {resource_name}")

    else:
        # Should not reach here if TAGGABLE_SERVICES check is done
        raise ValueError(f"Unsupported service type for native tagging: {resource_type}")


async def add_native_tag(
    resource_id: str,
    key: str,
    value: str,
    tenant_id: str,
) -> dict[str, Any]:
    """
    Add native tag to a resource (dual-write: FalkorDB + MiniStack).

    Stores tag in FalkorDB with namespace="native", then writes to MiniStack
    via boto3 if resource type supports native tagging.

    Args:
        resource_id: Resource ID to tag
        key: Tag key
        value: Tag value
        tenant_id: Tenant ID for isolation

    Returns:
        Dict with tag details and boto3_written flag

    Raises:
        ValueError: If validation fails or resource doesn't exist
        Exception: If FalkorDB operation fails

    Note:
        If boto3 write fails, FalkorDB update still succeeds.
        Partial success is logged as warning.

    Example:
        >>> await add_native_tag("s3:bucket:my-bucket", "Name", "uploads", "123456789012")
        {'resource_id': 's3:bucket:my-bucket', 'key': 'Name', 'value': 'uploads', 'boto3_written': True}
    """
    validate_tenant_id(tenant_id)
    validate_aws_tag(key, value, is_native=True)

    with trace_operation(
        "add_native_tag",
        resource_id=resource_id,
        key=key,
        tenant_id=tenant_id,
    ):
        # Extract resource type
        components = _extract_resource_components(resource_id)
        resource_type = components["type"]

        # Get existing tags for BEFORE state
        old_tags = get_native_tags(resource_id, tenant_id)

        # 1. Store in FalkorDB (always succeeds or raises)
        graph = get_graph()

        # Verify resource exists
        verify_query = """
        MATCH (r:Resource {id: $resource_id, tenant_id: $tenant_id})
        RETURN r
        """
        result = graph.query(
            verify_query,
            params={"resource_id": resource_id, "tenant_id": tenant_id},
        )

        if not result.result_set:
            raise ValueError(
                f"Resource {resource_id} not found for tenant {tenant_id}"
            )

        # Create Tag node (idempotent)
        tag_query = """
        MERGE (t:Tag {key: $key, value: $value})
        RETURN t
        """
        graph.query(tag_query, params={"key": key, "value": value})

        # Create TAGGED_WITH relationship with namespace="native"
        rel_query = """
        MATCH (r:Resource {id: $resource_id, tenant_id: $tenant_id})
        MATCH (t:Tag {key: $key, value: $value})
        MERGE (r)-[rel:TAGGED_WITH {namespace: $namespace, key: $key, value: $value}]->(t)
        RETURN rel
        """

        graph.query(
            rel_query,
            params={
                "resource_id": resource_id,
                "tenant_id": tenant_id,
                "key": key,
                "value": value,
                "namespace": TagNamespace.NATIVE.value,
            },
        )

        logger.info(
            f"Stored native tag in FalkorDB for {resource_id}: {key}={value}"
        )

        # 2. Write to MiniStack (if service supports native tagging)
        boto3_written = False

        if resource_type in TAGGABLE_SERVICES:
            try:
                # Get all native tags for resource (to send complete set)
                all_native_tags = get_native_tags(resource_id, tenant_id)

                await _write_native_tag_to_ministack(
                    resource_id, all_native_tags, tenant_id
                )

                boto3_written = True
                logger.info(f"Wrote native tag to MiniStack for {resource_id}")

            except Exception as e:
                logger.warning(
                    f"Native tag write to MiniStack failed for {resource_id}: {e}. "
                    f"FalkorDB update succeeded (partial success)."
                )
                boto3_written = False
        else:
            logger.warning(
                f"Resource type {resource_type} does not support native tagging. "
                f"Tag stored in FalkorDB only."
            )

        # Get new tags for AFTER state
        new_tags = get_native_tags(resource_id, tenant_id)

        # AUDIT log
        log_audit(
            "Native tag added",
            event_type="TAG_ADDED",
            actor={"id": tenant_id, "type": "TENANT"},
            target={"type": "RESOURCE", "id": resource_id},
            action="CREATE",
            status="SUCCESS" if boto3_written else "PARTIAL_SUCCESS",
            changes={"before": old_tags, "after": new_tags},
            namespace=TagNamespace.NATIVE.value,
            boto3_written=boto3_written,
        )

        return {
            "resource_id": resource_id,
            "key": key,
            "value": value,
            "namespace": TagNamespace.NATIVE.value,
            "tenant_id": tenant_id,
            "boto3_written": boto3_written,
            "created_at": datetime.now(UTC).isoformat(),
        }


async def remove_native_tag(
    resource_id: str,
    key: str,
    tenant_id: str,
) -> bool:
    """
    Remove native tag from a resource (dual-delete: FalkorDB + MiniStack).

    Removes tag from FalkorDB, then updates MiniStack with remaining tags.
    Idempotent: returns True even if tag doesn't exist.

    Args:
        resource_id: Resource ID
        key: Tag key to remove
        tenant_id: Tenant ID for isolation

    Returns:
        bool: True if tag was removed or didn't exist

    Raises:
        ValueError: If validation fails
        Exception: If FalkorDB operation fails

    Note:
        If boto3 write fails, FalkorDB deletion still succeeds.
        Partial success is logged as warning.

    Example:
        >>> await remove_native_tag("s3:bucket:my-bucket", "Name", "123456789012")
        True
    """
    validate_tenant_id(tenant_id)
    validate_aws_tag(key, "", is_native=True)  # Validate key format

    with trace_operation(
        "remove_native_tag",
        resource_id=resource_id,
        key=key,
        tenant_id=tenant_id,
    ):
        # Extract resource type
        components = _extract_resource_components(resource_id)
        resource_type = components["type"]

        # Get existing tags for BEFORE state
        old_tags = get_native_tags(resource_id, tenant_id)

        # 1. Remove from FalkorDB
        graph = get_graph()

        delete_query = """
        MATCH (r:Resource {id: $resource_id, tenant_id: $tenant_id})-[rel:TAGGED_WITH]->(t:Tag)
        WHERE rel.namespace = $namespace AND rel.key = $key
        DELETE rel
        RETURN count(rel) AS deleted_count
        """

        result = graph.query(
            delete_query,
            params={
                "resource_id": resource_id,
                "tenant_id": tenant_id,
                "namespace": TagNamespace.NATIVE.value,
                "key": key,
            },
        )

        deleted_count = result.result_set[0][0] if result.result_set else 0

        logger.info(
            f"Removed native tag from FalkorDB for {resource_id}: {key}"
            if deleted_count > 0
            else f"Native tag {key} not found on {resource_id} (no-op)"
        )

        # 2. Update MiniStack with remaining tags (if service supports native tagging)
        boto3_written = False

        if resource_type in TAGGABLE_SERVICES and deleted_count > 0:
            try:
                # Get remaining native tags
                remaining_tags = get_native_tags(resource_id, tenant_id)

                await _write_native_tag_to_ministack(
                    resource_id, remaining_tags, tenant_id
                )

                boto3_written = True
                logger.info(
                    f"Updated MiniStack tags for {resource_id} (removed {key})"
                )

            except Exception as e:
                logger.warning(
                    f"Native tag removal from MiniStack failed for {resource_id}: {e}. "
                    f"FalkorDB deletion succeeded (partial success)."
                )
                boto3_written = False

        # Get new tags for AFTER state
        new_tags = get_native_tags(resource_id, tenant_id)

        # AUDIT log
        log_audit(
            "Native tag removed",
            event_type="TAG_REMOVED",
            actor={"id": tenant_id, "type": "TENANT"},
            target={"type": "RESOURCE", "id": resource_id},
            action="DELETE",
            status="SUCCESS" if deleted_count > 0 else "NO_OP",
            changes={"before": old_tags, "after": new_tags},
            namespace=TagNamespace.NATIVE.value,
            key=key,
            boto3_written=boto3_written,
        )

        return True


def get_native_tags(
    resource_id: str,
    tenant_id: str,
) -> dict[str, str]:
    """
    Get all native tags for a resource from FalkorDB.

    Args:
        resource_id: Resource ID
        tenant_id: Tenant ID for isolation

    Returns:
        Dict mapping tag keys to values

    Raises:
        ValueError: If validation fails
        Exception: If FalkorDB query fails

    Example:
        >>> get_native_tags("s3:bucket:my-bucket", "123456789012")
        {'Name': 'uploads', 'Environment': 'prod'}
    """
    validate_tenant_id(tenant_id)

    with trace_operation(
        "get_native_tags",
        resource_id=resource_id,
        tenant_id=tenant_id,
    ):
        graph = get_graph()

        query = """
        MATCH (r:Resource {id: $resource_id, tenant_id: $tenant_id})-[rel:TAGGED_WITH]->(t:Tag)
        WHERE rel.namespace = $namespace
        RETURN rel.key AS key, rel.value AS value
        """

        result = graph.query(
            query,
            params={
                "resource_id": resource_id,
                "tenant_id": tenant_id,
                "namespace": TagNamespace.NATIVE.value,
            },
        )

        tags = {}
        for record in result.result_set:
            key = record[0]
            value = record[1]
            tags[key] = value

        logger.debug(f"Retrieved {len(tags)} native tags for {resource_id}")

        return tags


async def sync_native_tags_from_ministack(
    resource_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """
    Sync native tags from MiniStack to FalkorDB.

    Reads tags from MiniStack via boto3 and updates FalkorDB.
    Handles invalid keys gracefully: skips them, logs warning, continues.

    Args:
        resource_id: Resource ID
        tenant_id: Tenant ID for isolation

    Returns:
        Dict with sync results:
        {
            "synced_count": int,
            "skipped_count": int,
            "skipped_keys": List[str],
            "error": Optional[str]
        }

    Raises:
        ValueError: If validation fails or resource type not taggable
        Exception: If boto3 operation fails critically

    Example:
        >>> await sync_native_tags_from_ministack("s3:bucket:my-bucket", "123456789012")
        {'synced_count': 2, 'skipped_count': 0, 'skipped_keys': []}
    """
    validate_tenant_id(tenant_id)

    with trace_operation(
        "sync_native_tags_from_ministack",
        resource_id=resource_id,
        tenant_id=tenant_id,
    ):
        components = _extract_resource_components(resource_id)
        resource_type = components["type"]
        resource_name = components["name"]

        if resource_type not in TAGGABLE_SERVICES:
            raise ValueError(
                f"Resource type {resource_type} does not support native tagging"
            )

        # Read tags from MiniStack
        client = MiniStackClient(access_key=tenant_id)
        ministack_tags: dict[str, str] = {}

        try:
            if resource_type == "s3:bucket":
                session = client._get_session()
                async with session.client(
                    "s3", endpoint_url=client.endpoint_url
                ) as s3:
                    try:
                        response = await s3.get_bucket_tagging(Bucket=resource_name)
                        tag_set = response.get("TagSet", [])
                        ministack_tags = {tag["Key"]: tag["Value"] for tag in tag_set}
                    except Exception as e:
                        # Bucket might have no tags
                        if "NoSuchTagSet" in str(e):
                            ministack_tags = {}
                        else:
                            raise

            elif resource_type == "lambda:function":
                if resource_id.startswith("arn:"):
                    arn = resource_id
                else:
                    arn = f"arn:aws:lambda:us-east-1:{tenant_id}:function:{resource_name}"

                session = client._get_session()
                async with session.client(
                    "lambda", endpoint_url=client.endpoint_url
                ) as lambda_client:
                    response = await lambda_client.list_tags(Resource=arn)
                    ministack_tags = response.get("Tags", {})

            elif resource_type == "dynamodb:table":
                if resource_id.startswith("arn:"):
                    arn = resource_id
                else:
                    arn = f"arn:aws:dynamodb:us-east-1:{tenant_id}:table/{resource_name}"

                session = client._get_session()
                async with session.client(
                    "dynamodb", endpoint_url=client.endpoint_url
                ) as dynamodb:
                    response = await dynamodb.list_tags_of_resource(ResourceArn=arn)
                    tag_list = response.get("Tags", [])
                    ministack_tags = {tag["Key"]: tag["Value"] for tag in tag_list}

        except Exception as e:
            logger.error(f"Failed to read tags from MiniStack for {resource_id}: {e}")
            return {
                "synced_count": 0,
                "skipped_count": 0,
                "skipped_keys": [],
                "error": str(e),
            }

        # Sync tags to FalkorDB (skip invalid keys)
        synced_count = 0
        skipped_count = 0
        skipped_keys: list[str] = []

        for key, value in ministack_tags.items():
            try:
                validate_aws_tag(key, value, is_native=True)

                # Add to FalkorDB (idempotent)
                await add_native_tag(resource_id, key, value, tenant_id)

                synced_count += 1

            except ValueError as e:
                # Skip invalid keys, log warning, continue
                logger.warning(
                    f"Skipping invalid tag from MiniStack: {key}={value}, error: {e}"
                )
                skipped_count += 1
                skipped_keys.append(key)
                continue

        logger.info(
            f"Synced {synced_count} tags from MiniStack for {resource_id} "
            f"(skipped {skipped_count} invalid keys)"
        )

        return {
            "synced_count": synced_count,
            "skipped_count": skipped_count,
            "skipped_keys": skipped_keys,
            "error": None,
        }
