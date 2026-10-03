"""
Cognito service layer for MiniStack operations.

Handles boto3 operations for Cognito User Pools.
"""

import asyncio
import re
from typing import Any

import boto3
from botocore.exceptions import ClientError

from control_plane.graph.query import create_node, delete_node, query_nodes
from control_plane.observability import log_operational, trace_operation


class CognitoService:
    """
    Cognito service layer for tenant-scoped user pool operations.

    Each instance is scoped to a single tenant.
    """

    def __init__(self, tenant_id: str):
        """
        Initialize Cognito service for a tenant.

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
        Create boto3 Cognito client for MiniStack.

        Returns:
            boto3 Cognito IDP client configured for MiniStack endpoint
        """
        import os
        endpoint = os.getenv("MINISTACK_ENDPOINT", "http://localhost:4566")

        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key="dummy",
            region_name="us-east-1",
        )
        return session.client("cognito-idp", endpoint_url=endpoint)

    async def list_user_pools(self) -> list[dict[str, Any]]:
        """
        List all Cognito user pools for this tenant.

        Queries FalkorDB for user pool metadata.

        Returns:
            List of user pool dicts with metadata

        Raises:
            Exception: If query fails
        """
        with trace_operation("list_cognito_user_pools", tenant_id=self.tenant_id):
            try:
                pool_nodes = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"tenant_id": self.tenant_id, "type": "cognito:userpool"},
                )

                log_operational(
                    "Listed Cognito user pools",
                    tenant_id=self.tenant_id,
                    count=len(pool_nodes),
                )

                return pool_nodes

            except Exception as e:
                log_operational(
                    "Failed to list Cognito user pools",
                    tenant_id=self.tenant_id,
                    error=str(e),
                )
                raise

    async def get_user_pool(self, pool_id: str) -> dict[str, Any] | None:
        """
        Get details of a specific user pool.

        Args:
            pool_id: User pool ID

        Returns:
            User pool details or None if not found
        """
        with trace_operation("get_cognito_user_pool", tenant_id=self.tenant_id, pool_id=pool_id):
            try:
                # Query live data from MiniStack
                pool_desc = await asyncio.to_thread(
                    self.client.describe_user_pool,
                    UserPoolId=pool_id
                )

                return pool_desc["UserPool"]

            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    return None
                raise
