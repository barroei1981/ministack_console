"""SNS service layer for MiniStack operations."""
import asyncio
import re
from typing import Any
import boto3
from botocore.exceptions import ClientError
from control_plane.graph.query import query_nodes
from control_plane.observability import log_operational, trace_operation

class SNSService:
    def __init__(self, tenant_id: str):
        if not tenant_id or not re.match(r"^\d{12}$", tenant_id):
            raise ValueError("Tenant ID must be exactly 12 digits")
        self.tenant_id = tenant_id
        self.client = self._create_client()

    def _create_client(self) -> Any:
        import os
        endpoint = os.getenv("MINISTACK_ENDPOINT", "http://localhost:4566")
        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key="dummy",
            region_name="us-east-1",
        )
        return session.client("sns", endpoint_url=endpoint)

    async def list_topics(self) -> list[dict[str, Any]]:
        with trace_operation("list_sns_topics", tenant_id=self.tenant_id):
            try:
                topic_nodes = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"tenant_id": self.tenant_id, "type": "sns:topic"},
                )
                log_operational("Listed SNS topics", tenant_id=self.tenant_id, count=len(topic_nodes))
                return topic_nodes
            except Exception as e:
                log_operational("Failed to list SNS topics", tenant_id=self.tenant_id, error=str(e))
                raise
