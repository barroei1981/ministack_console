---
title: 'MSCL-5: Resource Dependency Detection'
type: 'feature'
created: '2026-10-02'
status: 'in-progress'
review_loop_iteration: 0
baseline_commit: '71874dfaf3f69ef1c95e6af9bb37ce82d44a9bf0'
context:
  - '_lch-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Resources exist in FalkorDB without dependency relationships. Developers can't visualize architecture (which Lambda uses which S3 bucket), can't assess deletion impact (what breaks if I delete this SQS queue), and have no visibility into event source mappings or policy relationships.

**Approach:** Detect dependencies by introspecting resource metadata (Lambda environment variables for S3 ARNs, event source mappings for SQS/SNS, S3 bucket policies for IAM roles) and create DEPENDS_ON relationships in FalkorDB. Run detection after each resource sync, compare detected vs existing dependencies, and create/delete relationships accordingly.

## Boundaries & Constraints

**Always:**
- Use existing DEPENDS_ON relationship from MSCL-1 schema (control_plane/graph/schema.py:67-71)
- Store dependency metadata (type, source) as relationship properties: `{type: "environment_variable" | "event_source_mapping" | "bucket_policy", metadata: {...}}`
- Run detection after resource sync in polling cycle (control_plane/inventory/poller.py integration)
- Use async patterns consistent with poller (async/await)
- Reuse create_relationship() from MSCL-1 for idempotent relationship creation
- Extend MiniStackClient with new boto3 methods (list_event_source_mappings, get_bucket_policy)
- Follow observability.md: emit OpenTelemetry traces, use OPERATIONAL logs for detection runs

**Ask First:**
- CloudFormation stack → resource dependencies (requires DescribeStackResources - large scope)
- DynamoDB Stream dependencies (additional boto3 complexity)
- API Gateway → Lambda dependencies (requires API Gateway polling first)
- Transitive dependency queries (graph traversal - can be added later)

**Never:**
- Modify DEPENDS_ON schema (already stable from MSCL-1)
- Create dependencies across tenant boundaries (enforce tenant_id matching)
- Run detection synchronously in API request path (polling only)
- Store full resource state in relationship properties (use metadata keys only)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Lambda with S3 ARN in env var | Lambda.state includes Environment.Variables with "arn:aws:s3:::bucket-name" | DEPENDS_ON created from Lambda to S3 with type="environment_variable" | S3 bucket not found in FalkorDB: log warning, skip dependency |
| Lambda with SQS event source | list_event_source_mappings returns SQS ARN | DEPENDS_ON created from Lambda to SQS with type="event_source_mapping", metadata includes mapping UUID | SQS queue not found: log warning, skip |
| Lambda env var removed | Env var no longer contains S3 ARN | DEPENDS_ON relationship deleted, no event emitted (deferred to MSCL-7) | N/A |
| S3 bucket with IAM policy | get_bucket_policy returns policy with IAM role ARN | DEPENDS_ON created from S3 to IAM with type="bucket_policy" | Bucket has no policy: skip silently |
| S3 bucket policy parse failure | Policy JSON malformed | Log error, skip dependency for this bucket | Don't fail entire detection run |
| Multiple dependencies same resource | Lambda has 3 S3 ARNs in env vars | 3 separate DEPENDS_ON relationships created | N/A |
| Boto3 API call fails | list_event_source_mappings times out | Retry twice with backoff, then skip Lambda dependency detection | Log operational error, continue with other resources |

</frozen-after-approval>

## Code Map

**Reuse from MSCL-1 (FalkorDB Schema + Graph Operations):**
- `control_plane/graph/schema.py:67-71` -- DEPENDS_ON relationship already defined (Resource→Resource)
- `control_plane/graph/query.py:184-259` -- `create_relationship()` for creating DEPENDS_ON relationships with properties
- `control_plane/graph/query.py:262-333` -- `query_nodes()` for finding resources by ID/type/name
- `tests/test_graph_query.py:398-424` -- Example Lambda→S3 dependency test (reference pattern)

**Reuse from MSCL-2 (MiniStackClient + Polling):**
- `control_plane/ministack_client.py:29-62` -- MiniStackClient class with aioboto3 session
- `control_plane/ministack_client.py:64-101` -- `_retry_with_backoff()` decorator (2 retries, 1s/2s delays)
- `control_plane/ministack_client.py:209-271` -- `get_lambda_functions()` returns Lambda metadata
- `control_plane/inventory/poller.py:138-150` -- Change detection (CREATED/UPDATED/DELETED)
- `control_plane/inventory/poller.py:161` -- Integration point: add dependency detection after sync_changes()
- `control_plane/inventory/sync.py:18-58` -- Pattern for syncing changes to FalkorDB

