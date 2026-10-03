"""
MCP Server implementation.

Exposes MiniStack Console control-plane data via Model Context Protocol.
"""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from mcp_server.config import config
from mcp_server.resources import (
    get_resource_dependencies,
    get_resource_graph,
    list_dynamodb_tables,
    list_lambda_functions,
    list_s3_buckets,
    list_tenant_resources,
    list_tenants,
    search_resources,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create MCP server
app = Server("ministack-console")


@app.list_resources()
async def list_resources_handler() -> list[Resource]:
    """
    List available MCP resources.

    Returns:
        List of Resource objects
    """
    return [
        Resource(
            uri="ministack://tenants",
            name="Tenants",
            description="List all tenants with resource counts",
            mimeType="application/json",
        ),
        Resource(
            uri="ministack://tenant/{tenant_id}/resources",
            name="Tenant Resources",
            description="List all resources for a specific tenant",
            mimeType="application/json",
        ),
        Resource(
            uri="ministack://resources/s3/buckets",
            name="S3 Buckets",
            description="List S3 buckets (requires tenant_id query param)",
            mimeType="application/json",
        ),
        Resource(
            uri="ministack://resources/lambda/functions",
            name="Lambda Functions",
            description="List Lambda functions (requires tenant_id query param)",
            mimeType="application/json",
        ),
        Resource(
            uri="ministack://resources/dynamodb/tables",
            name="DynamoDB Tables",
            description="List DynamoDB tables (requires tenant_id query param)",
            mimeType="application/json",
        ),
        Resource(
            uri="ministack://resource/{resource_id}/dependencies",
            name="Resource Dependencies",
            description="Get dependencies for a specific resource",
            mimeType="application/json",
        ),
        Resource(
            uri="ministack://search/resources",
            name="Search Resources",
            description="Search resources by query string",
            mimeType="application/json",
        ),
        Resource(
            uri="ministack://graph/resources",
            name="Resource Graph",
            description="Get resource graph with nodes and edges",
            mimeType="application/json",
        ),
    ]


@app.read_resource()
async def read_resource_handler(uri: str) -> str:
    """
    Read a specific resource by URI.

    Args:
        uri: Resource URI (e.g., "ministack://tenants")

    Returns:
        JSON string with resource data

    Raises:
        ValueError: If URI is not recognized
    """
    logger.info(f"Reading resource: {uri}")

    # Parse URI and extract components
    if not uri.startswith("ministack://"):
        raise ValueError(f"Invalid URI scheme: {uri}")

    path = uri.replace("ministack://", "")

    # Parse query parameters if present
    query_params = {}
    if "?" in path:
        path, query_string = path.split("?", 1)
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                query_params[key] = value

    try:
        # Route based on path
        if path == "tenants":
            data = await list_tenants()

        elif path.startswith("tenant/") and path.endswith("/resources"):
            # Extract tenant_id from path
            parts = path.split("/")
            if len(parts) != 3:
                raise ValueError(f"Invalid tenant resources URI: {uri}")
            tenant_id = parts[1]
            data = await list_tenant_resources(tenant_id)

        elif path == "resources/s3/buckets":
            tenant_id = query_params.get("tenant_id")
            if not tenant_id:
                raise ValueError("tenant_id query parameter required")
            data = await list_s3_buckets(tenant_id)

        elif path == "resources/lambda/functions":
            tenant_id = query_params.get("tenant_id")
            if not tenant_id:
                raise ValueError("tenant_id query parameter required")
            data = await list_lambda_functions(tenant_id)

        elif path == "resources/dynamodb/tables":
            tenant_id = query_params.get("tenant_id")
            if not tenant_id:
                raise ValueError("tenant_id query parameter required")
            data = await list_dynamodb_tables(tenant_id)

        elif path.startswith("resource/") and path.endswith("/dependencies"):
            # Extract resource_id from path
            parts = path.split("/")
            if len(parts) != 3:
                raise ValueError(f"Invalid resource dependencies URI: {uri}")
            resource_id = parts[1]
            tenant_id = query_params.get("tenant_id")
            if not tenant_id:
                raise ValueError("tenant_id query parameter required")
            data = await get_resource_dependencies(resource_id, tenant_id)

        elif path == "search/resources":
            query = query_params.get("q")
            if not query:
                raise ValueError("q query parameter required")
            tenant_id = query_params.get("tenant_id")
            service_type = query_params.get("service_type")
            data = await search_resources(query, tenant_id, service_type)

        elif path == "graph/resources":
            tenant_id = query_params.get("tenant_id")
            service_type = query_params.get("service_type")
            data = await get_resource_graph(tenant_id, service_type)

        else:
            raise ValueError(f"Unknown resource path: {path}")

        return json.dumps(data, indent=2)

    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}")
        raise


async def main():
    """
    Main entry point for MCP server.
    """
    logger.info(f"Starting MiniStack Console MCP Server (port {config.port})")
    logger.info(f"API base URL: {config.api_base_url}")
    logger.info(f"Dev mode: {config.dev_mode}")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
