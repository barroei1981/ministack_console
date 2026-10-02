"""
Observability utilities for structured logging and tracing.

Provides AUDIT logging helpers per observability.md requirements.
"""

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def log_audit(
    message: str,
    event_type: str,
    actor: dict[str, Any],
    target: dict[str, Any],
    action: str,
    status: str,
    changes: dict[str, Any] | None = None,
    **kwargs,
) -> None:
    """
    Log an audit event with structured format.

    Required for data modifications per observability.md:
    - WHO: actor (tenant_id, user_id if available)
    - WHAT: target (resource_id, action)
    - WHEN: timestamp (ISO 8601)
    - BEFORE/AFTER: changes (old state, new state)
    - STATUS: SUCCESS / FAILURE

    Args:
        message: Human-readable message
        event_type: Event type (e.g., TAG_ADDED, TAG_REMOVED)
        actor: Actor info dict with 'id' and 'type' keys
        target: Target info dict with 'type' and 'id' keys
        action: Action performed (CREATE, UPDATE, DELETE)
        status: Operation status (SUCCESS, FAILURE)
        changes: Optional before/after state dict
        **kwargs: Additional context fields

    Example:
        log_audit(
            "Resource tag added",
            event_type="TAG_ADDED",
            actor={"id": tenant_id, "type": "TENANT"},
            target={"type": "RESOURCE", "id": resource_id},
            action="CREATE",
            status="SUCCESS",
            changes={"before": {}, "after": {"project": "app"}}
        )
    """
    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "INFO",
        "type": "AUDIT",
        "message": message,
        "event_type": event_type,
        "actor": actor,
        "target": target,
        "action": action,
        "status": status,
    }

    if changes:
        audit_entry["changes"] = changes

    # Add any additional context
    audit_entry.update(kwargs)

    # Log as structured JSON-like entry
    logger.info(
        f"[AUDIT] {message}",
        extra=audit_entry,
    )


class TracingContext:
    """
    Minimal OpenTelemetry tracing context manager.

    In production, this should use actual OpenTelemetry SDK.
    For now, provides a no-op implementation that satisfies the interface.
    """

    def __init__(self, span_name: str, **attributes):
        self.span_name = span_name
        self.attributes = attributes

    def __enter__(self):
        logger.debug(f"[TRACE] Starting span: {self.span_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.debug(f"[TRACE] Span {self.span_name} failed: {exc_val}")
        else:
            logger.debug(f"[TRACE] Span {self.span_name} completed")
        return False


def log_operational(
    message: str,
    **context: Any,
) -> None:
    """
    Log an operational event with structured format.

    Used for normal operations, request/response flow, performance metrics.

    Args:
        message: Human-readable message
        **context: Additional context fields (duration_ms, status_code, etc.)

    Example:
        log_operational(
            "API request completed",
            method="GET",
            path="/api/tenants",
            status_code=200,
            duration_ms=45
        )
    """
    operational_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "INFO",
        "type": "OPERATIONAL",
        "message": message,
    }

    # Add context fields
    operational_entry.update(context)

    # Log as structured JSON-like entry
    logger.info(
        f"[OPERATIONAL] {message}",
        extra=operational_entry,
    )


def log_security(
    message: str,
    **context: Any,
) -> None:
    """
    Log a security event with structured format.

    Used for authentication, authorization, data access patterns, security policy violations.
    Per observability.md: SSE connections are data access patterns and require SECURITY logs.

    Args:
        message: Human-readable message
        **context: Additional context fields (user_id, tenant_id, ip_address, etc.)

    Example:
        log_security(
            "SSE connection established",
            tenant_id="123456789012",
            ip_address="192.168.1.100"
        )
    """
    security_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "INFO",
        "type": "SECURITY",
        "message": message,
    }

    # Add context fields
    security_entry.update(context)

    # Log as structured JSON-like entry
    logger.info(
        f"[SECURITY] {message}",
        extra=security_entry,
    )


def trace_operation(span_name: str, **attributes):
    """
    Decorator/context manager for tracing operations.

    Usage:
        with trace_operation("add_tag", resource_id=resource_id):
            # operation code
            pass

    In production, replace with actual OpenTelemetry tracing.
    """
    return TracingContext(span_name, **attributes)
