"""
Dependency detection logic for MiniStack resources.

Detects dependencies by introspecting resource metadata:
- Lambda→S3: environment variables containing S3 ARNs
- Lambda→SQS/SNS: event source mappings
- S3→IAM: bucket policies with IAM role principals
"""

import json
import logging
import re

from ..ministack_client import MiniStackClient
from .models import Dependency, DependencyType

logger = logging.getLogger(__name__)

# Import boto exceptions conditionally (may not be available in test env)
try:
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO_EXCEPTIONS = (ClientError, BotoCoreError, KeyError, json.JSONDecodeError)
except ImportError:
    # Fallback for test environments where botocore isn't available
    BOTO_EXCEPTIONS = (KeyError, json.JSONDecodeError)


def extract_s3_bucket_from_arn(arn: str) -> str | None:
    """
    Extract S3 bucket name from ARN.

    Args:
        arn: S3 ARN like "arn:aws:s3:::bucket-name" or "arn:aws:s3:::bucket-name/key"

    Returns:
        Bucket name or None if not a valid S3 ARN
    """
    if not arn.startswith("arn:aws:s3:::"):
        return None
    parts = arn.split("arn:aws:s3:::")[-1].split("/")
    return parts[0] if parts else None


def extract_sqs_queue_from_arn(arn: str) -> str | None:
    """
    Extract SQS queue name from ARN.

    Args:
        arn: SQS ARN like "arn:aws:sqs:us-east-1:000000000000:queue-name"

    Returns:
        Queue name or None if not a valid SQS ARN
    """
    if ":sqs:" not in arn:
        return None
    return arn.split(":")[-1]


def extract_sns_topic_from_arn(arn: str) -> str | None:
    """
    Extract SNS topic name from ARN.

    Args:
        arn: SNS ARN like "arn:aws:sns:us-east-1:000000000000:topic-name"

    Returns:
        Topic name or None if not a valid SNS ARN
    """
    if ":sns:" not in arn:
        return None
    return arn.split(":")[-1]


def extract_iam_role_from_arn(arn: str) -> str | None:
    """
    Extract IAM role name from ARN.

    Args:
        arn: IAM ARN like "arn:aws:iam::123456789012:role/RoleName"

    Returns:
        Role name or None if not a valid IAM role ARN
    """
    if ":iam:" not in arn or ":role/" not in arn:
        return None
    return arn.split("/")[-1]


async def detect_lambda_s3_dependencies(
    lambda_resource: dict, client: MiniStackClient
) -> list[Dependency]:
    """
    Detect Lambda→S3 dependencies from environment variables.

    Searches for S3 ARNs in Lambda environment variables.

    Args:
        lambda_resource: Lambda resource dict with 'name' and 'id' (ARN)
        client: MiniStackClient instance

    Returns:
        List of Dependency objects (Lambda→S3)
    """
    dependencies = []
    lambda_arn = lambda_resource["id"]
    lambda_name = lambda_resource["name"]

    try:
        # Fetch full function config to get environment variables
        config = await client.get_lambda_function_config(lambda_name)
        env_vars = config.get("Environment", {}).get("Variables", {})

        if not env_vars:
            logger.debug(f"Lambda {lambda_name} has no environment variables")
            return dependencies

        # Search for S3 ARNs in environment variable values
        s3_arn_pattern = re.compile(r"arn:aws:s3:::[a-zA-Z0-9._-]+")

        for var_name, var_value in env_vars.items():
            if not isinstance(var_value, str):
                continue

            matches = s3_arn_pattern.findall(var_value)
            for s3_arn in matches:
                bucket_name = extract_s3_bucket_from_arn(s3_arn)
                if bucket_name:
                    logger.debug(
                        f"Found S3 dependency: {lambda_name} → {bucket_name} (env var: {var_name})"
                    )
                    dependencies.append(
                        Dependency(
                            source_id=lambda_arn,
                            target_id=s3_arn,
                            type=DependencyType.ENVIRONMENT_VARIABLE,
                            metadata={
                                "env_var_name": var_name,
                                "bucket_name": bucket_name,
                            },
                        )
                    )

    except BOTO_EXCEPTIONS as e:
        logger.warning(
            f"[OPERATIONAL] Failed to detect S3 dependencies for Lambda {lambda_name}: {e}"
        )
    except Exception as e:
        logger.error(
            f"[OPERATIONAL] Unexpected error detecting S3 dependencies for Lambda {lambda_name}: {e}",
            exc_info=True
        )

    return dependencies


