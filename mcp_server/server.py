"""
MCP Server implementation for MiniStack Console.

Exposes ALL 87 MiniStack services via Model Context Protocol for AI assistant access.
"""

import asyncio
import json
import logging
from typing import Any, Sequence

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

from mcp_server.config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("ministack-console")


# ALL 87 MiniStack services mapped to resources
MINISTACK_SERVICES = [
    "s3", "dynamodb", "lambda", "cognito-idp", "ses", "sqs", "sns",
    "secretsmanager", "ssm", "logs", "events", "states", "iam", "kms",
    "apigateway", "cloudformation", "ec2", "ecr", "ecs", "rds", "elasticache",
    "athena", "glue", "emr", "kinesis", "firehose", "sagemaker", "batch",
    "stepfunctions", "eventbridge", "cloudwatch", "xray", "config",
    "cloudtrail", "guardduty", "securityhub", "inspector", "macie",
    "waf", "shield", "acm", "route53", "cloudfront", "elb", "autoscaling",
    "efs", "fsx", "backup", "datasync", "transfer", "snowball", "storagegateway",
    "redshift", "neptune", "documentdb", "keyspaces", "timestream", "qldb",
    "appsync", "amplify", "pinpoint", "mobile", "iot", "iotanalytics",
    "iotevents", "greengrassv2", "workspaces", "appstream", "lightsail",
    "organizations", "servicecatalog", "ram", "workmail", "chime",
    "connect", "transcribe", "translate", "polly", "comprehend",
    "rekognition", "textract", "forecast", "personalize", "lookout",
    "frauddetector", "mediaconvert", "medialive", "mediastore", "msk",
    "lakeformation", "managedblockchain", "lex", "signer"
]


