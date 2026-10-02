"""
Tagging system constants and models.

Defines taggable service types, namespace enums, and AWS validation constraints.
"""

from enum import Enum

# Services that support native tagging via AWS APIs
TAGGABLE_SERVICES: list[str] = [
    "s3:bucket",
    "lambda:function",
    "dynamodb:table",
]

# AWS tag constraints (per AWS Tagging Best Practices)
MAX_TAG_KEY_LENGTH = 128
MAX_TAG_VALUE_LENGTH = 256

# Reserved AWS prefixes (block for native tags only)
AWS_RESERVED_PREFIXES: list[str] = ["aws:", "AWS:"]


class TagNamespace(str, Enum):
    """Tag namespace for isolation between control-plane and native tags."""

    CONTROL_PLANE = "control_plane"
    NATIVE = "native"
