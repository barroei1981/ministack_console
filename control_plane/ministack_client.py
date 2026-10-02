"""
MiniStack API client using boto3.

Provides async wrappers for AWS service APIs with retry logic and health checks.
"""

import asyncio
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC

try:
    import aioboto3
except ImportError:
    aioboto3 = None

logger = logging.getLogger(__name__)

# Configuration
MINISTACK_ENDPOINT = os.getenv("MINISTACK_ENDPOINT", "http://localhost:4566")
MINISTACK_ACCESS_KEY = os.getenv("MINISTACK_ACCESS_KEY", "000000000000")
MINISTACK_SECRET_KEY = os.getenv("MINISTACK_SECRET_KEY", "test")
MINISTACK_REGION = os.getenv("MINISTACK_REGION", "us-east-1")
MAX_RETRIES = int(os.getenv("MINISTACK_MAX_RETRIES", "2"))
RETRY_BASE_DELAY = float(os.getenv("MINISTACK_RETRY_DELAY", "1.0"))


class MiniStackClient:
    """
    Async boto3 client wrapper for MiniStack API.

    Implements retry logic per AD-12: 2 retries with exponential backoff (1s, 2s).
    """

    def __init__(
        self,
        endpoint_url: str = MINISTACK_ENDPOINT,
        access_key: str = MINISTACK_ACCESS_KEY,
        secret_key: str = MINISTACK_SECRET_KEY,
        region: str = MINISTACK_REGION,
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.session = None

        if aioboto3 is None:
            raise ImportError(
                "aioboto3 package not installed. Install with: pip install aioboto3"
            )

    def _get_session(self):
        """Get or create aioboto3 session."""
        if self.session is None:
            self.session = aioboto3.Session(
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )
        return self.session

    async def _retry_with_backoff(self, func, service_name: str):
        """
        Execute async function with exponential backoff retry.

        Retries up to MAX_RETRIES times with delays: 1s, 2s.

        Args:
            func: Async callable to execute
            service_name: Service name for logging

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                return await func()

            except Exception as e:
                last_exception = e

                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"{service_name} API call failed (attempt {attempt + 1}/{MAX_RETRIES + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"{service_name} API call failed after {MAX_RETRIES + 1} attempts: {e}"
                    )

        raise last_exception

    async def health_check(self) -> Dict[str, Any]:
        """
        Check MiniStack health via internal API.

        Returns:
            Dict with health status:
            {
                "healthy": bool,
                "instance_id": str,
                "error": Optional[str]
            }
        """
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                url = f"{self.endpoint_url}/_ministack/health"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "healthy": True,
                            "instance_id": data.get("instance_id", "unknown"),
                            "error": None,
                        }
                    else:
                        return {
                            "healthy": False,
                            "instance_id": None,
                            "error": f"HTTP {response.status}",
                        }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"healthy": False, "instance_id": None, "error": str(e)}

    async def get_s3_buckets(self) -> List[Dict[str, Any]]:
        """
        List all S3 buckets.

        Returns:
            List of bucket resources:
            [
                {
                    "id": "arn:aws:s3:::bucket-name",
                    "type": "s3:bucket",
                    "name": "bucket-name",
                    "tenant_id": "000000000000",
                    "arn": "arn:aws:s3:::bucket-name",
                    "state": {
                        "creation_date": "2026-10-02T00:00:00Z",
                        "location": "us-east-1"
                    },
                    "created_at": "2026-10-02T00:00:00Z",
                    "updated_at": "2026-10-02T00:00:00Z"
                }
            ]

        Raises:
            Exception: If API call fails after retries
        """

        async def _list_buckets():
            session = self._get_session()
            async with session.client("s3", endpoint_url=self.endpoint_url) as s3:
                response = await s3.list_buckets()

                resources = []
                for bucket in response.get("Buckets", []):
                    bucket_name = bucket["Name"]
                    creation_date = bucket["CreationDate"].isoformat()

                    # Get bucket location
                    try:
                        location_response = await s3.get_bucket_location(
                            Bucket=bucket_name
                        )
                        location = location_response.get("LocationConstraint") or "us-east-1"
                    except Exception as e:
                        logger.debug(
                            f"Could not get location for bucket {bucket_name}: {e}"
                        )
                        location = "us-east-1"

                    arn = f"arn:aws:s3:::{bucket_name}"

                    resources.append(
                        {
                            "id": arn,
                            "type": "s3:bucket",
                            "name": bucket_name,
                            "tenant_id": self.access_key,
                            "arn": arn,
                            "state": {
                                "creation_date": creation_date,
                                "location": location,
                            },
                            "created_at": creation_date,
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
                    )

                return resources

        return await self._retry_with_backoff(_list_buckets, "S3")

    async def get_lambda_functions(self) -> List[Dict[str, Any]]:
        """
        List all Lambda functions.

        Returns:
            List of function resources:
            [
                {
                    "id": "arn:aws:lambda:us-east-1:000000000000:function:func-name",
                    "type": "lambda:function",
                    "name": "func-name",
                    "tenant_id": "000000000000",
                    "arn": "arn:aws:lambda:us-east-1:000000000000:function:func-name",
                    "state": {
                        "runtime": "python3.11",
                        "handler": "index.handler",
                        "memory_size": 128,
                        "timeout": 3
                    },
                    "created_at": "2026-10-02T00:00:00Z",
                    "updated_at": "2026-10-02T00:00:00Z"
                }
            ]

        Raises:
            Exception: If API call fails after retries
        """

        async def _list_functions():
            session = self._get_session()
            async with session.client(
                "lambda", endpoint_url=self.endpoint_url
            ) as lambda_client:
                response = await lambda_client.list_functions()

                resources = []
                for func in response.get("Functions", []):
                    func_arn = func["FunctionArn"]
                    func_name = func["FunctionName"]
                    last_modified = func.get("LastModified", datetime.now(UTC).isoformat())

                    resources.append(
                        {
                            "id": func_arn,
                            "type": "lambda:function",
                            "name": func_name,
                            "tenant_id": self.access_key,
                            "arn": func_arn,
                            "state": {
                                "runtime": func.get("Runtime", "unknown"),
                                "handler": func.get("Handler", "unknown"),
                                "memory_size": func.get("MemorySize", 128),
                                "timeout": func.get("Timeout", 3),
                                "last_modified": last_modified,
                            },
                            "created_at": last_modified,
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
                    )

                return resources

        return await self._retry_with_backoff(_list_functions, "Lambda")

    async def get_dynamodb_tables(self) -> List[Dict[str, Any]]:
        """
        List all DynamoDB tables.

        Returns:
            List of table resources:
            [
                {
                    "id": "arn:aws:dynamodb:us-east-1:000000000000:table/table-name",
                    "type": "dynamodb:table",
                    "name": "table-name",
                    "tenant_id": "000000000000",
                    "arn": "arn:aws:dynamodb:us-east-1:000000000000:table/table-name",
                    "state": {
                        "status": "ACTIVE",
                        "item_count": 0,
                        "size_bytes": 0
                    },
                    "created_at": "2026-10-02T00:00:00Z",
                    "updated_at": "2026-10-02T00:00:00Z"
                }
            ]

        Raises:
            Exception: If API call fails after retries
        """

        async def _list_tables():
            session = self._get_session()
            async with session.client(
                "dynamodb", endpoint_url=self.endpoint_url
            ) as dynamodb:
                response = await dynamodb.list_tables()

                resources = []
                for table_name in response.get("TableNames", []):
                    # Get table details
                    try:
                        table_response = await dynamodb.describe_table(
                            TableName=table_name
                        )
                        table = table_response["Table"]

                        table_arn = table["TableArn"]
                        creation_date = table.get("CreationDateTime", datetime.now(UTC)).isoformat()

                        resources.append(
                            {
                                "id": table_arn,
                                "type": "dynamodb:table",
                                "name": table_name,
                                "tenant_id": self.access_key,
                                "arn": table_arn,
                                "state": {
                                    "status": table.get("TableStatus", "UNKNOWN"),
                                    "item_count": table.get("ItemCount", 0),
                                    "size_bytes": table.get("TableSizeBytes", 0),
                                    "creation_date": creation_date,
                                },
                                "created_at": creation_date,
                                "updated_at": datetime.now(UTC).isoformat(),
                            }
                        )

                    except Exception as e:
                        logger.warning(
                            f"Could not describe table {table_name}: {e}"
                        )
                        # Create minimal resource entry
                        arn = f"arn:aws:dynamodb:{self.region}:{self.access_key}:table/{table_name}"
                        now = datetime.now(UTC).isoformat()
                        resources.append(
                            {
                                "id": arn,
                                "type": "dynamodb:table",
                                "name": table_name,
                                "tenant_id": self.access_key,
                                "arn": arn,
                                "state": {"status": "UNKNOWN"},
                                "created_at": now,
                                "updated_at": now,
                            }
                        )

                return resources

        return await self._retry_with_backoff(_list_tables, "DynamoDB")

    async def list_event_source_mappings(
        self, function_name: str
    ) -> List[Dict[str, Any]]:
        """
        List event source mappings for a Lambda function.

        Args:
            function_name: Lambda function name

        Returns:
            List of event source mappings:
            [
                {
                    "UUID": "mapping-uuid",
                    "EventSourceArn": "arn:aws:sqs:...",
                    "State": "Enabled",
                    "FunctionArn": "arn:aws:lambda:...",
                }
            ]

        Raises:
            Exception: If API call fails after retries
        """

        async def _list_mappings():
            session = self._get_session()
            async with session.client(
                "lambda", endpoint_url=self.endpoint_url
            ) as lambda_client:
                response = await lambda_client.list_event_source_mappings(
                    FunctionName=function_name
                )
                return response.get("EventSourceMappings", [])

        return await self._retry_with_backoff(_list_mappings, "Lambda")

    async def get_bucket_policy(self, bucket_name: str) -> Optional[str]:
        """
        Get S3 bucket policy as JSON string.

        Args:
            bucket_name: S3 bucket name

        Returns:
            Policy JSON string or None if no policy exists

        Raises:
            Exception: If API call fails after retries (except NoSuchBucketPolicy)
        """

        async def _get_policy():
            session = self._get_session()
            async with session.client(
                "s3", endpoint_url=self.endpoint_url
            ) as s3_client:
                try:
                    response = await s3_client.get_bucket_policy(Bucket=bucket_name)
                    return response.get("Policy")
                except Exception as e:
                    # NoSuchBucketPolicy is expected for buckets without policies
                    if "NoSuchBucketPolicy" in str(e):
                        return None
                    raise

        return await self._retry_with_backoff(_get_policy, "S3")

    async def get_lambda_function_config(self, function_name: str) -> Dict[str, Any]:
        """
        Get full Lambda function configuration including environment variables.

        Args:
            function_name: Lambda function name

        Returns:
            Function configuration dict with Environment.Variables

        Raises:
            Exception: If API call fails after retries
        """

        async def _get_function():
            session = self._get_session()
            async with session.client(
                "lambda", endpoint_url=self.endpoint_url
            ) as lambda_client:
                response = await lambda_client.get_function(FunctionName=function_name)
                return response.get("Configuration", {})

        return await self._retry_with_backoff(_get_function, "Lambda")