async def detect_lambda_event_sources(
    lambda_resource: dict, client: MiniStackClient
) -> list[Dependency]:
    """
    Detect Lambda→SQS/SNS dependencies from event source mappings.

    Args:
        lambda_resource: Lambda resource dict with 'name' and 'id' (ARN)
        client: MiniStackClient instance

    Returns:
        List of Dependency objects (Lambda→SQS or Lambda→SNS)
    """
    dependencies = []
    lambda_arn = lambda_resource["id"]
    lambda_name = lambda_resource["name"]

    try:
        # Fetch event source mappings
        mappings = await client.list_event_source_mappings(lambda_name)

        for mapping in mappings:
            event_source_arn = mapping.get("EventSourceArn")
            mapping_uuid = mapping.get("UUID")
            state = mapping.get("State", "Unknown")

            if not event_source_arn:
                continue

            # Determine resource type from ARN
            if ":sqs:" in event_source_arn:
                queue_name = extract_sqs_queue_from_arn(event_source_arn)
                logger.debug(
                    f"Found SQS event source: {lambda_name} → {queue_name} (UUID: {mapping_uuid})"
                )
            elif ":sns:" in event_source_arn:
                topic_name = extract_sns_topic_from_arn(event_source_arn)
                logger.debug(
                    f"Found SNS event source: {lambda_name} → {topic_name} (UUID: {mapping_uuid})"
                )
            else:
                # Other event sources (DynamoDB Streams, Kinesis) - skip for now
                logger.debug(
                    f"Skipping non-SQS/SNS event source: {event_source_arn}"
                )
                continue

            dependencies.append(
                Dependency(
                    source_id=lambda_arn,
                    target_id=event_source_arn,
                    type=DependencyType.EVENT_SOURCE_MAPPING,
                    metadata={
                        "mapping_uuid": mapping_uuid,
                        "state": state,
                    },
                )
            )

    except BOTO_EXCEPTIONS as e:
        logger.warning(
            f"[OPERATIONAL] Failed to detect event source dependencies for Lambda {lambda_name}: {e}"
        )
    except Exception as e:
        logger.error(
            f"[OPERATIONAL] Unexpected error detecting event sources for Lambda {lambda_name}: {e}",
            exc_info=True
        )

    return dependencies


async def detect_s3_iam_dependencies(
    s3_resource: dict, client: MiniStackClient
) -> list[Dependency]:
    """
    Detect S3→IAM dependencies from bucket policies.

    Parses bucket policy to find IAM role ARNs in Principal.AWS.

    Args:
        s3_resource: S3 resource dict with 'name' and 'id' (ARN)
        client: MiniStackClient instance

    Returns:
        List of Dependency objects (S3→IAM)
    """
    dependencies = []
    bucket_name = s3_resource["name"]
    bucket_arn = s3_resource["id"]

    try:
        # Fetch bucket policy
        policy_json = await client.get_bucket_policy(bucket_name)

        if not policy_json:
            logger.debug(f"S3 bucket {bucket_name} has no policy")
            return dependencies

        # Parse policy JSON
        try:
            policy = json.loads(policy_json)
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse bucket policy for {bucket_name}: {e}"
            )
            return dependencies

        # Extract IAM principals from policy statements
        statements = policy.get("Statement", [])
        if not isinstance(statements, list):
            statements = [statements]

        for statement in statements:
            principal = statement.get("Principal", {})

            # Handle different principal formats
            aws_principals = []
            if isinstance(principal, str):
                if principal == "*":
                    continue  # Skip wildcard principals
                aws_principals.append(principal)
            elif isinstance(principal, dict):
                aws_field = principal.get("AWS", [])
                if isinstance(aws_field, str):
                    aws_principals.append(aws_field)
                elif isinstance(aws_field, list):
                    aws_principals.extend(aws_field)

            # Extract IAM role ARNs
            for arn in aws_principals:
                if not isinstance(arn, str):
                    continue

                role_name = extract_iam_role_from_arn(arn)
                if role_name:
                    logger.debug(
                        f"Found IAM dependency: {bucket_name} → {role_name}"
                    )
                    dependencies.append(
                        Dependency(
                            source_id=bucket_arn,
                            target_id=arn,
                            type=DependencyType.BUCKET_POLICY,
                            metadata={
                                "role_name": role_name,
                                "effect": statement.get("Effect", "Unknown"),
                            },
                        )
                    )

    except BOTO_EXCEPTIONS as e:
        logger.warning(
            f"[OPERATIONAL] Failed to detect IAM dependencies for S3 bucket {bucket_name}: {e}"
        )
    except Exception as e:
        logger.error(
            f"[OPERATIONAL] Unexpected error detecting IAM dependencies for S3 bucket {bucket_name}: {e}",
            exc_info=True
        )

    return dependencies
