"""
SQS service layer for MiniStack operations.

Handles boto3 operations for SQS queues.
"""

import asyncio
import re
from typing import Any

import boto3
from botocore.exceptions import ClientError

from control_plane.graph.query import create_node, delete_node, query_nodes
from control_plane.observability import log_operational, trace_operation


class SQSService:
    """
    SQS service layer for tenant-scoped queue operations.

    Each instance is scoped to a single tenant.
    """

    def __init__(self, tenant_id: str):
        """
        Initialize SQS service for a tenant.

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
        Create boto3 SQS client for MiniStack.

        Returns:
            boto3 SQS client configured for MiniStack endpoint
        """
        import os
        endpoint = os.getenv("MINISTACK_ENDPOINT", "http://localhost:4566")

        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key="dummy",
            region_name="us-east-1",
        )
        return session.client("sqs", endpoint_url=endpoint)

    async def list_queues(self) -> list[dict[str, Any]]:
        """
        List all SQS queues for this tenant.

        Queries FalkorDB for queue metadata.

        Returns:
            List of queue dicts with metadata

        Raises:
            Exception: If query fails
        """
        with trace_operation("list_sqs_queues", tenant_id=self.tenant_id):
            try:
                queue_nodes = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"tenant_id": self.tenant_id, "type": "sqs:queue"},
                )

                log_operational(
                    "Listed SQS queues",
                    tenant_id=self.tenant_id,
                    count=len(queue_nodes),
                )

                return queue_nodes

            except Exception as e:
                log_operational(
                    "Failed to list SQS queues",
                    tenant_id=self.tenant_id,
                    error=str(e),
                )
                raise

    async def get_queue(self, queue_name: str) -> dict[str, Any] | None:
        """Get queue by name."""
        queues = await self.list_queues()
        for q in queues:
            if q.get("name") == queue_name:
                return q
        return None

    async def create_queue(self, queue_name: str) -> dict[str, Any]:
        """Create SQS queue."""
        with trace_operation("create_sqs_queue", tenant_id=self.tenant_id):
            try:
                result = await asyncio.to_thread(
                    self.client.create_queue,
                    QueueName=queue_name
                )
                queue_url = result["QueueUrl"]
                log_operational(f"Created SQS queue: {queue_name}", tenant_id=self.tenant_id)
                return {"queue_url": queue_url, "queue_name": queue_name}
            except Exception as e:
                log_operational(f"Failed to create queue: {e}", tenant_id=self.tenant_id)
                raise

    async def delete_queue(self, queue_url: str) -> dict[str, Any]:
        """Delete SQS queue."""
        with trace_operation("delete_sqs_queue", tenant_id=self.tenant_id):
            try:
                await asyncio.to_thread(
                    self.client.delete_queue,
                    QueueUrl=queue_url
                )
                log_operational(f"Deleted SQS queue: {queue_url}", tenant_id=self.tenant_id)
                return {"message": "Queue deleted"}
            except Exception as e:
                log_operational(f"Failed to delete queue: {e}", tenant_id=self.tenant_id)
                raise

    async def send_message(self, queue_name: str, message_body: str) -> dict[str, Any]:
        """Send message to queue."""
        with trace_operation("send_sqs_message", tenant_id=self.tenant_id):
            try:
                # Get queue URL
                response = await asyncio.to_thread(
                    self.client.get_queue_url,
                    QueueName=queue_name
                )
                queue_url = response["QueueUrl"]

                # Send message
                result = await asyncio.to_thread(
                    self.client.send_message,
                    QueueUrl=queue_url,
                    MessageBody=message_body
                )
                log_operational(f"Sent message to queue: {queue_name}", tenant_id=self.tenant_id)
                return {"message_id": result.get("MessageId")}
            except Exception as e:
                log_operational(f"Failed to send message: {e}", tenant_id=self.tenant_id)
                raise
