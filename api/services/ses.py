"""
SES service layer for MiniStack operations.

Handles boto3 operations for SES (Simple Email Service).
"""

import asyncio
import re
from typing import Any

import boto3
from botocore.exceptions import ClientError

from control_plane.graph.query import create_node, delete_node, query_nodes
from control_plane.observability import log_operational, trace_operation


class SESService:
    """
    SES service layer for tenant-scoped email operations.

    Each instance is scoped to a single tenant.
    """

    def __init__(self, tenant_id: str):
        """
        Initialize SES service for a tenant.

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
        Create boto3 SES client for MiniStack.

        Returns:
            boto3 SES client configured for MiniStack endpoint
        """
        import os
        endpoint = os.getenv("MINISTACK_ENDPOINT", "http://localhost:4566")

        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key="dummy",
            region_name="us-east-1",
        )
        return session.client("ses", endpoint_url=endpoint)

    async def list_identities(self) -> list[dict[str, Any]]:
        """
        List all SES verified identities for this tenant.

        Queries FalkorDB for identity metadata.

        Returns:
            List of identity dicts with metadata

        Raises:
            Exception: If query fails
        """
        with trace_operation("list_ses_identities", tenant_id=self.tenant_id):
            try:
                identity_nodes = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"tenant_id": self.tenant_id, "type": "ses:identity"},
                )

                log_operational(
                    "Listed SES identities",
                    tenant_id=self.tenant_id,
                    count=len(identity_nodes),
                )

                return identity_nodes

            except Exception as e:
                log_operational(
                    "Failed to list SES identities",
                    tenant_id=self.tenant_id,
                    error=str(e),
                )
                raise

    async def get_identity_verification_attributes(self, identities: list[str]) -> dict[str, Any]:
        """
        Get verification status of email identities.

        Args:
            identities: List of email addresses or domains

        Returns:
            Verification attributes for each identity
        """
        with trace_operation("get_ses_verification_attributes", tenant_id=self.tenant_id):
            try:
                result = await asyncio.to_thread(
                    self.client.get_identity_verification_attributes,
                    Identities=identities
                )

                return result.get("VerificationAttributes", {})

            except ClientError as e:
                log_operational(
                    "Failed to get SES verification attributes",
                    tenant_id=self.tenant_id,
                    error=str(e),
                )
                raise

    async def verify_email_identity(self, email: str) -> dict[str, Any]:
        """
        Send verification email to an address.

        Args:
            email: Email address to verify

        Returns:
            Response metadata
        """
        with trace_operation("verify_ses_email", tenant_id=self.tenant_id, email=email):
            try:
                result = await asyncio.to_thread(
                    self.client.verify_email_identity,
                    EmailAddress=email
                )

                log_operational(
                    "Sent SES verification email",
                    tenant_id=self.tenant_id,
                    email=email,
                )

                return result

            except ClientError as e:
                log_operational(
                    "Failed to send SES verification email",
                    tenant_id=self.tenant_id,
                    email=email,
                    error=str(e),
                )
                raise
