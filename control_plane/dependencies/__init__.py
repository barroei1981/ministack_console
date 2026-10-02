"""
Dependency detection and management for MiniStack resources.

Detects dependencies between resources (Lambda→S3, Lambda→SQS, S3→IAM)
and maintains DEPENDS_ON relationships in FalkorDB.
"""

from .detector import (
    detect_lambda_event_sources,
    detect_lambda_s3_dependencies,
    detect_s3_iam_dependencies,
)
from .manager import sync_all_dependencies
from .models import Dependency, DependencyType

__all__ = [
    "Dependency",
    "DependencyType",
    "detect_lambda_event_sources",
    "detect_lambda_s3_dependencies",
    "detect_s3_iam_dependencies",
    "sync_all_dependencies",
]
