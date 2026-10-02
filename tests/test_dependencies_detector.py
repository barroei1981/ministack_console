"""
Unit tests for dependency detector.

Tests ARN parsing and dependency detection logic.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from control_plane.dependencies.detector import (
    extract_s3_bucket_from_arn,
    extract_sqs_queue_from_arn,
    extract_sns_topic_from_arn,
    extract_iam_role_from_arn,
    detect_lambda_s3_dependencies,
    detect_lambda_event_sources,
    detect_s3_iam_dependencies,
)
from control_plane.dependencies.models import DependencyType


class TestARNParsing:
    """Test ARN extraction functions."""

    def test_extract_s3_bucket_valid_arn(self):
        """Test extracting bucket name from valid S3 ARN."""
        arn = "arn:aws:s3:::my-bucket"
        assert extract_s3_bucket_from_arn(arn) == "my-bucket"

    def test_extract_s3_bucket_with_key(self):
        """Test extracting bucket name from S3 ARN with object key."""
        arn = "arn:aws:s3:::my-bucket/path/to/object"
        assert extract_s3_bucket_from_arn(arn) == "my-bucket"

    def test_extract_s3_bucket_invalid_arn(self):
        """Test extracting bucket from invalid ARN returns None."""
        assert extract_s3_bucket_from_arn("arn:aws:sqs:::queue") is None
        assert extract_s3_bucket_from_arn("not-an-arn") is None
        assert extract_s3_bucket_from_arn("") is None

    def test_extract_sqs_queue_valid_arn(self):
        """Test extracting queue name from valid SQS ARN."""
        arn = "arn:aws:sqs:us-east-1:000000000000:my-queue"
        assert extract_sqs_queue_from_arn(arn) == "my-queue"

    def test_extract_sqs_queue_invalid_arn(self):
        """Test extracting queue from invalid ARN returns None."""
        assert extract_sqs_queue_from_arn("arn:aws:s3:::bucket") is None
        assert extract_sqs_queue_from_arn("not-an-arn") is None

    def test_extract_sns_topic_valid_arn(self):
        """Test extracting topic name from valid SNS ARN."""
        arn = "arn:aws:sns:us-east-1:000000000000:my-topic"
        assert extract_sns_topic_from_arn(arn) == "my-topic"

    def test_extract_sns_topic_invalid_arn(self):
        """Test extracting topic from invalid ARN returns None."""
        assert extract_sns_topic_from_arn("arn:aws:s3:::bucket") is None

    def test_extract_iam_role_valid_arn(self):
        """Test extracting role name from valid IAM ARN."""
        arn = "arn:aws:iam::123456789012:role/MyRole"
        assert extract_iam_role_from_arn(arn) == "MyRole"

    def test_extract_iam_role_with_path(self):
        """Test extracting role name from IAM ARN with path."""
        arn = "arn:aws:iam::123456789012:role/path/to/MyRole"
        assert extract_iam_role_from_arn(arn) == "MyRole"

    def test_extract_iam_role_invalid_arn(self):
        """Test extracting role from invalid ARN returns None."""
        assert extract_iam_role_from_arn("arn:aws:s3:::bucket") is None
        assert extract_iam_role_from_arn("arn:aws:iam::123:user/User") is None


@pytest.mark.asyncio
class TestLambdaS3Dependencies:
    """Test Lambda→S3 dependency detection."""

    async def test_detect_s3_dependency_from_env_var(self):
        """Test detecting S3 dependency from environment variable."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.get_lambda_function_config = AsyncMock(
            return_value={
                "Environment": {
                    "Variables": {
                        "BUCKET_NAME": "arn:aws:s3:::my-bucket",
                        "OTHER_VAR": "value",
                    }
                }
            }
        )

        deps = await detect_lambda_s3_dependencies(lambda_resource, mock_client)

        assert len(deps) == 1
        assert deps[0].source_id == lambda_resource["id"]
        assert deps[0].target_id == "arn:aws:s3:::my-bucket"
        assert deps[0].type == DependencyType.ENVIRONMENT_VARIABLE
        assert deps[0].metadata["env_var_name"] == "BUCKET_NAME"
        assert deps[0].metadata["bucket_name"] == "my-bucket"

    async def test_detect_multiple_s3_dependencies(self):
        """Test detecting multiple S3 dependencies from different env vars."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.get_lambda_function_config = AsyncMock(
            return_value={
                "Environment": {
                    "Variables": {
                        "INPUT_BUCKET": "arn:aws:s3:::input-bucket",
                        "OUTPUT_BUCKET": "arn:aws:s3:::output-bucket",
                        "ARCHIVE_BUCKET": "arn:aws:s3:::archive-bucket",
                    }
                }
            }
        )

        deps = await detect_lambda_s3_dependencies(lambda_resource, mock_client)

        assert len(deps) == 3
        bucket_names = {dep.metadata["bucket_name"] for dep in deps}
        assert bucket_names == {"input-bucket", "output-bucket", "archive-bucket"}

    async def test_detect_no_s3_dependencies(self):
        """Test detecting no dependencies when no S3 ARNs in env vars."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.get_lambda_function_config = AsyncMock(
            return_value={
                "Environment": {
                    "Variables": {
                        "API_KEY": "secret",
                        "DB_HOST": "localhost",
                    }
                }
            }
        )

        deps = await detect_lambda_s3_dependencies(lambda_resource, mock_client)

        assert len(deps) == 0

    async def test_detect_s3_dependencies_no_env_vars(self):
        """Test detecting no dependencies when Lambda has no env vars."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.get_lambda_function_config = AsyncMock(
            return_value={"Environment": {}}
        )

        deps = await detect_lambda_s3_dependencies(lambda_resource, mock_client)

        assert len(deps) == 0

    async def test_detect_s3_dependencies_api_failure(self):
        """Test graceful handling of API failure."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.get_lambda_function_config = AsyncMock(
            side_effect=Exception("API error")
        )

        deps = await detect_lambda_s3_dependencies(lambda_resource, mock_client)

        # Should return empty list on error, not raise
        assert len(deps) == 0


