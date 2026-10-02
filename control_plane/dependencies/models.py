"""
Data models for dependency detection.

Defines Dependency dataclass and DependencyType enum.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DependencyType(Enum):
    """Type of dependency relationship."""

    ENVIRONMENT_VARIABLE = "environment_variable"
    EVENT_SOURCE_MAPPING = "event_source_mapping"
    BUCKET_POLICY = "bucket_policy"


@dataclass
class Dependency:
    """
    Detected dependency between two resources.

    Maps to DEPENDS_ON relationship in FalkorDB.
    """

    source_id: str  # Source resource ID (e.g., Lambda ARN)
    target_id: str  # Target resource ID (e.g., S3 bucket ARN)
    type: DependencyType  # Dependency type
    metadata: dict[str, Any]  # Additional context (mapping UUID, env var name, etc.)

    def __eq__(self, other: object) -> bool:
        """
        Compare dependencies for equality.

        Two dependencies are equal if source, target, and type match.
        Metadata differences don't affect equality (for change detection).
        """
        if not isinstance(other, Dependency):
            return False

        return (
            self.source_id == other.source_id
            and self.target_id == other.target_id
            and self.type == other.type
        )

    def __hash__(self) -> int:
        """Hash by source, target, and type for set operations."""
        return hash((self.source_id, self.target_id, self.type.value))

    def to_properties(self) -> dict[str, Any]:
        """Convert to FalkorDB relationship properties."""
        return {
            "type": self.type.value,
            "metadata": self.metadata,
        }
