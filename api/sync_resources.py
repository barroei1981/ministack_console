"""
Sync existing MiniStack resources into the Control-Plane.

This script discovers resources already in MiniStack and imports them
into FalkorDB so the Control-Plane knows about them.
"""

import asyncio
import logging
import sys
from typing import Any

import boto3
from botocore.config import Config

# Add parent directory to path for imports
sys.path.insert(0, '/app')

from control_plane.graph.query import create_node, get_graph

logger = logging.getLogger(__name__)


def log_operational(message: str):
    """Simple logging wrapper."""
    logger.info(message)
    print(message)


def get_boto3_client(service: str, endpoint_url: str, tenant_id: str):
    """Create boto3 client for a service."""
    return boto3.client(
        service,
        endpoint_url=endpoint_url,
        aws_access_key_id=tenant_id,
        aws_secret_access_key="dummy",
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


async def sync_s3_buckets(endpoint_url: str, tenant_id: str, project: str | None = None) -> int:
    """Discover and import S3 buckets."""
    s3 = get_boto3_client("s3", endpoint_url, tenant_id)

    try:
        response = s3.list_buckets()
        buckets = response.get("Buckets", [])

        imported = 0
        for bucket in buckets:
            bucket_name = bucket["Name"]

            # Check if already exists in FalkorDB
            graph = get_graph()
            existing = graph.query(
                "MATCH (n:Resource) WHERE n.id = $id AND n.tenant_id = $tenant_id RETURN n",
                {"id": bucket_name, "tenant_id": tenant_id}
            ).result_set

            if existing:
                log_operational(f"S3 bucket {bucket_name} already in FalkorDB, skipping")
                continue

            # Get bucket details
            try:
                versioning = s3.get_bucket_versioning(Bucket=bucket_name)
                versioning_enabled = versioning.get("Status") == "Enabled"
            except:
                versioning_enabled = False

            try:
                encryption = s3.get_bucket_encryption(Bucket=bucket_name)
                encryption_enabled = True
            except:
                encryption_enabled = False

            # Create node in FalkorDB
            node_id = f"s3:bucket:{bucket_name}"
            create_node(
                "Resource",
                {
                    "id": node_id,
                    "name": bucket_name,
                    "type": "s3:bucket",
                    "tenant_id": tenant_id,
                    "project": project or "imported",
                    "versioning": versioning_enabled,
                    "encryption": encryption_enabled,
                    "created_at": bucket["CreationDate"].isoformat(),
                },
            )

            log_operational(f"Imported S3 bucket: {bucket_name}")
            imported += 1

        return imported
    except Exception as e:
        log_operational(f"Error syncing S3 buckets: {e}")
        return 0


async def sync_dynamodb_tables(endpoint_url: str, tenant_id: str, project: str | None = None) -> int:
    """Discover and import DynamoDB tables."""
    log_operational(f"[DynamoDB] Starting sync for tenant {tenant_id}")

    dynamodb = get_boto3_client("dynamodb", endpoint_url, tenant_id)

    try:
        log_operational("[DynamoDB] Calling list_tables()")
        response = dynamodb.list_tables()
        table_names = response.get("TableNames", [])
        log_operational(f"[DynamoDB] Got {len(table_names)} tables from list_tables()")

        log_operational(f"Found {len(table_names)} DynamoDB tables to sync")

        imported = 0
        for table_name in table_names:
            log_operational(f"Checking table: {table_name}")

            # Check if already exists
            node_id = f"dynamodb:table:{table_name}"

            try:
                graph = get_graph()
                existing = graph.query(
                    "MATCH (n:Resource) WHERE n.id = $id AND n.tenant_id = $tenant_id RETURN n",
                    {"id": node_id, "tenant_id": tenant_id}
                ).result_set

                if existing:
                    log_operational(f"Table {table_name} already exists, skipping")
                    continue
            except Exception as e:
                log_operational(f"Error checking existing node: {e}")
                # Continue anyway - try to create

            # Get table details
            table_desc = dynamodb.describe_table(TableName=table_name)
            table = table_desc["Table"]

            arn = f"arn:aws:dynamodb:us-east-1:{tenant_id}:table/{table_name}"
            billing_mode = table.get("BillingModeSummary", {}).get("BillingMode", "PAY_PER_REQUEST")

            # Store key_schema and attribute_definitions as JSON strings for caching
            import json
            key_schema_json = json.dumps(table.get("KeySchema", []))
            attr_def_json = json.dumps(table.get("AttributeDefinitions", []))

            node_data = {
                "id": node_id,
                "name": table_name,
                "type": "dynamodb:table",
                "tenant_id": tenant_id,
                "project": project or "imported",
                "arn": arn,
                "created_at": table["CreationDateTime"].isoformat(),
                "table_status": table["TableStatus"],
                "item_count": int(table.get("ItemCount", 0)),
                "billing_mode": billing_mode,
                "key_schema": key_schema_json,
                "attribute_definitions": attr_def_json,
            }

            try:
                create_node("Resource", node_data)
            except Exception as e:
                log_operational(f"Failed to create node for {table_name}: {e}")
                raise

            log_operational(f"Imported DynamoDB table: {table_name}")
            imported += 1

        return imported
    except Exception as e:
        log_operational(f"Error syncing DynamoDB tables: {e}")
        return 0


async def sync_cognito_user_pools(endpoint_url: str, tenant_id: str, project: str | None = None) -> int:
    """Discover and import Cognito user pools."""
    cognito = get_boto3_client("cognito-idp", endpoint_url, tenant_id)

    try:
        response = cognito.list_user_pools(MaxResults=60)
        pools = response.get("UserPools", [])

        imported = 0
        for pool in pools:
            pool_id = pool["Id"]
            pool_name = pool["Name"]

            # Check if already exists
            node_id = f"cognito:userpool:{pool_id}"
            graph = get_graph()
            existing = graph.query(
                "MATCH (n:Resource) WHERE n.id = $id AND n.tenant_id = $tenant_id RETURN n",
                {"id": node_id, "tenant_id": tenant_id}
            ).result_set

            if existing:
                log_operational(f"Cognito user pool {pool_name} already exists, skipping")
                continue

            # Create node
            create_node(
                "Resource",
                {
                    "id": node_id,
                    "name": pool_name,
                    "type": "cognito:userpool",
                    "tenant_id": tenant_id,
                    "project": project or "imported",
                    "pool_id": pool_id,
                    "status": pool.get("Status", "UNKNOWN"),
                    "created_at": pool["CreationDate"].isoformat() if "CreationDate" in pool else "",
                    "last_modified": pool["LastModifiedDate"].isoformat() if "LastModifiedDate" in pool else "",
                },
            )

            log_operational(f"Imported Cognito user pool: {pool_name}")
            imported += 1

        return imported
    except Exception as e:
        log_operational(f"Error syncing Cognito user pools: {e}")
        return 0


async def sync_lambda_functions(endpoint_url: str, tenant_id: str, project: str | None = None) -> int:
    """Discover and import Lambda functions."""
    lambda_client = get_boto3_client("lambda", endpoint_url, tenant_id)

    try:
        response = lambda_client.list_functions()
        functions = response.get("Functions", [])

        imported = 0
        for func in functions:
            func_name = func["FunctionName"]

            # Check if already exists
            graph = get_graph()
            node_id = f"lambda:function:{func_name}"
            existing = graph.query(
                "MATCH (n:Resource) WHERE n.id = $id AND n.tenant_id = $tenant_id RETURN n",
                {"id": node_id, "tenant_id": tenant_id}
            ).result_set

            if existing:
                log_operational(f"Lambda function {func_name} already in FalkorDB, skipping")
                continue

            create_node(
                "Resource",
                {
                    "id": node_id,
                    "name": func_name,
                    "type": "lambda:function",
                    "tenant_id": tenant_id,
                    "project": project or "imported",
                    "runtime": func.get("Runtime", "unknown"),
                    "handler": func.get("Handler", "unknown"),
                    "memory": func.get("MemorySize", 128),
                    "timeout": func.get("Timeout", 3),
                    "last_modified": func.get("LastModified", ""),
                },
            )

            log_operational(f"Imported Lambda function: {func_name}")
            imported += 1

        return imported
    except Exception as e:
        log_operational(f"Error syncing Lambda functions: {e}")
        return 0


async def sync_all_resources(
    endpoint_url: str = "http://localhost:4566",
    tenant_id: str = "000000000001",
    project: str | None = None
):
    """Sync all resources from MiniStack to Control-Plane."""
    log_operational(f"Starting resource sync for tenant {tenant_id}")

    s3_count = await sync_s3_buckets(endpoint_url, tenant_id, project)
    dynamodb_count = await sync_dynamodb_tables(endpoint_url, tenant_id, project)
    cognito_count = await sync_cognito_user_pools(endpoint_url, tenant_id, project)
    ses_count = await sync_ses_identities(endpoint_url, tenant_id, project)
    sqs_count = await sync_sqs_queues(endpoint_url, tenant_id, project)
    lambda_count = await sync_lambda_functions(endpoint_url, tenant_id, project)

    total = s3_count + dynamodb_count + cognito_count + ses_count + sqs_count + lambda_count

    log_operational(
        f"Sync complete: {s3_count} S3 buckets, {dynamodb_count} DynamoDB tables, "
        f"{cognito_count} Cognito pools, {ses_count} SES identities, {sqs_count} SQS queues, {lambda_count} Lambda functions ({total} total)"
    )

    return {
        "s3_buckets": s3_count,
        "dynamodb_tables": dynamodb_count,
        "cognito_user_pools": cognito_count,
        "ses_identities": ses_count,
        "sqs_queues": sqs_count,
        "lambda_functions": lambda_count,
        "total": total,
    }


if __name__ == "__main__":
    tenant_id = sys.argv[1] if len(sys.argv) > 1 else "000000000001"
    project = sys.argv[2] if len(sys.argv) > 2 else None

    result = asyncio.run(sync_all_resources(tenant_id=tenant_id, project=project))
    print(f"\nImported {result['total']} resources:")
    print(f"  S3 buckets: {result['s3_buckets']}")
    print(f"  DynamoDB tables: {result['dynamodb_tables']}")
    print(f"  Cognito user pools: {result['cognito_user_pools']}")
    print(f"  SQS queues: {result['sqs_queues']}")
    print(f"  Lambda functions: {result['lambda_functions']}")


async def sync_sqs_queues(endpoint_url: str, tenant_id: str, project: str | None = None) -> int:
    """Discover and import SQS queues."""
    sqs = get_boto3_client("sqs", endpoint_url, tenant_id)

    try:
        response = sqs.list_queues()
        queue_urls = response.get("QueueUrls", [])

        imported = 0
        for queue_url in queue_urls:
            # Extract queue name from URL
            queue_name = queue_url.split("/")[-1]

            # Check if already exists
            node_id = f"sqs:queue:{queue_name}"
            graph = get_graph()
            existing = graph.query(
                "MATCH (n:Resource) WHERE n.id = $id AND n.tenant_id = $tenant_id RETURN n",
                {"id": node_id, "tenant_id": tenant_id}
            ).result_set

            if existing:
                log_operational(f"SQS queue {queue_name} already exists, skipping")
                continue

            # Get queue attributes
            attrs = sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["ApproximateNumberOfMessages", "CreatedTimestamp", "QueueArn"]
            ).get("Attributes", {})

            # Create node
            create_node(
                "Resource",
                {
                    "id": node_id,
                    "name": queue_name,
                    "type": "sqs:queue",
                    "tenant_id": tenant_id,
                    "project": project or "imported",
                    "queue_url": queue_url,
                    "arn": attrs.get("QueueArn", ""),
                    "message_count": int(attrs.get("ApproximateNumberOfMessages", 0)),
                    "created_timestamp": attrs.get("CreatedTimestamp", ""),
                },
            )

            log_operational(f"Imported SQS queue: {queue_name}")
            imported += 1

        return imported
    except Exception as e:
        log_operational(f"Error syncing SQS queues: {e}")
        return 0


