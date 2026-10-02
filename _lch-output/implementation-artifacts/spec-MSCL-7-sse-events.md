---
title: 'MSCL-7: Server-Sent Events for Real-Time Updates'
type: 'feature'
created: '2026-10-02'
status: 'done'
review_loop_iteration: 1
baseline_commit: '77d79b17c5264a11135eeac7b66274956787d888'
context:
  - '_lch-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Developers using the Web UI must manually refresh to see resource changes. When a Lambda is created via CLI/SDK, when a dependency is detected, or when tags are updated, the UI shows stale data until the user clicks refresh. This breaks the real-time management experience expected from a control-plane.

**Approach:** Build a Server-Sent Events (SSE) system that streams resource changes from the control-plane to connected UI clients. Create an event bus that the poller publishes to after each change (RESOURCE_CREATED/UPDATED/DELETED, DEPENDENCY_ADDED/REMOVED, TAGS_UPDATED), expose an SSE endpoint via the REST API, and provide a React hook for UI components to subscribe. Events arrive within 5 seconds (30s poll interval + processing time), reconnect automatically on disconnect, and handle 10+ concurrent connections per tenant.

## Boundaries & Constraints

**Always:**
- Use Server-Sent Events (SSE) via native `EventSource` API, not WebSockets (unidirectional server→client only)
- Tenant isolation: filter events by tenant_id, never send cross-tenant events
- Emit events after successful FalkorDB writes in `sync_changes()` (control_plane/inventory/sync.py:42-48)
- Use asyncio.Queue for in-memory pub/sub (no external message broker like Redis Pub/Sub)
- SSE endpoint at `/api/sse?tenant_id={tenant_id}` using FastAPI `StreamingResponse`
- Event format: `data: {JSON}\n\n` (SSE protocol), payload includes `{type, resource, timestamp}`
- Built-in reconnect: rely on EventSource's automatic reconnection (exponential backoff)
- Follow observability.md: structured OPERATIONAL logs for connection/disconnection, no logs per event (too noisy)

**Ask First:**
- Event history/replay for reconnected clients (requires persistent queue - deferred to future story)
- Cross-tab synchronization (LocalStorage events - UI enhancement, not backend concern)
- Rate limiting per SSE connection (current NFRs assume 10 concurrent connections, no abuse scenario defined)

**Never:**
- Use WebSockets (bidirectional overhead not needed)
- Store events in FalkorDB or persistent queue (in-memory only for MVP)
- Send full resource state on every event (resource object only, UI refetches if needed)
- Create SSE endpoint before MSCL-6 REST API foundation exists (blocking dependency)
- Run event detection synchronously in API request path (polling publishes, API streams)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| New S3 bucket created | `sync_changes()` receives Change(CREATED, s3_bucket) | `event_bus.publish("RESOURCE_CREATED", resource)` → SSE client receives `{type: "RESOURCE_CREATED", resource: {...}, timestamp: "2026-10-02T12:34:56Z"}` | FalkorDB write fails: no event emitted (event emission after successful write only) |
| Lambda config updated | Change(UPDATED, lambda_function) | SSE event `RESOURCE_UPDATED` with updated resource payload | N/A |
| DynamoDB table deleted | Change(DELETED, dynamodb_table) | SSE event `RESOURCE_DELETED` with `{id, type, tenant_id}` (minimal payload) | N/A |
| Dependency added (Lambda→S3) | `manager.sync_all_dependencies()` creates DEPENDS_ON | `event_bus.publish("DEPENDENCY_ADDED", {source_id, target_id, type})` | N/A |
| SSE client disconnects | EventSource closes, asyncio.CancelledError raised | Unsubscribe from event bus, clean up queue | No error - normal flow |
| SSE client reconnects | New EventSource connects to `/api/sse` | New subscription created, missed events NOT replayed (stateless) | N/A |
| 10 concurrent SSE connections | 10 browser tabs open for same tenant | All 10 queues receive every event | No performance degradation (asyncio.Queue scales) |
| No subscribers for tenant | Event published but `subscribers[tenant_id]` empty | Event discarded silently | N/A |

</frozen-after-approval>

## Code Map

**Reuse from MSCL-2 (Poller + Change Detection):**
- `control_plane/inventory/poller.py:139-154` -- Change detection creates `Change` objects (CREATED/UPDATED/DELETED)
- `control_plane/inventory/sync.py:18-58` -- `sync_changes()` iterates changes, dispatches to sync handlers
- `control_plane/inventory/sync.py:42-48` -- **Integration point:** add event emission after successful FalkorDB write
- `control_plane/inventory/models.py` -- `ChangeType` enum, `Resource` dataclass with `to_dict()` for serialization

**Reuse from MSCL-5 (Dependency Detection):**
- `control_plane/dependencies/manager.py` -- **Integration point:** emit DEPENDENCY_ADDED/REMOVED after relationship sync

**Reuse from MSCL-6 (REST API Foundation):**
- `api/main.py` -- FastAPI app (MSCL-6 creates this)
- `api/routes/` -- Route modules pattern (add `api/routes/sse.py`)
- `api/middleware/` -- Tenant isolation middleware (reuse for tenant_id validation in SSE endpoint)

**Reuse from MSCL-4 (Observability):**
- `control_plane/observability.py:24-62` -- `trace_operation()` decorator, `log_operational()` for connection events