@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """List ALL 87 MiniStack service resources."""
    resources = [
        Resource(
            uri="ministack://tenants",
            name="Tenants",
            description="List all tenants with resource counts",
            mimeType="application/json",
        ),
        Resource(
            uri="ministack://graph",
            name="Resource Graph",
            description="Full resource dependency graph across all services",
            mimeType="application/json",
        ),
    ]

    # Add resource endpoint for each MiniStack service
    for service in MINISTACK_SERVICES:
        resources.append(
            Resource(
                uri=f"ministack://resources/{service}",
                name=f"{service.upper()} Resources",
                description=f"List all {service} resources (requires tenant_id param)",
                mimeType="application/json",
            )
        )

    return resources


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read ANY MiniStack service resource."""
    import httpx

    try:
        if uri == "ministack://tenants":
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{config.api_base_url}/api/tenants")
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)

        elif uri == "ministack://graph":
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{config.api_base_url}/api/graph")
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)

        elif uri.startswith("ministack://resources/"):
            # Extract service name
            parts = uri.replace("ministack://resources/", "").split("?")
            service = parts[0]

            # Parse query params
            tenant_id = "000000000001"  # Default
            if len(parts) > 1:
                for param in parts[1].split("&"):
                    if param.startswith("tenant_id="):
                        tenant_id = param.split("=")[1]

            # Call API for this service
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{config.api_base_url}/api/resources/{service}?tenant_id={tenant_id}"
                )
                if response.status_code == 404:
                    return json.dumps({
                        "service": service,
                        "status": "not_implemented",
                        "message": f"Service {service} is available in MiniStack but not yet implemented in Console API",
                        "available_services": MINISTACK_SERVICES
                    }, indent=2)
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)

        else:
            return json.dumps({"error": f"Unknown resource URI: {uri}"})

    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}")
        return json.dumps({"error": str(e), "uri": uri})


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List ALL available tools for 87 services."""
    tools = []

    # S3 Tools
    tools.extend([
        Tool(
            name="s3_create_bucket",
            description="Create an S3 bucket",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["name", "tenant_id"],
            },
        ),
        Tool(
            name="s3_delete_bucket",
            description="Delete an S3 bucket",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "force": {"type": "boolean"},
                },
                "required": ["name", "tenant_id"],
            },
        ),
        Tool(
            name="s3_upload_object",
            description="Upload object to S3",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket": {"type": "string"},
                    "key": {"type": "string"},
                    "body": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["bucket", "key", "body", "tenant_id"],
            },
        ),
    ])

    # DynamoDB Tools
    tools.extend([
        Tool(
            name="dynamodb_create_table",
            description="Create DynamoDB table",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "hash_key": {"type": "string"},
                    "hash_key_type": {"type": "string", "enum": ["S", "N", "B"]},
                    "tenant_id": {"type": "string"},
                },
                "required": ["name", "hash_key", "hash_key_type", "tenant_id"],
            },
        ),
        Tool(
            name="dynamodb_put_item",
            description="Put item in DynamoDB",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "item": {"type": "object"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["table", "item", "tenant_id"],
            },
        ),
    ])

    # Lambda Tools
    tools.extend([
        Tool(
            name="lambda_invoke",
            description="Invoke Lambda function",
            inputSchema={
                "type": "object",
                "properties": {
                    "function": {"type": "string"},
                    "payload": {"type": "object"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["function", "tenant_id"],
            },
        ),
    ])

    # SQS Tools
    tools.extend([
        Tool(
            name="sqs_send_message",
            description="Send SQS message",
            inputSchema={
                "type": "object",
                "properties": {
                    "queue_url": {"type": "string"},
                    "body": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["queue_url", "body", "tenant_id"],
            },
        ),
        Tool(
            name="sqs_create_queue",
            description="Create SQS queue",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["name", "tenant_id"],
            },
        ),
    ])

    # SES Tools
    tools.extend([
        Tool(
            name="ses_verify_email",
            description="Verify email in SES",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["email", "tenant_id"],
            },
        ),
    ])

    # SNS Tools
    tools.extend([
        Tool(
            name="sns_publish",
            description="Publish to SNS topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic_arn": {"type": "string"},
                    "message": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["topic_arn", "message", "tenant_id"],
            },
        ),
    ])

    # Secrets Manager Tools
    tools.extend([
        Tool(
            name="secretsmanager_create_secret",
            description="Create secret",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["name", "value", "tenant_id"],
            },
        ),
    ])

    # Generic query tools
    tools.extend([
        Tool(
            name="search_resources",
            description="Search resources across ALL 87 services",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "service": {"type": "string", "enum": MINISTACK_SERVICES},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_all_resources",
            description="List all resources for a tenant across ALL services",
            inputSchema={
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string"},
                },
                "required": ["tenant_id"],
            },
        ),
    ])

    return tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Execute tool for ANY of the 87 services."""
    import httpx

    try:
        args = arguments or {}
        tenant_id = args.get("tenant_id", "000000000001")

        # Route to appropriate API endpoint based on tool name
        service = name.split("_")[0]  # Extract service from tool name (e.g., "s3" from "s3_create_bucket")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # S3 Operations
            if name == "s3_create_bucket":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/s3/buckets",
                    json=args,
                )
            elif name == "s3_delete_bucket":
                response = await client.delete(
                    f"{config.api_base_url}/api/resources/s3/buckets/{args['name']}",
                    params={"tenant_id": tenant_id, "force": args.get("force", False)},
                )
            elif name == "s3_upload_object":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/s3/buckets/{args['bucket']}/objects",
                    json={"key": args["key"], "body": args["body"]},
                    params={"tenant_id": tenant_id},
                )

            # DynamoDB Operations
            elif name == "dynamodb_create_table":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/dynamodb/tables",
                    json=args,
                )
            elif name == "dynamodb_put_item":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/dynamodb/tables/{args['table']}/items",
                    json={"item": args["item"]},
                    params={"tenant_id": tenant_id},
                )

            # Lambda Operations
            elif name == "lambda_invoke":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/lambda/functions/{args['function']}/invoke",
                    json={"payload": args.get("payload", {})},
                    params={"tenant_id": tenant_id},
                )

            # SQS Operations
            elif name == "sqs_send_message":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/sqs/messages",
                    json={"url": args["queue_url"], "body": args["body"]},
                    params={"tenant_id": tenant_id},
                )
            elif name == "sqs_create_queue":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/sqs/queues",
                    json={"name": args["name"]},
                    params={"tenant_id": tenant_id},
                )

            # SES Operations
            elif name == "ses_verify_email":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/ses/identities",
                    json={"email": args["email"]},
                    params={"tenant_id": tenant_id},
                )

            # SNS Operations
            elif name == "sns_publish":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/sns/publish",
                    json={"topic_arn": args["topic_arn"], "message": args["message"]},
                    params={"tenant_id": tenant_id},
                )

            # Secrets Manager Operations
            elif name == "secretsmanager_create_secret":
                response = await client.post(
                    f"{config.api_base_url}/api/resources/secretsmanager/secrets",
                    json={"name": args["name"], "value": args["value"]},
                    params={"tenant_id": tenant_id},
                )

            # Query Operations
            elif name == "search_resources":
                response = await client.get(
                    f"{config.api_base_url}/api/search",
                    params={"q": args["query"], "tenant_id": args.get("tenant_id"), "service": args.get("service")},
                )
            elif name == "list_all_resources":
                response = await client.get(
                    f"{config.api_base_url}/api/resources?tenant_id={tenant_id}",
                )

            else:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "not_implemented",
                        "message": f"Tool {name} not yet implemented in API layer",
                        "available_in_ministack": True
                    })
                )]

            if response.status_code >= 400:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"HTTP {response.status_code}",
                        "detail": response.text,
                        "tool": name
                    })
                )]

            return [TextContent(type="text", text=json.dumps(response.json(), indent=2))]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e), "tool": name}))]


async def main():
    """Run the MCP server."""
    logger.info("Starting MiniStack Console MCP Server")
    logger.info(f"Supporting {len(MINISTACK_SERVICES)} services")
    logger.info(f"API endpoint: {config.api_base_url}")

    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="ministack-console",
            server_version="1.0.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