async def sync_ses_identities(endpoint_url: str, tenant_id: str, project: str | None = None) -> int:
    """Discover and import SES verified email identities."""
    ses = get_boto3_client("ses", endpoint_url, tenant_id)

    try:
        response = ses.list_identities()
        identities = response.get("Identities", [])

        # Get verification status
        if identities:
            attrs_response = ses.get_identity_verification_attributes(Identities=identities)
            verification_attrs = attrs_response.get("VerificationAttributes", {})
        else:
            verification_attrs = {}

        imported = 0
        for identity in identities:
            # Check if already exists
            node_id = f"ses:identity:{identity}"
            graph = get_graph()
            existing = graph.query(
                "MATCH (n:Resource) WHERE n.id = $id AND n.tenant_id = $tenant_id RETURN n",
                {"id": node_id, "tenant_id": tenant_id}
            ).result_set

            if existing:
                log_operational(f"SES identity {identity} already exists, skipping")
                continue

            # Get verification status
            attrs = verification_attrs.get(identity, {})
            verification_status = attrs.get("VerificationStatus", "Unknown")

            # Create node
            create_node(
                "Resource",
                {
                    "id": node_id,
                    "name": identity,
                    "type": "ses:identity",
                    "tenant_id": tenant_id,
                    "project": project or "imported",
                    "verification_status": verification_status,
                },
            )

            log_operational(f"Imported SES identity: {identity} ({verification_status})")
            imported += 1

        return imported
    except Exception as e:
        log_operational(f"Error syncing SES identities: {e}")
        return 0