**New modules to create:**
- `control_plane/events/__init__.py` -- Public API exports
- `control_plane/events/bus.py` -- EventBus class (subscribe/unsubscribe/publish)
- `control_plane/events/models.py` -- Event dataclasses (ResourceEvent, DependencyEvent)
- `api/routes/sse.py` -- SSE endpoint (`GET /api/sse`)
- `web_ui/hooks/useSSE.ts` -- React hook for SSE client (if web_ui/ exists; else deferred)

**Integration points:**
- `sync.py:42-48` -- Add `await event_bus.publish("RESOURCE_CREATED", resource)` after `await graph.upsert_resource()`
- `manager.py` -- Add event emission after `create_relationship()`/`delete_relationship()`
- `api/main.py` -- Register SSE router: `app.include_router(sse.router)`

## Tasks & Acceptance

**Execution:**
- [x] `control_plane/events/__init__.py` -- Create module, export `EventBus` singleton
- [x] `control_plane/events/models.py` -- Define `Event` dataclass (type: str, resource: dict, timestamp: str), `EventType` enum ("RESOURCE_CREATED", "RESOURCE_UPDATED", "RESOURCE_DELETED", "DEPENDENCY_ADDED", "DEPENDENCY_REMOVED", "TAGS_UPDATED")
- [x] `control_plane/events/bus.py` -- Implement `EventBus` class with `subscribe(tenant_id) -> asyncio.Queue`, `unsubscribe(tenant_id, queue)`, `publish(event_type, resource)` using Dict[str, List[asyncio.Queue]] for subscribers
- [x] `control_plane/inventory/sync.py` -- Add event emission after successful FalkorDB operations (lines 42-48): `await event_bus.publish("RESOURCE_CREATED", resource.to_dict())`
- [x] `control_plane/dependencies/manager.py` -- Add event emission after relationship creation: `await event_bus.publish("DEPENDENCY_ADDED", {source_id, target_id, type, metadata})`
- [x] `api/routes/sse.py` -- Create SSE endpoint `GET /api/sse?tenant_id={tenant_id}` using FastAPI `StreamingResponse`, subscribe to event bus, yield SSE-formatted events (`data: {json}\n\n`)
- [x] `api/main.py` -- Register SSE router with `app.include_router(sse.router)` (depends on MSCL-6 creating api/main.py first)
- [x] `tests/test_event_bus.py` -- Unit tests: subscribe/publish, multiple subscribers, unsubscribe cleanup, tenant isolation (events only to matching tenant_id)
- [x] `tests/integration/test_sse_endpoint.py` -- Integration test: create resource via poller → SSE client receives event within 5s, test reconnection, test concurrent connections

**Acceptance Criteria:**
- Given the Web UI is connected to `/api/sse?tenant_id=123456789012`, when a new S3 bucket is created in MiniStack, then within 35 seconds (30s poll + 5s processing), the client receives a RESOURCE_CREATED event
- Given an SSE connection is active, when a Lambda function's configuration is updated, then the client receives a RESOURCE_UPDATED event with the updated resource payload
- Given an SSE connection is active, when a DynamoDB table is deleted, then the client receives a RESOURCE_DELETED event with `{id, type, tenant_id}`
- Given a dependency is detected (Lambda→S3), when `manager.sync_all_dependencies()` completes, then the client receives a DEPENDENCY_ADDED event with `{source_id, target_id, type}`
- Given an SSE connection drops (network issue), when the connection is lost, then the EventSource automatically reconnects and resumes receiving events (no events lost for events emitted after reconnection)
- Given 10 concurrent SSE connections for the same tenant, when a resource event occurs, then all 10 connections receive the event within 5 seconds
- Given SSE connection is requested with invalid tenant_id, then the endpoint returns 400 Bad Request (tenant validation via middleware)

## Spec Change Log

## Design Notes

**Event Bus Architecture:**
```python
# Singleton event bus instance
event_bus = EventBus()

# In sync.py, after successful write:
await event_bus.publish("RESOURCE_CREATED", resource.to_dict())

# In sse.py endpoint:
queue = await event_bus.subscribe(tenant_id)
try:
    while True:
        event = await queue.get()
        yield f"data: {json.dumps(event)}\n\n"
except asyncio.CancelledError:
    await event_bus.unsubscribe(tenant_id, queue)
```

**SSE Endpoint Pattern:**
```python
@router.get("/api/sse")
async def sse_endpoint(tenant_id: str = Query(...)):
    async def event_generator():
        queue = await event_bus.subscribe(tenant_id)
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            await event_bus.unsubscribe(tenant_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

**Tenant Isolation:**
- Event bus maintains separate subscriber lists per tenant_id: `Dict[str, List[asyncio.Queue]]`
- `publish()` only sends events to queues registered for that tenant
- SSE endpoint validates tenant_id via middleware (reuse from MSCL-6)

## Verification

**Commands:**
- `pytest tests/test_event_bus.py -v` -- expected: all unit tests pass
- `pytest tests/integration/test_sse_endpoint.py -v` -- expected: SSE endpoint streams events, reconnection works
- `ruff check control_plane/events/ api/routes/sse.py` -- expected: no lint errors
- `mypy control_plane/events/ api/routes/sse.py` -- expected: no type errors

**Manual checks:**
1. Start control-plane and MiniStack
2. Connect to `http://localhost:3001/api/sse?tenant_id=123456789012` via `curl` or browser EventSource
3. Create S3 bucket via AWS CLI: `aws --endpoint-url=http://localhost:4566 s3 mb s3://test-bucket`
4. Verify SSE client receives RESOURCE_CREATED event within 35 seconds
5. Open 10 browser tabs with SSE connections, create another resource, verify all tabs receive the event
