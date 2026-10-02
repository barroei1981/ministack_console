"""
Event models for Server-Sent Events system.

Defines event types and data structures for real-time updates.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class EventType(Enum):
    """Types of events emitted by the control-plane."""

    RESOURCE_CREATED = "RESOURCE_CREATED"
    RESOURCE_UPDATED = "RESOURCE_UPDATED"
    RESOURCE_DELETED = "RESOURCE_DELETED"
    DEPENDENCY_ADDED = "DEPENDENCY_ADDED"
    DEPENDENCY_REMOVED = "DEPENDENCY_REMOVED"
    TAGS_UPDATED = "TAGS_UPDATED"


@dataclass
class Event:
    """
    Event emitted by control-plane to SSE subscribers.

    Events are tenant-scoped and contain resource/dependency changes.
    """

    type: str  # EventType value
    resource: dict[str, Any]  # Resource data or dependency info
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    tenant_id: str | None = None  # For tenant isolation

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "type": self.type,
            "resource": self.resource,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
        }