@pytest.mark.asyncio
class TestLambdaEventSources:
    """Test Lambda→SQS/SNS dependency detection from event sources."""

    async def test_detect_sqs_event_source(self):
        """Test detecting SQS event source mapping."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.list_event_source_mappings = AsyncMock(
            return_value=[
                {
                    "UUID": "mapping-123",
                    "EventSourceArn": "arn:aws:sqs:us-east-1:000000000000:my-queue",
                    "State": "Enabled",
                }
            ]
        )

        deps = await detect_lambda_event_sources(lambda_resource, mock_client)

        assert len(deps) == 1
        assert deps[0].source_id == lambda_resource["id"]
        assert deps[0].target_id == "arn:aws:sqs:us-east-1:000000000000:my-queue"
        assert deps[0].type == DependencyType.EVENT_SOURCE_MAPPING
        assert deps[0].metadata["mapping_uuid"] == "mapping-123"
        assert deps[0].metadata["state"] == "Enabled"

    async def test_detect_sns_event_source(self):
        """Test detecting SNS event source mapping."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.list_event_source_mappings = AsyncMock(
            return_value=[
                {
                    "UUID": "mapping-456",
                    "EventSourceArn": "arn:aws:sns:us-east-1:000000000000:my-topic",
                    "State": "Enabled",
                }
            ]
        )

        deps = await detect_lambda_event_sources(lambda_resource, mock_client)

        assert len(deps) == 1
        assert deps[0].target_id == "arn:aws:sns:us-east-1:000000000000:my-topic"

    async def test_detect_multiple_event_sources(self):
        """Test detecting multiple event sources."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.list_event_source_mappings = AsyncMock(
            return_value=[
                {
                    "UUID": "mapping-1",
                    "EventSourceArn": "arn:aws:sqs:us-east-1:000000000000:queue-1",
                    "State": "Enabled",
                },
                {
                    "UUID": "mapping-2",
                    "EventSourceArn": "arn:aws:sqs:us-east-1:000000000000:queue-2",
                    "State": "Enabled",
                },
            ]
        )

        deps = await detect_lambda_event_sources(lambda_resource, mock_client)

        assert len(deps) == 2

    async def test_detect_no_event_sources(self):
        """Test detecting no event sources when none exist."""
        lambda_resource = {
            "id": "arn:aws:lambda:us-east-1:000000000000:function:my-func",
            "name": "my-func",
            "type": "lambda:function",
        }

        mock_client = Mock()
        mock_client.list_event_source_mappings = AsyncMock(return_value=[])

        deps = await detect_lambda_event_sources(lambda_resource, mock_client)

        assert len(deps) == 0


@pytest.mark.asyncio
class TestS3IAMDependencies:
    """Test S3→IAM dependency detection from bucket policies."""

    async def test_detect_iam_dependency_from_policy(self):
        """Test detecting IAM dependency from bucket policy."""
        s3_resource = {
            "id": "arn:aws:s3:::my-bucket",
            "name": "my-bucket",
            "type": "s3:bucket",
        }

        policy = {
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": "arn:aws:iam::123456789012:role/MyRole"
                    },
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::my-bucket/*",
                }
            ]
        }

        mock_client = Mock()
        mock_client.get_bucket_policy = AsyncMock(
            return_value='{"Statement": [{"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::123456789012:role/MyRole"}, "Action": "s3:GetObject", "Resource": "arn:aws:s3:::my-bucket/*"}]}'
        )

        deps = await detect_s3_iam_dependencies(s3_resource, mock_client)

        assert len(deps) == 1
        assert deps[0].source_id == s3_resource["id"]
        assert deps[0].target_id == "arn:aws:iam::123456789012:role/MyRole"
        assert deps[0].type == DependencyType.BUCKET_POLICY
        assert deps[0].metadata["role_name"] == "MyRole"
        assert deps[0].metadata["effect"] == "Allow"

    async def test_detect_multiple_iam_dependencies(self):
        """Test detecting multiple IAM roles from policy."""
        s3_resource = {
            "id": "arn:aws:s3:::my-bucket",
            "name": "my-bucket",
            "type": "s3:bucket",
        }

        mock_client = Mock()
        mock_client.get_bucket_policy = AsyncMock(
            return_value='{"Statement": [{"Effect": "Allow", "Principal": {"AWS": ["arn:aws:iam::123456789012:role/Role1", "arn:aws:iam::123456789012:role/Role2"]}, "Action": "s3:GetObject", "Resource": "arn:aws:s3:::my-bucket/*"}]}'
        )

        deps = await detect_s3_iam_dependencies(s3_resource, mock_client)

        assert len(deps) == 2
        role_names = {dep.metadata["role_name"] for dep in deps}
        assert role_names == {"Role1", "Role2"}

    async def test_detect_no_iam_dependencies_no_policy(self):
        """Test detecting no dependencies when bucket has no policy."""
        s3_resource = {
            "id": "arn:aws:s3:::my-bucket",
            "name": "my-bucket",
            "type": "s3:bucket",
        }

        mock_client = Mock()
        mock_client.get_bucket_policy = AsyncMock(return_value=None)

        deps = await detect_s3_iam_dependencies(s3_resource, mock_client)

        assert len(deps) == 0

    async def test_detect_no_iam_dependencies_wildcard_principal(self):
        """Test skipping wildcard principals."""
        s3_resource = {
            "id": "arn:aws:s3:::my-bucket",
            "name": "my-bucket",
            "type": "s3:bucket",
        }

        mock_client = Mock()
        mock_client.get_bucket_policy = AsyncMock(
            return_value='{"Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::my-bucket/*"}]}'
        )

        deps = await detect_s3_iam_dependencies(s3_resource, mock_client)

        assert len(deps) == 0

    async def test_detect_iam_dependencies_malformed_policy(self):
        """Test graceful handling of malformed policy JSON."""
        s3_resource = {
            "id": "arn:aws:s3:::my-bucket",
            "name": "my-bucket",
            "type": "s3:bucket",
        }

        mock_client = Mock()
        mock_client.get_bucket_policy = AsyncMock(
            return_value="{malformed json"
        )

        deps = await detect_s3_iam_dependencies(s3_resource, mock_client)

        # Should return empty list on parse error, not raise
        assert len(deps) == 0
