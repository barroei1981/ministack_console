"""
DynamoDB service layer for MiniStack operations.

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


class DynamoDBService:
    """
    DynamoDB service layer for tenant-scoped table operations.

    Each instance is scoped to a single tenant. Uses boto3 to interact with
    MiniStack and maintains resource state in FalkorDB.
    """

    def __init__(self, tenant_id: str):
        """
        Initialize DynamoDB service for a tenant.

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
        Create boto3 DynamoDB client for MiniStack.

        Returns:
            boto3 DynamoDB client configured for MiniStack endpoint
        """
        import os
        endpoint = os.getenv("MINISTACK_ENDPOINT", "http://localhost:4566")

        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key="dummy",
            region_name="us-east-1",
        )
        return session.client("dynamodb", endpoint_url=endpoint)

    async def list_tables(self) -> list[dict[str, Any]]:
        """
        List all DynamoDB tables for this tenant.

        Queries FalkorDB for table metadata (source of truth for control-plane state).

        Returns:
            List of table dicts with metadata

        Raises:
            Exception: If query fails
        """
        with trace_operation("list_dynamodb_tables", tenant_id=self.tenant_id):
            try:
                table_nodes = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"tenant_id": self.tenant_id, "type": "dynamodb:table"},
                )

                log_operational(
                    "Listed DynamoDB tables",
                    tenant_id=self.tenant_id,
                    count=len(table_nodes),
                )

                return table_nodes

            except Exception as e:
                log_operational(
                    "Failed to list DynamoDB tables",
                    tenant_id=self.tenant_id,
                    error=str(e),
                )
                raise

    async def get_table(self, name: str) -> dict[str, Any] | None:
        """
        Get DynamoDB table details from FalkorDB.

        Args:
            name: Table name

        Returns:
            Table dict or None if not found
        """
        with trace_operation(
            "get_dynamodb_table", tenant_id=self.tenant_id, table_name=name
        ):
            try:
                tables = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={
                        "tenant_id": self.tenant_id,
                        "type": "dynamodb:table",
                        "name": name,
                    },
                )

                return tables[0] if tables else None

            except Exception as e:
                log_operational(
                    "Failed to get DynamoDB table",
                    tenant_id=self.tenant_id,
                    table_name=name,
                    error=str(e),
                )
                raise

    async def create_table(
        self,
        name: str,
        key_schema: list[dict[str, str]],
        attribute_definitions: list[dict[str, str]],
        billing_mode: str = "PAY_PER_REQUEST",
        provisioned_throughput: dict[str, int] | None = None,
        project: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create DynamoDB table with dual-write pattern.

        Pattern: MiniStack first → FalkorDB → SSE event (rollback FalkorDB on failure)

        Args:
            name: Table name
            key_schema: Key schema definition (HASH and optionally RANGE keys)
            attribute_definitions: Attribute definitions for keys
            billing_mode: Billing mode (PAY_PER_REQUEST or PROVISIONED)
            provisioned_throughput: Provisioned throughput (if billing_mode=PROVISIONED)
            project: Project tag
            tags: Additional control-plane tags

        Returns:
            Created table metadata

        Raises:
            ClientError: If MiniStack operation fails
            Exception: If FalkorDB operation fails
        """
        with trace_operation(
            "create_dynamodb_table", tenant_id=self.tenant_id, table_name=name
        ):
            arn = f"arn:aws:dynamodb:us-east-1:{self.tenant_id}:table/{name}"

            # Step 1: Create in MiniStack
            create_params: dict[str, Any] = {
                "TableName": name,
                "KeySchema": key_schema,
                "AttributeDefinitions": attribute_definitions,
                "BillingMode": billing_mode,
            }

            if billing_mode == "PROVISIONED":
                if not provisioned_throughput:
                    provisioned_throughput = {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
                create_params["ProvisionedThroughput"] = provisioned_throughput

            if tags:
                create_params["Tags"] = [
                    {"Key": k, "Value": v} for k, v in tags.items()
                ]

            try:
                response = await asyncio.to_thread(
                    self.client.create_table, **create_params
                )

                table_desc = response["TableDescription"]

                log_audit(
                    event_type="TABLE_CREATED",
                    actor={"id": self.tenant_id, "type": "TENANT"},
                    target={"type": "DYNAMODB_TABLE", "id": arn},
                    action="CREATE",
                    status="SUCCESS",
                    changes={"after": {"name": name, "arn": arn}},
                )

            except ClientError as e:
                log_operational(
                    "Failed to create DynamoDB table in MiniStack",
                    tenant_id=self.tenant_id,
                    table_name=name,
                    error=str(e),
                )
                raise

            # Step 2: Create in FalkorDB
            node_id = arn
            now = datetime.now(UTC).isoformat()

            control_tags = {"tenant": self.tenant_id}
            if project:
                control_tags["project"] = project
            if tags:
                control_tags.update(tags)

            node_data = {
                "id": node_id,
                "type": "dynamodb:table",
                "name": name,
                "tenant_id": self.tenant_id,
                "project": project,
                "arn": arn,
                "created_at": now,
                "tags": control_tags,
                "state": {
                    "key_schema": key_schema,
                    "attribute_definitions": attribute_definitions,
                    "billing_mode": billing_mode,
                    "table_status": table_desc.get("TableStatus", "ACTIVE"),
                    "item_count": 0,
                },
            }

            try:
                await asyncio.to_thread(
                    create_node, "Resource", node_id, node_data
                )

                log_operational(
                    "Created DynamoDB table in FalkorDB",
                    tenant_id=self.tenant_id,
                    table_name=name,
                    node_id=node_id,
                )

            except Exception as e:
                log_operational(
                    "Failed to create DynamoDB table in FalkorDB — rolling back MiniStack",
                    tenant_id=self.tenant_id,
                    table_name=name,
                    error=str(e),
                )

                # Rollback: delete from MiniStack
                try:
                    await asyncio.to_thread(self.client.delete_table, TableName=name)
                    log_operational(
                        "Rolled back DynamoDB table in MiniStack",
                        tenant_id=self.tenant_id,
                        table_name=name,
                    )
                except Exception as rollback_err:
                    log_operational(
                        "CRITICAL: Failed to rollback MiniStack table",
                        tenant_id=self.tenant_id,
                        table_name=name,
                        error=str(rollback_err),
                    )

                raise

            # Step 3: Emit SSE event
            try:
                event_bus.publish(
                    {
                        "type": "RESOURCE_CREATED",
                        "resource_type": "dynamodb:table",
                        "resource_id": node_id,
                        "tenant_id": self.tenant_id,
                        "data": node_data,
                    }
                )
            except Exception as e:
                log_operational(
                    "Failed to emit RESOURCE_CREATED event (non-blocking)",
                    resource_id=node_id,
                    error=str(e),
                )

            return node_data

    async def delete_table(self, name: str) -> dict[str, Any]:
        """
        Delete DynamoDB table with dual-delete pattern.

        Pattern: MiniStack first → FalkorDB → SSE event

        Args:
            name: Table name

        Returns:
            Deleted table metadata

        Raises:
            ClientError: If MiniStack operation fails
            Exception: If FalkorDB operation fails
        """
        with trace_operation(
            "delete_dynamodb_table", tenant_id=self.tenant_id, table_name=name
        ):
            arn = f"arn:aws:dynamodb:us-east-1:{self.tenant_id}:table/{name}"

            # Get table data before deletion (for audit log)
            table_data = await self.get_table(name)
            if not table_data:
                raise ValueError(f"Table {name} not found")

            # Step 1: Delete from MiniStack
            try:
                await asyncio.to_thread(self.client.delete_table, TableName=name)

                log_audit(
                    event_type="TABLE_DELETED",
                    actor={"id": self.tenant_id, "type": "TENANT"},
                    target={"type": "DYNAMODB_TABLE", "id": arn},
                    action="DELETE",
                    status="SUCCESS",
                    changes={"before": {"name": name, "arn": arn}},
                )

            except ClientError as e:
                log_operational(
                    "Failed to delete DynamoDB table from MiniStack",
                    tenant_id=self.tenant_id,
                    table_name=name,
                    error=str(e),
                )
                raise

            # Step 2: Delete from FalkorDB
            try:
                await asyncio.to_thread(delete_node, "Resource", arn)

                log_operational(
                    "Deleted DynamoDB table from FalkorDB",
                    tenant_id=self.tenant_id,
                    table_name=name,
                    node_id=arn,
                )

            except Exception as e:
                log_operational(
                    "Failed to delete DynamoDB table from FalkorDB (orphaned node)",
                    tenant_id=self.tenant_id,
                    table_name=name,
                    node_id=arn,
                    error=str(e),
                )
                raise

            # Step 3: Emit SSE event
            try:
                event_bus.publish(
                    {
                        "type": "RESOURCE_DELETED",
                        "resource_type": "dynamodb:table",
                        "resource_id": arn,
                        "tenant_id": self.tenant_id,
                    }
                )
            except Exception as e:
                log_operational(
                    "Failed to emit RESOURCE_DELETED event (non-blocking)",
                    resource_id=arn,
                    error=str(e),
                )

            return table_data

    async def scan_items(
        self,
        table_name: str,
        limit: int = 100,
        exclusive_start_key: dict[str, Any] | None = None,
        filter_expression: str | None = None,
        projection_expression: str | None = None,
    ) -> dict[str, Any]:
        """
        Scan DynamoDB table items.

        Args:
            table_name: Table name
            limit: Maximum items to return
            exclusive_start_key: Pagination token (from previous scan)
            filter_expression: Filter expression
            projection_expression: Projection expression

        Returns:
            Dict with 'items', 'count', 'last_evaluated_key'

        Raises:
            ClientError: If MiniStack operation fails
        """
        with trace_operation(
            "scan_dynamodb_items",
            tenant_id=self.tenant_id,
            table_name=table_name,
            limit=limit,
        ):
            scan_params: dict[str, Any] = {"TableName": table_name, "Limit": limit}

            if exclusive_start_key:
                scan_params["ExclusiveStartKey"] = exclusive_start_key
            if filter_expression:
                scan_params["FilterExpression"] = filter_expression
            if projection_expression:
                scan_params["ProjectionExpression"] = projection_expression

            try:
                response = await asyncio.to_thread(self.client.scan, **scan_params)

                items = response.get("Items", [])
                count = response.get("Count", 0)
                last_key = response.get("LastEvaluatedKey")

                log_operational(
                    "Scanned DynamoDB table items",
                    tenant_id=self.tenant_id,
                    table_name=table_name,
                    count=count,
                    has_more=bool(last_key),
                )

                return {
                    "items": items,
                    "count": count,
                    "last_evaluated_key": last_key,
                }

            except ClientError as e:
                log_operational(
                    "Failed to scan DynamoDB table",
                    tenant_id=self.tenant_id,
                    table_name=table_name,
                    error=str(e),
                )
                raise

    async def put_item(
        self, table_name: str, item: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Put item to DynamoDB table.

        Args:
            table_name: Table name
            item: Item data (in DynamoDB JSON format)

        Returns:
            Response metadata

        Raises:
            ClientError: If MiniStack operation fails
        """
        with trace_operation(
            "put_dynamodb_item",
            tenant_id=self.tenant_id,
            table_name=table_name,
        ):
            try:
                response = await asyncio.to_thread(
                    self.client.put_item, TableName=table_name, Item=item
                )

                log_audit(
                    event_type="ITEM_WRITTEN",
                    actor={"id": self.tenant_id, "type": "TENANT"},
                    target={"type": "DYNAMODB_ITEM", "id": f"{table_name}/{item}"},
                    action="UPDATE",
                    status="SUCCESS",
                    changes={"after": item},
                )

                # Emit SSE event for table update
                try:
                    arn = f"arn:aws:dynamodb:us-east-1:{self.tenant_id}:table/{table_name}"
                    event_bus.publish(
                        {
                            "type": "RESOURCE_UPDATED",
                            "resource_type": "dynamodb:table",
                            "resource_id": arn,
                            "tenant_id": self.tenant_id,
                        }
                    )
                except Exception as e:
                    log_operational(
                        "Failed to emit RESOURCE_UPDATED event (non-blocking)",
                        resource_id=arn,
                        error=str(e),
                    )

                return response

            except ClientError as e:
                log_operational(
                    "Failed to put item to DynamoDB table",
                    tenant_id=self.tenant_id,
                    table_name=table_name,
                    error=str(e),
                )
                raise

    async def delete_item(
        self, table_name: str, key: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Delete item from DynamoDB table.

        Args:
            table_name: Table name
            key: Primary key of item to delete

        Returns:
            Response metadata

        Raises:
            ClientError: If MiniStack operation fails
        """
        with trace_operation(
            "delete_dynamodb_item",
            tenant_id=self.tenant_id,
            table_name=table_name,
        ):
            try:
                response = await asyncio.to_thread(
                    self.client.delete_item, TableName=table_name, Key=key
                )

                log_audit(
                    event_type="ITEM_DELETED",
                    actor={"id": self.tenant_id, "type": "TENANT"},
                    target={"type": "DYNAMODB_ITEM", "id": f"{table_name}/{key}"},
                    action="DELETE",
                    status="SUCCESS",
                    changes={"before": key},
                )

                # Emit SSE event for table update
                try:
                    arn = f"arn:aws:dynamodb:us-east-1:{self.tenant_id}:table/{table_name}"
                    event_bus.publish(
                        {
                            "type": "RESOURCE_UPDATED",
                            "resource_type": "dynamodb:table",
                            "resource_id": arn,
                            "tenant_id": self.tenant_id,
                        }
                    )
                except Exception as e:
                    log_operational(
                        "Failed to emit RESOURCE_UPDATED event (non-blocking)",
                        resource_id=arn,
                        error=str(e),
                    )

                return response

            except ClientError as e:
                log_operational(
                    "Failed to delete item from DynamoDB table",
                    tenant_id=self.tenant_id,
                    table_name=table_name,
                    error=str(e),
                )
                raise
