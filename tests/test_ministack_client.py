"""
Unit tests for MiniStack client wrapper.

Tests:
- Health check
- Retry logic with exponential backoff
- S3 bucket fetching
- Lambda function fetching
- DynamoDB table fetching
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from control_plane.ministack_client import MiniStackClient


@pytest.fixture
def mock_client():
    """Create MiniStackClient with mocked session."""
    return MiniStackClient(
        endpoint_url="http://localhost:4566",
        access_key="123456789012",
        secret_key="test",
        region="us-east-1",
    )


@pytest.mark.asyncio
async def test_health_check_success(mock_client):
    """Test successful health check."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"instance_id": "test-123"})

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await mock_client.health_check()

    assert result["healthy"] is True
    assert result["instance_id"] == "test-123"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_health_check_failure(mock_client):
    """Test health check when MiniStack is unreachable."""
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        result = await mock_client.health_check()

    assert result["healthy"] is False
    assert result["instance_id"] is None
    assert "Connection refused" in result["error"]


@pytest.mark.asyncio
async def test_get_s3_buckets_success(mock_client):
    """Test fetching S3 buckets."""
    mock_s3_client = MagicMock()
    mock_s3_client.list_buckets = AsyncMock(
        return_value={
            "Buckets": [
                {"Name": "test-bucket-1", "CreationDate": datetime(2026, 10, 1)},
                {"Name": "test-bucket-2", "CreationDate": datetime(2026, 10, 2)},
            ]
        }
    )
    mock_s3_client.get_bucket_location = AsyncMock(
        return_value={"LocationConstraint": "us-east-1"}
    )
    mock_s3_client.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_s3_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_s3_client)
    mock_client.session = mock_session

    buckets = await mock_client.get_s3_buckets()

    assert len(buckets) == 2
    assert buckets[0]["name"] == "test-bucket-1"
    assert buckets[0]["type"] == "s3:bucket"
    assert buckets[0]["tenant_id"] == "123456789012"
    assert buckets[0]["arn"] == "arn:aws:s3:::test-bucket-1"


@pytest.mark.asyncio
async def test_get_lambda_functions_success(mock_client):
    """Test fetching Lambda functions."""
    mock_lambda_client = MagicMock()
    mock_lambda_client.list_functions = AsyncMock(
        return_value={
            "Functions": [
                {
                    "FunctionName": "test-function",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                    "Runtime": "python3.11",
                    "Handler": "index.handler",
                    "MemorySize": 128,
                    "Timeout": 3,
                    "LastModified": "2026-10-01T00:00:00Z",
                }
            ]
        }
    )
    mock_lambda_client.__aenter__ = AsyncMock(return_value=mock_lambda_client)
    mock_lambda_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_lambda_client)
    mock_client.session = mock_session

    functions = await mock_client.get_lambda_functions()

    assert len(functions) == 1
    assert functions[0]["name"] == "test-function"
    assert functions[0]["type"] == "lambda:function"
    assert functions[0]["tenant_id"] == "123456789012"
    assert functions[0]["state"]["runtime"] == "python3.11"


@pytest.mark.asyncio
async def test_get_dynamodb_tables_success(mock_client):
    """Test fetching DynamoDB tables."""
    mock_dynamodb_client = MagicMock()
    mock_dynamodb_client.list_tables = AsyncMock(
        return_value={"TableNames": ["test-table"]}
    )
    mock_dynamodb_client.describe_table = AsyncMock(
        return_value={
            "Table": {
                "TableName": "test-table",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
                "TableStatus": "ACTIVE",
                "CreationDateTime": datetime(2026, 10, 1),
                "ItemCount": 100,
                "TableSizeBytes": 1024,
            }
        }
    )
    mock_dynamodb_client.__aenter__ = AsyncMock(return_value=mock_dynamodb_client)
    mock_dynamodb_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_dynamodb_client)
    mock_client.session = mock_session

    tables = await mock_client.get_dynamodb_tables()

    assert len(tables) == 1
    assert tables[0]["name"] == "test-table"
    assert tables[0]["type"] == "dynamodb:table"
    assert tables[0]["tenant_id"] == "123456789012"
    assert tables[0]["state"]["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_retry_logic_success_on_second_attempt(mock_client):
    """Test retry logic succeeds on second attempt."""
    mock_s3_client = MagicMock()

    # First call fails, second succeeds
    mock_s3_client.list_buckets = AsyncMock(
        side_effect=[
            Exception("Temporary error"),
            {"Buckets": [{"Name": "test-bucket", "CreationDate": datetime(2026, 10, 1)}]},
        ]
    )
    mock_s3_client.get_bucket_location = AsyncMock(
        return_value={"LocationConstraint": "us-east-1"}
    )
    mock_s3_client.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_s3_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_s3_client)
    mock_client.session = mock_session

    # Should succeed after retry
    buckets = await mock_client.get_s3_buckets()

    assert len(buckets) == 1
    assert buckets[0]["name"] == "test-bucket"


@pytest.mark.asyncio
async def test_retry_logic_fails_after_max_retries(mock_client):
    """Test retry logic fails after max retries."""
    mock_s3_client = MagicMock()

    # All calls fail
    mock_s3_client.list_buckets = AsyncMock(side_effect=Exception("Persistent error"))
    mock_s3_client.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_s3_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_s3_client)
    mock_client.session = mock_session

    # Should fail after max retries
    with pytest.raises(Exception, match="Persistent error"):
        await mock_client.get_s3_buckets()
