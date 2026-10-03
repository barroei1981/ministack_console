"""
MCP Tools implementation for write operations (create, update, delete).
"""

import httpx
from mcp_server.config import config
from mcp_server.transactions import (
    add_resource_to_transaction,
    confirm_transaction,
    create_transaction,
    get_transaction,
    mark_transaction_failed,
    mark_transaction_rolled_back,
)


# S3 Operations

async def create_s3_bucket(
    name: str,
    tenant_id: str,
    project: str | None = None,
    versioning: bool = False,
    encryption: bool = False,
) -> dict:
    """
    Create an S3 bucket.

    Args:
        name: Bucket name
        tenant_id: Tenant ID
        project: Optional project tag
        versioning: Enable versioning
        encryption: Enable server-side encryption

    Returns:
        Dict with bucket details
    """
    payload = {
        "name": name,
        "tenant_id": tenant_id,
        "project": project,
        "versioning": versioning,
        "encryption": encryption,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.api_base_url}/api/resources/s3/buckets",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def delete_s3_bucket(name: str, tenant_id: str, force: bool = False) -> dict:
    """
    Delete an S3 bucket.

    Args:
        name: Bucket name
        tenant_id: Tenant ID
        force: Force delete even if not empty

    Returns:
        Dict with deletion confirmation
    """
    params = {"tenant_id": tenant_id}
    if force:
        params["force"] = "true"

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{config.api_base_url}/api/resources/s3/buckets/{name}",
            params=params,
        )
        response.raise_for_status()
        return response.json()


# Lambda Operations

async def create_lambda_function(
    name: str,
    runtime: str,
    handler: str,
    code_base64: str,
    tenant_id: str,
    project: str | None = None,
    environment: dict | None = None,
    memory: int = 128,
    timeout: int = 3,
) -> dict:
    """
    Create a Lambda function.

    Args:
        name: Function name
        runtime: Runtime (e.g., python3.11, nodejs18.x)
        handler: Handler (e.g., index.handler)
        code_base64: Base64-encoded code ZIP
        tenant_id: Tenant ID
        project: Optional project tag
        environment: Optional environment variables
        memory: Memory in MB
        timeout: Timeout in seconds

    Returns:
        Dict with function details
    """
    payload = {
        "name": name,
        "runtime": runtime,
        "handler": handler,
        "code_base64": code_base64,
        "tenant_id": tenant_id,
        "project": project,
        "environment": environment or {},
        "memory": memory,
        "timeout": timeout,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{config.api_base_url}/api/resources/lambda/functions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def delete_lambda_function(name: str, tenant_id: str) -> dict:
    """
    Delete a Lambda function.

    Args:
        name: Function name
        tenant_id: Tenant ID

    Returns:
        Dict with deletion confirmation
    """
    params = {"tenant_id": tenant_id}

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{config.api_base_url}/api/resources/lambda/functions/{name}",
            params=params,
        )
        response.raise_for_status()
        return response.json()


# DynamoDB Operations

async def create_dynamodb_table(
    name: str,
    partition_key: dict,  # {"AttributeName": "id", "KeyType": "HASH"}
    tenant_id: str,
    sort_key: dict | None = None,  # {"AttributeName": "timestamp", "KeyType": "RANGE"}
    billing_mode: str = "PAY_PER_REQUEST",
    project: str | None = None,
) -> dict:
    """
    Create a DynamoDB table.

    Args:
        name: Table name
        partition_key: Partition key definition
        tenant_id: Tenant ID
        sort_key: Optional sort key definition
        billing_mode: PAY_PER_REQUEST or PROVISIONED
        project: Optional project tag

    Returns:
        Dict with table details
    """
    key_schema = [partition_key]
    if sort_key:
        key_schema.append(sort_key)

    # Attribute definitions from keys
    attribute_definitions = [
        {
            "AttributeName": partition_key["AttributeName"],
            "AttributeType": "S",  # Default to string
        }
    ]
    if sort_key:
        attribute_definitions.append(
            {
                "AttributeName": sort_key["AttributeName"],
                "AttributeType": "S",
            }
        )

    payload = {
        "name": name,
        "key_schema": key_schema,
        "attribute_definitions": attribute_definitions,
        "billing_mode": billing_mode,
        "tenant_id": tenant_id,
        "project": project,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.api_base_url}/api/resources/dynamodb/tables",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def delete_dynamodb_table(name: str, tenant_id: str) -> dict:
    """
    Delete a DynamoDB table.

    Args:
        name: Table name
        tenant_id: Tenant ID

    Returns:
        Dict with deletion confirmation
    """
    params = {"tenant_id": tenant_id}

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{config.api_base_url}/api/resources/dynamodb/tables/{name}",
            params=params,
        )
        response.raise_for_status()
        return response.json()


# Bulk Operations

async def bulk_delete_project_resources(project_name: str, tenant_id: str) -> dict:
    """
    Delete all resources in a project (bulk operation).

    Args:
        project_name: Project name
        tenant_id: Tenant ID

    Returns:
        Dict with bulk delete results
    """
    params = {"tenant_id": tenant_id}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.delete(
            f"{config.api_base_url}/api/projects/{project_name}/resources",
            params=params,
        )
        response.raise_for_status()
        return response.json()