**Reuse from MSCL-3 (Tenant Isolation):**
- Enforce tenant_id matching when creating DEPENDS_ON (both source and target must have same tenant_id)

**Reuse from MSCL-4 (Observability):**
- `control_plane/observability.py:24-62` -- `trace_operation()` decorator for OpenTelemetry tracing
- Operational logging pattern (not AUDIT - dependency detection is analysis, not data modification)

**New modules to create:**
- `control_plane/dependencies/__init__.py` -- Public API exports
- `control_plane/dependencies/models.py` -- Dependency dataclass, DependencyType enum
- `control_plane/dependencies/detector.py` -- detect_lambda_dependencies(), detect_s3_dependencies()
- `control_plane/dependencies/manager.py` -- sync_all_dependencies() orchestrates detection + sync

**Integration points:**
- Extend MiniStackClient with list_event_source_mappings(function_name), get_bucket_policy(bucket_name)
- Call manager.sync_all_dependencies(resources) in poller._poll_cycle() after sync_changes()

## Tasks & Acceptance

**Execution:**
- [x] `control_plane/dependencies/__init__.py` -- Create module, export public functions
- [x] `control_plane/dependencies/models.py` -- Define Dependency dataclass (source_id, target_id, type, metadata), DependencyType enum ("environment_variable", "event_source_mapping", "bucket_policy")
- [x] `control_plane/ministack_client.py` -- Add list_event_source_mappings(function_name) → returns List[EventSourceMapping] with UUID, ARN, State
- [x] `control_plane/ministack_client.py` -- Add get_bucket_policy(bucket_name) → returns policy JSON string or None
- [x] `control_plane/ministack_client.py` -- Add get_lambda_function_config(function_name) → returns full config with Environment.Variables (needed for detection)
- [x] `control_plane/dependencies/detector.py` -- Implement detect_lambda_s3_dependencies(lambda_resource) → parses Environment.Variables for S3 ARNs, returns List[Dependency]
- [x] `control_plane/dependencies/detector.py` -- Implement detect_lambda_event_sources(lambda_resource, client) → calls list_event_source_mappings, parses SQS/SNS ARNs, returns List[Dependency]
- [x] `control_plane/dependencies/detector.py` -- Implement detect_s3_iam_dependencies(s3_resource, client) → calls get_bucket_policy, parses IAM role ARNs from Principal.AWS, returns List[Dependency]
- [x] `control_plane/dependencies/manager.py` -- Implement sync_all_dependencies(resources) → runs detection for each resource, compares with existing DEPENDS_ON, creates/deletes relationships
- [x] `control_plane/graph/query.py` -- Add query_relationships() for querying existing DEPENDS_ON relationships
- [x] `control_plane/graph/query.py` -- Add delete_relationship() for deleting stale DEPENDS_ON relationships
- [x] `control_plane/inventory/poller.py` -- Integrate: call sync_all_dependencies(all_resources) after sync_changes() at line 161, wrap in try/except to prevent poller failure
- [x] `tests/test_dependencies_detector.py` -- Unit tests: Lambda env var parsing (valid ARN, malformed ARN, no S3 ARNs), event source mapping parsing, S3 policy parsing
- [x] `tests/test_dependencies_manager.py` -- Unit tests: sync creates new relationships, sync deletes stale relationships, tenant isolation (no cross-tenant dependencies)
- [ ] `tests/integration/test_dependencies_e2e.py` -- Integration test: create Lambda with S3 env var → poll → verify DEPENDS_ON in FalkorDB; remove env var → poll → verify DEPENDS_ON deleted

**Acceptance Criteria:**
- Given a Lambda function has environment variable "BUCKET_NAME=arn:aws:s3:::my-bucket", when dependency detection runs, then a (:Lambda)-[:DEPENDS_ON {type: "environment_variable"}]->(:S3) relationship is created and I can query "What does this Lambda depend on?" to see the S3 bucket
- Given a Lambda function has an SQS event source mapping, when dependency detection runs, then a DEPENDS_ON relationship is created from Lambda to SQS with metadata including the mapping UUID
- Given an S3 bucket has a policy with Principal.AWS="arn:aws:iam::123456789012:role/MyRole", when dependency detection runs, then a DEPENDS_ON relationship is created from S3 to IAM role
- Given a Lambda env var referencing S3 is removed, when dependency detection runs, then the existing DEPENDS_ON relationship is deleted from FalkorDB
- Given I query "What depends on this S3 bucket?", when the query executes, then all Lambdas with DEPENDS_ON relationships to that bucket are returned with dependency type "environment_variable"

## Spec Change Log

### Review Findings

