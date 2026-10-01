---
title: 'MSCL-2: MiniStack Integration and Resource Polling'
type: 'feature'
created: '2026-10-02'
status: 'done'
review_loop_iteration: 0
baseline_commit: '6c353795b7b31cef2015cc75c5099a7162db6764'
context:
  - '_lch-output/implementation-artifacts/epic-1-context.md'
  - 'control_plane/graph/query.py'
  - 'control_plane/graph/schema.py'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Control-plane has no visibility into MiniStack's resource state. Cannot track what S3 buckets, Lambda functions, or DynamoDB tables exist, detect when resources are created/modified/deleted, or maintain a real-time inventory for the Web UI and MCP Server.

**Approach:** Implement async polling loop using boto3 to query MiniStack API every 30 seconds, detect resource changes (create/update/delete) via snapshot comparison, and sync discovered resources to FalkorDB graph using MSCL-1's graph operations.

## Boundaries & Constraints

**Always:**
- Use boto3 with MiniStack endpoint (localhost:4566) per AD-8
- Poll every 30 seconds (configurable via POLL_INTERVAL_SECONDS env var)
- Sync all changes to FalkorDB using `create_node()` and `query_nodes()` from control_plane/graph/query.py
- Use async/await patterns for all I/O operations (boto3 via aioboto3 or asyncio.to_thread)
- Retry MiniStack API calls 2 times with exponential backoff (1s, 2s) per AD-12
- After 3 consecutive poll failures (90 seconds), mark resources as "stale" in FalkorDB
- Support Phase 1 services only: S3 (buckets), Lambda (functions), DynamoDB (tables)

**Ask First:**
- Adding support for additional AWS services beyond S3/Lambda/DynamoDB
- Changing polling interval from 30 seconds
- Changing retry strategy or failure thresholds

**Never:**
- Write to FalkorDB directly via Cypher queries (always use control_plane/graph/query.py operations)
- Block the event loop with synchronous I/O (boto3 clients must run in thread pool or use aioboto3)
- Skip health checks before polling (must verify MiniStack is reachable)
- Hardcode AWS credentials or endpoint URLs (must be configurable)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First poll, MiniStack healthy | 3 S3 buckets, 2 Lambda functions exist | All 5 resources created as Resource nodes in FalkorDB with type, name, tenant_id, arn, state | N/A |
| Resource created between polls | New bucket "test-bucket" appears | RESOURCE_CREATED change detected, new Resource node created, tenant_id extracted from access key | N/A |
| Resource deleted between polls | Lambda function "func-1" missing | RESOURCE_DELETED change detected, Resource node deleted from FalkorDB | N/A |
| Resource modified between polls | Bucket versioning enabled | RESOURCE_UPDATED change detected, Resource.state JSON updated in FalkorDB | N/A |
| MiniStack unreachable (port closed) | Connection refused on localhost:4566 | Retry 2 times (1s, 2s backoff), log error, skip this poll cycle, continue next cycle | After 3 consecutive failures (90s), mark all resources as stale |
| MiniStack restart detected | Health check shows different instance ID | Detect restart, trigger full re-inventory (query all services), clear stale markers, complete within 1 minute | Log restart event for debugging |
| Empty tenant (no resources) | list_buckets() returns empty, list_functions() returns empty | No Resource nodes created, poll completes successfully with zero changes | N/A |
| boto3 API error (throttling, 500) | S3 ListBuckets raises BotoCoreError | Retry 2 times, if still fails log error and skip S3 this cycle (continue with Lambda/DynamoDB), mark S3 resources stale after 3 cycles | Do not crash poller, gracefully degrade per-service |

</frozen-after-approval>

## Code Map

**Reuse from MSCL-1:**
- `control_plane/graph/query.py` -- create_node(), query_nodes(), delete_node() for FalkorDB CRUD operations
- `control_plane/graph/schema.py` -- SCHEMA constant defines Resource node properties (id, type, name, tenant_id, arn, state, created_at, updated_at)

**New modules to create:**
- `control_plane/ministack_client.py` -- boto3 wrapper with retry logic, provides get_s3_buckets(), get_lambda_functions(), get_dynamodb_tables(), health_check()
- `control_plane/inventory/poller.py` -- Main async polling loop, orchestrates polling cycle every 30s, handles MiniStack restart detection
- `control_plane/inventory/detector.py` -- Change detection algorithm, compares current state to last snapshot, returns list of Change objects (CREATED/UPDATED/DELETED)
- `control_plane/inventory/sync.py` -- Sync layer to FalkorDB, translates Change objects to graph operations (create/update/delete Resource nodes)
- `control_plane/inventory/models.py` -- Data classes: Resource, Change, ChangeType enum, Snapshot

**Configuration:**
- Environment variables: MINISTACK_ENDPOINT (default localhost:4566), POLL_INTERVAL_SECONDS (default 30), MINISTACK_ACCESS_KEY (12-digit tenant ID)

## Tasks & Acceptance

