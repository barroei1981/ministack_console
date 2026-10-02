# MSCL-7: Server-Sent Events System - Implementation Plan

## Alignment

- **Epic**: Epic 1 - Control-Plane Foundation
- **PRD requirement**: Real-time updates for Web UI - developers need immediate feedback when resources change in MiniStack without manual refresh
- **Architecture constraint**: Control-Plane Core layer (from ADR 2026-10-01) - must maintain real-time resource state visibility for both UI and eventual MCP interface
- **ADRs in scope**: 
  - ADR 2026-10-01 (Control-Plane Architecture) - establishes Web UI as primary human interface requiring real-time updates
  - ADR 2026-10-01 (Definition of Done End-to-End) - requires end-to-end verification that SSE events fire when resources actually change
- **Reuse decision**: 
  - Extending existing `sync.py:_sync_created/updated/deleted` functions (lines 61-128) to emit events after successful FalkorDB writes - same control flow, adding event publication step
  - Extending existing `manager.py:_sync_resource_dependencies` (lines 111-251) to emit DEPENDENCY_ADDED/REMOVED events after relationship operations
  - New event bus module needed - no existing pub/sub mechanism in codebase
- **Cross-layer contract**: SSE endpoint `GET /api/sse?tenant_id={tenant_id}` → event bus subscription → poller/sync layer publishes events. Web UI will use EventSource API to consume SSE stream.
- **Confirmed consistent**: YES - SSE for server-to-client push aligns with Control-Plane architecture's real-time visibility requirement, no conflicts with existing patterns

## Implementation Tasks

### 1. Event Bus Core (`control_plane/events/`)
- [ ] Create `control_plane/events/__init__.py` - export EventBus singleton
- [ ] Create `control_plane/events/models.py` - Event dataclass, EventType enum
- [ ] Create `control_plane/events/bus.py` - EventBus class with subscribe/unsubscribe/publish

### 2. Integration Points
- [ ] `control_plane/inventory/sync.py` - Add event emission after successful FalkorDB writes (lines 83, 109, 126)
- [ ] `control_plane/dependencies/manager.py` - Add event emission after dependency creation/deletion (lines 206, 235)

### 3. SSE Endpoint (`api/routes/sse.py`)
- [ ] Create SSE endpoint with tenant_id validation
- [ ] Implement event streaming with proper SSE format
- [ ] Handle disconnect/cleanup gracefully
- [ ] Register router in `api/main.py`

### 4. Testing
- [ ] Unit tests for EventBus (subscribe/publish/tenant isolation)
- [ ] Integration test: resource change → SSE event received
- [ ] End-to-end test: create S3 bucket via MiniStack → SSE client receives RESOURCE_CREATED within 35s

## Event Types

- **RESOURCE_CREATED**: New resource discovered in MiniStack
- **RESOURCE_UPDATED**: Resource state changed
- **RESOURCE_DELETED**: Resource removed from MiniStack
- **DEPENDENCY_ADDED**: New dependency relationship detected
- **DEPENDENCY_REMOVED**: Dependency no longer exists
- **TAGS_UPDATED**: Resource tags modified (deferred - tagging system doesn't emit events yet)

## Non-Functional Requirements

- **Latency**: Events arrive within 35 seconds (30s poll interval + 5s processing)
- **Concurrency**: Support 10 concurrent SSE connections per tenant
- **Tenant Isolation**: Events filtered by tenant_id, no cross-tenant leakage
- **Reconnection**: EventSource handles reconnect automatically, no server-side event replay (stateless)

## Integration Points Detail

### sync.py Integration
```python
# After line 83 in _sync_created:
await event_bus.publish("RESOURCE_CREATED", resource.to_dict())

# After line 109 in _sync_updated:
await event_bus.publish("RESOURCE_UPDATED", resource.to_dict())

# After line 126 in _sync_deleted:
await event_bus.publish("RESOURCE_DELETED", {"id": resource_id, "tenant_id": tenant_id})
```

### manager.py Integration
```python
# After line 206 in _sync_resource_dependencies (dependency created):
await event_bus.publish("DEPENDENCY_ADDED", {
    "source_id": dep.source_id,
    "target_id": dep.target_id,
    "type": dep.type.value,
    "metadata": dep.metadata,
    "tenant_id": tenant_id
})

# After line 235 (dependency deleted):
await event_bus.publish("DEPENDENCY_REMOVED", {
    "source_id": dep.source_id,
    "target_id": dep.target_id,
    "type": dep.type.value,
    "tenant_id": tenant_id
})
```

## Observability

Per `observability.md`:
- **OPERATIONAL logs**: Connection/disconnection events (not per-event - too noisy)
- **Structured format**: Include trace_id, tenant_id, connection count
- **No secrets**: Event payloads must not contain credentials or sensitive data