**Decision Needed:**
- [x] [Review][Decision] No cleanup of orphaned DEPENDS_ON relationships when source resource deleted — **RESOLVED: Use soft deletion with deleted_at timestamp. Add deleted_at property to DEPENDS_ON relationships when source/target deleted. Update queries to filter WHERE r.deleted_at IS NULL. Provide get_historical_dependencies() for audit trail.**

**Patch Required:**
- [ ] [Review][Patch] Soft delete orphaned dependencies — Add deleted_at timestamp property to DEPENDS_ON relationships, update manager.py to set deleted_at on resource deletion, update query_relationships() to filter deleted_at IS NULL by default [manager.py, query.py]
- [ ] [Review][Patch] Missing AUDIT logs for dependency creates/deletes — data modifications must emit audit events per observability.md [manager.py:846, 863]
- [ ] [Review][Patch] Missing SECURITY logs for cross-tenant dependency blocks — security decisions must be logged with SECURITY type per observability.md [manager.py:831-836, 932-938]
- [ ] [Review][Patch] Missing structured logging with type classification — all logs use plain logger.debug/info instead of log_operational/log_security/log_audit per observability.md [dependencies/*.py]
- [ ] [Review][Patch] Missing OpenTelemetry instrumentation — no trace_operation() wrappers for dependency sync operations per observability.md [manager.py, detector.py]
- [ ] [Review][Patch] Missing integration test test_dependencies_e2e.py — acceptance criteria cannot be verified end-to-end without this test [tests/integration/]
- [ ] [Review][Patch] Blind exception catches — detector.py uses bare except, should catch specific exceptions (ClientError, JSONDecodeError) [detector.py:497, 564]
- [ ] [Review][Patch] Duplicate sync logic — ~80 lines duplicated between _sync_lambda_dependencies and _sync_s3_dependencies, extract common logic to helper [manager.py:759-869, 871-972]
- [ ] [Review][Patch] Missing field validation — direct dict access without checking keys exist (resource["id"], resource["name"], resource["tenant_id"]) [detector.py:459-460, manager.py:774-775]

**Deferred (Pre-existing or Out of Scope):**
- [x] [Review][Defer] N+1 query problem — query_relationships called once per resource instead of batching [manager.py:789, 892] — deferred, performance optimization
- [x] [Review][Defer] Sequential resource processing — Lambda and S3 resources processed serially, should use asyncio.gather for concurrency [manager.py:728-748] — deferred, performance optimization

## Design Notes

**ARN Parsing Pattern:**
```python
def extract_s3_bucket_from_arn(arn: str) -> Optional[str]:
    # "arn:aws:s3:::bucket-name" or "arn:aws:s3:::bucket-name/key"
    if not arn.startswith("arn:aws:s3:::"):
        return None
    parts = arn.split("arn:aws:s3:::")[-1].split("/")
    return parts[0] if parts else None

def extract_sqs_queue_from_arn(arn: str) -> Optional[str]:
    # "arn:aws:sqs:us-east-1:000000000000:queue-name"
    if ":sqs:" not in arn:
        return None
    return arn.split(":")[-1]
```

**Dependency Sync Algorithm:**
```python
async def sync_all_dependencies(resources: List[Resource]):
    for resource in resources:
        detected = await detect_dependencies(resource)
        existing = await get_existing_dependencies(resource.id)
        
        # Create new dependencies
        for dep in detected:
            if dep not in existing:
                await create_relationship(resource.id, dep.target_id, "DEPENDS_ON", dep.properties)
        
        # Delete stale dependencies
        for dep in existing:
            if dep not in detected:
                await delete_relationship(resource.id, dep.target_id, "DEPENDS_ON")
```

**Lambda Environment Variables Fetching:**
Lambda.state from polling doesn't include environment variables. Detection must call `lambda_client.get_function(FunctionName=name)` to retrieve full configuration including `Environment.Variables`.

**Observability:**
Use OPERATIONAL logs (not AUDIT) - dependency detection is analysis/observation, not data modification. Emit traces for detection runs and relationship sync operations.

## Verification

**Commands:**
- `pytest tests/test_dependencies_detector.py -v` -- expected: all ARN parsing and detection tests pass
- `pytest tests/test_dependencies_manager.py -v` -- expected: all sync logic tests pass
- `pytest tests/integration/test_dependencies_e2e.py -v` -- expected: end-to-end dependency lifecycle tests pass
- `mypy control_plane/dependencies/` -- expected: no type errors
- `ruff check control_plane/dependencies/` -- expected: no lint errors

**Manual checks:**
- After running poller: query FalkorDB for DEPENDS_ON relationships, verify metadata properties present
- Check logs for "Dependency detection" operational messages, verify tracing spans emitted
