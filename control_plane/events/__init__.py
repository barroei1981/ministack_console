"""
Events module for real-time SSE notifications.

Exports EventBus singleton for use across control-plane.
"""

from .bus import EventBus
from .models import Event, EventType

# Singleton event bus instance
event_bus = EventBus()

__all__ = ["Event", "EventBus", "EventType", "event_bus"]
