"""
Data models for resource inventory system.

Defines core types: Resource, Change, ChangeType, Snapshot.
"""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Dict, List, Any, Optional


class ChangeType(Enum):
    """Type of resource change detected."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


@dataclass
class Resource:
    """
    AWS resource tracked by control-plane.

    Maps 1:1 to Resource node in FalkorDB.
    """

    id: str  # Unique resource identifier (e.g., ARN or resource ID)
    type: str  # Resource type (e.g., "s3:bucket", "lambda:function")
    name: str  # Resource name
    tenant_id: str  # MiniStack tenant ID (12-digit access key)
    arn: str  # AWS ARN format
    state: Dict[str, Any]  # Flexible JSON blob of resource-specific metadata
    created_at: str  # ISO 8601 timestamp
    updated_at: str  # ISO 8601 timestamp

    def __eq__(self, other: object) -> bool:
        """
        Compare resources for equality.

        Two resources are equal if all properties match (used for change detection).
        """
        if not isinstance(other, Resource):
            return False

        return (
            self.id == other.id
            and self.type == other.type
            and self.name == other.name
            and self.tenant_id == other.tenant_id
            and self.arn == other.arn
            and self.state == other.state
        )

    def __hash__(self) -> int:
        """Hash by ID for set operations."""
        return hash(self.id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for FalkorDB node properties."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "tenant_id": self.tenant_id,
            "arn": self.arn,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Change:
    """
    Detected change in resource state.

    Produced by detector, consumed by sync layer.
    """

    change_type: ChangeType
    resource: Optional[Resource] = None  # Present for CREATED/UPDATED
    resource_id: Optional[str] = None  # Present for DELETED

    def __post_init__(self):
        """Validate change invariants."""
        if self.change_type in (ChangeType.CREATED, ChangeType.UPDATED):
            if self.resource is None:
                raise ValueError(f"{self.change_type.value} change requires resource")
        elif self.change_type == ChangeType.DELETED:
            if self.resource_id is None:
                raise ValueError("DELETED change requires resource_id")


@dataclass
class Snapshot:
    """
    Point-in-time snapshot of all resources.

    Used for change detection between poll cycles.
    """

    resources: List[Resource]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    _resources_by_id: Dict[str, Resource] = field(init=False, repr=False)

    def __post_init__(self):
        """Build lookup index for fast access."""
        self._resources_by_id = {r.id: r for r in self.resources}

    def get(self, resource_id: str) -> Optional[Resource]:
        """Get resource by ID."""
        return self._resources_by_id.get(resource_id)

    def has(self, resource_id: str) -> bool:
        """Check if resource exists in snapshot."""
        return resource_id in self._resources_by_id

    def get_ids(self) -> set:
        """Get set of all resource IDs."""
        return set(self._resources_by_id.keys())
