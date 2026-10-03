"""
MCP Resources implementation for read operations.
"""

import httpx
from mcp_server.config import config


async def list_tenants() -> dict:
    """
    List all tenants via REST API.

    Returns:
        Dict with tenants list
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{config.api_base_url}/api/tenants")
        response.raise_for_status()
        return response.json()


async def list_tenant_resources(tenant_id: str) -> dict:
    """
    List all resources for a specific tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        Dict with resources list
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.api_base_url}/api/tenants/{tenant_id}/resources"
        )
        response.raise_for_status()
        return response.json()


async def list_s3_buckets(tenant_id: str) -> dict:
    """
    List S3 buckets for a specific tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        Dict with buckets list
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.api_base_url}/api/resources/s3/buckets",
            params={"tenant_id": tenant_id},
        )
        response.raise_for_status()
        return response.json()


async def list_lambda_functions(tenant_id: str) -> dict:
    """
    List Lambda functions for a specific tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        Dict with functions list
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.api_base_url}/api/resources/lambda/functions",
            params={"tenant_id": tenant_id},
        )
        response.raise_for_status()
        return response.json()


async def list_dynamodb_tables(tenant_id: str) -> dict:
    """
    List DynamoDB tables for a specific tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        Dict with tables list
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.api_base_url}/api/resources/dynamodb/tables",
            params={"tenant_id": tenant_id},
        )
        response.raise_for_status()
        return response.json()


async def get_resource_dependencies(resource_id: str, tenant_id: str) -> dict:
    """
    Get dependencies for a specific resource.

    Args:
        resource_id: Resource ID
        tenant_id: Tenant ID

    Returns:
        Dict with dependencies
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.api_base_url}/api/resources/{resource_id}/dependencies",
            params={"tenant_id": tenant_id},
        )
        response.raise_for_status()
        return response.json()


async def search_resources(query: str, tenant_id: str | None = None, service_type: str | None = None) -> dict:
    """
    Search resources by query string.

    Args:
        query: Search query
        tenant_id: Optional tenant filter
        service_type: Optional service type filter

    Returns:
        Dict with search results
    """
    params = {"q": query}
    if tenant_id:
        params["tenant_id"] = tenant_id
    if service_type:
        params["service_type"] = service_type

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.api_base_url}/api/search/resources",
            params=params,
        )
        response.raise_for_status()
        return response.json()


async def get_resource_graph(tenant_id: str | None = None, service_type: str | None = None) -> dict:
    """
    Get resource graph for visualization.

    Args:
        tenant_id: Optional tenant filter
        service_type: Optional service type filter

    Returns:
        Dict with nodes and edges
    """
    params = {}
    if tenant_id:
        params["tenant_id"] = tenant_id
    if service_type:
        params["service_type"] = service_type

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.api_base_url}/api/graph/resources",
            params=params,
        )
        response.raise_for_status()
        return response.json()
