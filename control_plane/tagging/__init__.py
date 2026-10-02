"""
Dual tagging system for MiniStack resources.

Provides two independent tagging systems:
1. Control-plane tags: Stored in FalkorDB only, apply to ALL resources
2. Native tags: Stored in FalkorDB AND written to MiniStack via boto3 (taggable services only)

Namespace isolation prevents collision between control-plane and native tags.
"""

from control_plane.tagging.control_plane import (
    add_control_plane_tag,
    get_control_plane_tags,
    query_resources_by_tag,
    remove_control_plane_tag,
)
from control_plane.tagging.models import (
    AWS_RESERVED_PREFIXES,
    MAX_TAG_KEY_LENGTH,
    MAX_TAG_VALUE_LENGTH,
    TAGGABLE_SERVICES,
    TagNamespace,
)
from control_plane.tagging.native import (
    add_native_tag,
    get_native_tags,
    remove_native_tag,
    sync_native_tags_from_ministack,
    validate_aws_tag,
)

__all__ = [
    # Constants
    "TAGGABLE_SERVICES",
    "MAX_TAG_KEY_LENGTH",
    "MAX_TAG_VALUE_LENGTH",
    "AWS_RESERVED_PREFIXES",
    "TagNamespace",
    # Control-plane tagging
    "add_control_plane_tag",
    "remove_control_plane_tag",
    "get_control_plane_tags",
    "query_resources_by_tag",
    # Native tagging
    "validate_aws_tag",
    "add_native_tag",
    "remove_native_tag",
    "get_native_tags",
    "sync_native_tags_from_ministack",
]