**Execution:**
- [x] `control_plane/ministack_client.py` -- Create boto3 client wrapper with retry logic and health check using aioboto3 or asyncio.to_thread -- Required for AD-8 (polling strategy) and AD-12 (retry logic)
- [x] `control_plane/inventory/models.py` -- Define Resource, Change, ChangeType, Snapshot data classes with type hints -- Required for type safety and change detection algorithm
- [x] `control_plane/inventory/detector.py` -- Implement change detection: compare current resources to last snapshot, return list of changes with type (CREATED/UPDATED/DELETED) -- Required for incremental updates per AD-8
- [x] `control_plane/inventory/sync.py` -- Implement sync_changes(changes: List[Change]): for each change, call create_node/query_nodes/delete_node from graph/query.py -- Required for FR-1 (resource inventory)
- [x] `control_plane/inventory/poller.py` -- Implement async polling loop: every 30s, fetch resources via ministack_client, detect changes, sync to FalkorDB, handle errors per AD-12 -- Required for FR-1 (resource inventory) and AD-8 (polling strategy)
- [x] `tests/test_ministack_client.py` -- Unit tests for boto3 client wrapper: test retry logic, health check, resource fetching, error handling -- Required for quality gates
- [x] `tests/test_detector.py` -- Unit tests for change detection algorithm: test CREATED/UPDATED/DELETED detection, empty snapshots, no changes -- Required for quality gates
- [x] `tests/test_sync.py` -- Unit tests for sync layer: verify correct graph operations called for each change type -- Required for quality gates
- [x] `tests/integration/test_polling_e2e.py` -- Integration test: mock MiniStack API, run one poll cycle, verify resources appear in FalkorDB within 30s -- Required for AC validation

**Acceptance Criteria:**
- Given MiniStack is running on localhost:4566, when the control-plane starts, then it connects to MiniStack successfully, begins polling every 30 seconds, and detects MiniStack health status
- Given MiniStack has 3 S3 buckets and 2 Lambda functions, when the poller runs, then all 5 resources are discovered and stored in FalkorDB as Resource nodes with id, type, name, tenant_id, arn, state, created_at, updated_at
- Given a new S3 bucket is created in MiniStack, when the next poll cycle runs, then the new resource is detected, added to FalkorDB, and a RESOURCE_CREATED change is logged
- Given a Lambda function is deleted from MiniStack, when the next poll cycle runs, then the resource is removed from FalkorDB and a RESOURCE_DELETED change is logged
- Given a DynamoDB table's configuration is modified in MiniStack, when the next poll cycle runs, then the Resource.state JSON is updated in FalkorDB and a RESOURCE_UPDATED change is logged
- Given MiniStack is unreachable (connection refused), when the poller attempts to connect, then it retries 2 times with exponential backoff (1s, 2s), logs the error, and after 3 consecutive failures (90 seconds) marks all resources as "stale"
- Given MiniStack restarts (state cleared), when the poller detects the restart via health check, then it performs a full re-inventory, clears all stale markers, and completes within 1 minute

## Spec Change Log

## Design Notes

**Change Detection Algorithm:**
```python
def detect_changes(current: List[Resource], previous: Snapshot) -> List[Change]:
    current_ids = {r.id for r in current}
    previous_ids = {r.id for r in previous.resources}
    
    created = [r for r in current if r.id not in previous_ids]
    deleted_ids = previous_ids - current_ids
    updated = [r for r in current 
               if r.id in previous_ids and r != previous.get(r.id)]
    
    return [
        *[Change(CREATED, resource=r) for r in created],
        *[Change(UPDATED, resource=r) for r in updated],
        *[Change(DELETED, resource_id=id) for id in deleted_ids]
    ]
```

**Tenant Extraction:**
- Tenant ID = AWS access key used to create boto3 session (12-digit MiniStack access key)
- Each Resource node gets tenant_id property for multi-tenant isolation per FR-3

**Async Polling Loop:**
```python
async def poll_loop():
    while True:
        try:
            if not await ministack_client.health_check():
                await handle_restart()
                continue
            
            resources = await fetch_all_resources()
            changes = detector.detect_changes(resources, last_snapshot)
            await sync.sync_changes(changes)
            
            last_snapshot = Snapshot(resources)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Poll error: {e}")
            failure_count += 1
            if failure_count >= 3:
                await mark_resources_stale()
            await asyncio.sleep(5)
```

## Verification

**Commands:**
- `pytest tests/test_ministack_client.py -v` -- expected: all boto3 client tests pass
- `pytest tests/test_detector.py -v` -- expected: all change detection tests pass
- `pytest tests/test_sync.py -v` -- expected: all sync layer tests pass
- `pytest tests/integration/test_polling_e2e.py -v` -- expected: E2E polling test passes (requires mocked MiniStack)
- `python -m control_plane.inventory.poller` -- expected: starts polling loop, logs "Poll cycle complete" every 30s

**Manual checks:**
- Start MiniStack: `docker run -p 4566:4566 ministackorg/ministack`
- Start poller, create S3 bucket via AWS CLI: `aws s3 mb s3://test-bucket --endpoint-url=http://localhost:4566`
- Within 30s, verify bucket appears in FalkorDB: `python -c "from control_plane.graph.query import query_nodes; print(query_nodes('Resource', {'type': 's3:bucket'}))"`
