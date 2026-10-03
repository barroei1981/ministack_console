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
from mcp_server.tools import (
    bulk_delete_project_resources,
    create_dynamodb_table,
    create_lambda_function,
    create_s3_bucket,
    delete_dynamodb_table,
    delete_lambda_function,
    delete_s3_bucket,
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


@app.list_tools()
async def list_tools_handler() -> list[Tool]:
    """
    List available MCP tools.

    Returns:
        List of Tool objects
    """
    return [
        Tool(
            name="create_s3_bucket",
            description="Create an S3 bucket in MiniStack",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Bucket name (3-63 chars, lowercase)"},
                    "tenant_id": {"type": "string", "description": "Tenant ID (12 digits)"},
                    "project": {"type": "string", "description": "Optional project tag"},
                    "versioning": {"type": "boolean", "description": "Enable versioning", "default": False},
                    "encryption": {"type": "boolean", "description": "Enable server-side encryption", "default": False},
                },
                "required": ["name", "tenant_id"],
            },
        ),
        Tool(
            name="delete_s3_bucket",
            description="Delete an S3 bucket from MiniStack",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Bucket name"},
                    "tenant_id": {"type": "string", "description": "Tenant ID (12 digits)"},
                    "force": {"type": "boolean", "description": "Force delete even if not empty", "default": False},
                },
                "required": ["name", "tenant_id"],
            },
        ),
        Tool(
            name="create_lambda_function",
            description="Create a Lambda function in MiniStack",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Function name"},
                    "runtime": {"type": "string", "description": "Runtime (e.g., python3.11, nodejs18.x)"},
                    "handler": {"type": "string", "description": "Handler (e.g., index.handler)"},
                    "code_base64": {"type": "string", "description": "Base64-encoded code ZIP"},
                    "tenant_id": {"type": "string", "description": "Tenant ID (12 digits)"},
                    "project": {"type": "string", "description": "Optional project tag"},
                    "environment": {"type": "object", "description": "Environment variables", "default": {}},
                    "memory": {"type": "integer", "description": "Memory in MB", "default": 128},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 3},
                },
                "required": ["name", "runtime", "handler", "code_base64", "tenant_id"],
            },
        ),
        Tool(
            name="delete_lambda_function",
            description="Delete a Lambda function from MiniStack",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Function name"},
                    "tenant_id": {"type": "string", "description": "Tenant ID (12 digits)"},
                },
                "required": ["name", "tenant_id"],
            },
        ),
        Tool(
            name="create_dynamodb_table",
            description="Create a DynamoDB table in MiniStack",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Table name"},
                    "partition_key": {
                        "type": "object",
                        "description": "Partition key (e.g., {AttributeName: 'id', KeyType: 'HASH'})",
                    },
                    "tenant_id": {"type": "string", "description": "Tenant ID (12 digits)"},
                    "sort_key": {
                        "type": "object",
                        "description": "Optional sort key (e.g., {AttributeName: 'timestamp', KeyType: 'RANGE'})",
                    },
                    "billing_mode": {
                        "type": "string",
                        "description": "PAY_PER_REQUEST or PROVISIONED",
                        "default": "PAY_PER_REQUEST",
                    },
                    "project": {"type": "string", "description": "Optional project tag"},
                },
                "required": ["name", "partition_key", "tenant_id"],
            },
        ),
        Tool(
            name="delete_dynamodb_table",
            description="Delete a DynamoDB table from MiniStack",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Table name"},
                    "tenant_id": {"type": "string", "description": "Tenant ID (12 digits)"},
                },
                "required": ["name", "tenant_id"],
            },
        ),
        Tool(
            name="bulk_delete_project_resources",
            description="Delete all resources in a project (destructive bulk operation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project name"},
                    "tenant_id": {"type": "string", "description": "Tenant ID (12 digits)"},
                },
                "required": ["project_name", "tenant_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool_handler(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Execute a tool by name with given arguments.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of TextContent with results

    Raises:
        ValueError: If tool name is not recognized
    """
    logger.info(f"Calling tool: {name} with arguments: {arguments}")

    try:
        if name == "create_s3_bucket":
            result = await create_s3_bucket(**arguments)
        elif name == "delete_s3_bucket":
            result = await delete_s3_bucket(**arguments)
        elif name == "create_lambda_function":
            result = await create_lambda_function(**arguments)
        elif name == "delete_lambda_function":
            result = await delete_lambda_function(**arguments)
        elif name == "create_dynamodb_table":
            result = await create_dynamodb_table(**arguments)
        elif name == "delete_dynamodb_table":
            result = await delete_dynamodb_table(**arguments)
        elif name == "bulk_delete_project_resources":
            result = await bulk_delete_project_resources(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        logger.error(f"Tool {name} failed: {error_msg}")
        return [TextContent(type="text", text=f"Error: {error_msg}")]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return [TextContent(type="text", text=f"Error: {e!s}")]


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
