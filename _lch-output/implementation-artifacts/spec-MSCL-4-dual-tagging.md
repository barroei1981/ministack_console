---
title: 'MSCL-4: Dual Tagging System (Control-Plane + Native)'
type: 'feature'
created: '2026-10-02'
status: 'done'
review_loop_iteration: 1
baseline_commit: '9a9da7c935c16a353496f0e50143fe45d13ae6cc'
context:
  - '_lch-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Resources lack a tagging system for logical organization. Developers need to group resources by project (control-plane tags for internal organization) while maintaining AWS CLI/SDK compatibility (native MiniStack tags). Without dual tagging, either control-plane organization OR AWS compatibility must be sacrificed.

**Approach:** Implement two independent tagging systems: (1) Control-plane tags stored in FalkorDB via TAGGED_WITH relationships (applies to ALL resources, all service types), (2) Native tags written through to both FalkorDB (namespace: "native") and MiniStack via boto3 APIs (applies to taggable services only: S3, Lambda, DynamoDB). Both systems coexist without collision via namespace isolation.

## Boundaries & Constraints

**Always:**
- Use existing TAGGED_WITH relationship from MSCL-1 schema (control_plane/graph/schema.py:72-78)
- Namespace isolation: control-plane tags (namespace: "control_plane"), native tags (namespace: "native")
- Write-through for native tags: FalkorDB first, then boto3 to MiniStack
- Enforce tenant_id filtering on all tag queries (MSCL-3 isolation)
- Use TAGGABLE_SERVICES constant (S3, Lambda, DynamoDB) to gate boto3 calls
- Reuse graph operations (create_node, create_relationship, query_nodes) from MSCL-1
- Reuse boto3 client infrastructure and retry logic from MSCL-2

**Ask First:**
- CloudFormation stack tag propagation (requires stack tracking - deferred)
- Tag validation rules (reserved keys, character limits - deferred)
- Bulk tagging operations (batch API - deferred)
- Tag history/audit trail (requires event system - MSCL-7)

**Never:**
- Skip namespace validation (control_plane vs native)
- Allow unvalidated tag keys (prevent Cypher injection)
- Write native tags to MiniStack for non-taggable services (store in FalkorDB only, log warning)
- Query tags across namespaces without explicit namespace filter
- Create tags without tenant_id context

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Add control-plane tag to S3 bucket | resource_id="s3:bucket:test", key="project", value="microservice-a" | Tag stored in FalkorDB: (:Resource)-[:TAGGED_WITH {namespace:"control_plane"}]->(:Tag {key:"project"}), tag applies to resource | N/A |
| Add control-plane tag to Lambda | resource_id="lambda:function:handler", key="team", value="backend" | Tag stored in FalkorDB, no boto3 call (control-plane tags don't propagate to MiniStack) | N/A |
| Add native tag to S3 bucket | resource_id="s3:bucket:test", key="Name", value="uploads" | Tag stored in FalkorDB (namespace:"native") AND written to MiniStack via put_bucket_tagging | boto3 failure: FalkorDB update succeeds, boto3 error logged, caller receives partial success warning |
| Add native tag to non-taggable service | resource_id="sqs:queue:tasks", key="Name", value="task-queue" | Tag stored in FalkorDB (namespace:"native") only, warning logged: "SQS does not support native tagging" | No error raised (store succeeds in FalkorDB) |
| Query resources by control-plane tag | key="project", value="microservice-a", tenant_id="123456789012" | Returns all resources with matching control-plane tag in tenant | Empty list if no matches |
| Get all tags for resource | resource_id="s3:bucket:test" | Returns {"control_plane": {"project": "microservice-a"}, "native": {"Name": "uploads"}} | Empty dicts if no tags in each namespace |
| Remove control-plane tag | resource_id="s3:bucket:test", key="project" | Deletes TAGGED_WITH relationship with namespace="control_plane" and key="project" | No error if tag doesn't exist (idempotent) |
| Remove native tag from S3 | resource_id="s3:bucket:test", key="Name" | Deletes from FalkorDB AND removes from MiniStack via put_bucket_tagging (send remaining tags) | boto3 failure: FalkorDB delete succeeds, boto3 error logged |

</frozen-after-approval>

## Code Map

**Reuse from MSCL-1 (FalkorDB Schema + Graph Operations):**
- `control_plane/graph/schema.py:48-51` -- Tag node type already defined with `key` and `value` properties
- `control_plane/graph/schema.py:72-78` -- TAGGED_WITH relationship already defined, supports namespace property
- `control_plane/graph/query.py:130-182` -- `create_node()` for creating Tag nodes
- `control_plane/graph/query.py:184-260` -- `create_relationship()` for TAGGED_WITH relationships between Resource and Tag
- `control_plane/graph/query.py:262-333` -- `query_nodes()` for tag queries with filters
- `control_plane/graph/__init__.py:7-12` -- Graph operations exported from module

**Reuse from MSCL-2 (Boto3 Client + Async Patterns):**
- `control_plane/ministack_client.py:29-62` -- MiniStackClient class with aioboto3 session management, endpoint_url configuration
- `control_plane/ministack_client.py:64-101` -- `_retry_with_backoff()` decorator for exponential backoff (1s, 2s) with MAX_RETRIES=2
- `control_plane/ministack_client.py:139-207` -- Async context manager pattern for boto3 clients (S3, Lambda, DynamoDB)

**Reuse from MSCL-3 (Tenant Isolation):**
- `control_plane/tenants/isolation.py:21-41` -- `validate_tenant_id()` for 12-digit validation
- `control_plane/tenants/isolation.py:78-117` -- Pattern for tenant-scoped queries using `filters={"tenant_id": tenant_id}`

**New modules to create:**
- `control_plane/tagging/__init__.py` -- Public API exports
- `control_plane/tagging/models.py` -- TAGGABLE_SERVICES constant, TagNamespace enum
- `control_plane/tagging/control_plane.py` -- Control-plane tag operations (FalkorDB only)
- `control_plane/tagging/native.py` -- Native tag operations (dual-write FalkorDB + boto3)

**Integration points:**
- Extend MiniStackClient with tagging methods for S3 (put_bucket_tagging/get_bucket_tagging), Lambda (tag_resource/list_tags), DynamoDB (tag_resource/list_tags_of_resource)

## Tasks & Acceptance

**Execution:**
- [x] `control_plane/tagging/__init__.py` -- Create module, export public API from control_plane.py and native.py
- [x] `control_plane/tagging/models.py` -- Define TAGGABLE_SERVICES constant (["s3:bucket", "lambda:function", "dynamodb:table"]), TagNamespace enum, AWS_RESERVED_PREFIXES constant (["aws:", "AWS:"]) -- Required for service-type routing and namespace validation
- [x] `control_plane/tagging/models.py` -- Define AWS constraint constants: MAX_TAG_KEY_LENGTH=128, MAX_TAG_VALUE_LENGTH=256 -- Required for AWS compatibility
- [x] `control_plane/tagging/control_plane.py` -- Implement add_control_plane_tag(resource_id, key, value, tenant_id) with OpenTelemetry tracing and AUDIT logging (WHO/WHAT/WHEN/BEFORE/AFTER): create Tag node, create TAGGED_WITH relationship with namespace="control_plane" -- Required for FR-4 + observability.md
- [x] `control_plane/tagging/control_plane.py` -- Implement remove_control_plane_tag(resource_id, key, tenant_id) with OpenTelemetry tracing and AUDIT logging: delete TAGGED_WITH relationship (idempotent) -- Required for tag lifecycle + observability.md
- [x] `control_plane/tagging/control_plane.py` -- Implement get_control_plane_tags(resource_id, tenant_id) with OpenTelemetry tracing: query all TAGGED_WITH relationships with namespace="control_plane" for resource -- Required for tag retrieval
- [x] `control_plane/tagging/control_plane.py` -- Implement query_resources_by_tag(key, value, tenant_id, resource_type=None) with OpenTelemetry tracing: query Resources via TAGGED_WITH with namespace="control_plane", filter by tenant_id -- Required for project-based resource filtering
- [x] `control_plane/tagging/native.py` -- Implement validate_aws_tag(key, value): enforce AWS constraints (key ≤128 chars, value ≤256 chars, block reserved prefixes for native tags) -- Required for AWS compatibility
- [x] `control_plane/tagging/native.py` -- Implement add_native_tag(resource_id, key, value, tenant_id) with OpenTelemetry tracing, AUDIT logging, and AWS validation: dual-write to FalkorDB (namespace="native") AND boto3 (if resource_type in TAGGABLE_SERVICES) -- Required for NFR-6 + observability.md + AWS compatibility
- [x] `control_plane/tagging/native.py` -- Implement remove_native_tag(resource_id, key, tenant_id) with OpenTelemetry tracing and AUDIT logging: remove from FalkorDB AND boto3 (update remaining tags), return consistent partial-success indicator -- Required for tag lifecycle + observability.md
- [x] `control_plane/tagging/native.py` -- Implement get_native_tags(resource_id, tenant_id) with OpenTelemetry tracing: query TAGGED_WITH with namespace="native" -- Required for native tag retrieval
- [x] `control_plane/tagging/native.py` -- Implement sync_native_tags_from_ministack(resource_id) with error handling: skip invalid keys from MiniStack, log warning, continue sync for remaining tags -- Required for drift detection + robustness
- [x] `tests/test_tagging_control_plane.py` -- Unit tests: add/remove/get control-plane tags, query by tag with tenant filtering, multiple tags on single resource, idempotent remove, AWS validation (128 char key limit, 256 char value limit) -- Required for quality gates
- [x] `tests/test_tagging_native.py` -- Unit tests: add/remove/get native tags for taggable services, non-taggable service warning, namespace isolation, AWS reserved prefix blocking, remove_native_tag boto3 failure (verify partial success), error handling consistency -- Required for quality gates
- [x] `tests/integration/test_tagging_e2e.py` -- Integration test: native tag write-through (add tag → verify in both FalkorDB and MiniStack via boto3), query by project tag across multiple service types (S3, Lambda, DynamoDB), sync with invalid keys from MiniStack -- Required for AC validation

**Acceptance Criteria:**
- Given I tag an S3 bucket with control-plane tag (key="project", value="microservice-a"), when the tag is applied, then it is stored in FalkorDB as (:Resource)-[:TAGGED_WITH {namespace:"control_plane", key:"project", value:"microservice-a"}]->(:Tag), the tag applies to the resource regardless of service type, and I can query all resources with project="microservice-a" across multiple tenants
- Given I tag an S3 bucket with native tag (key="Name", value="uploads"), when the tag is applied, then it is stored in FalkorDB (namespace:"native") AND written to MiniStack via put_bucket_tagging, the tag is visible in AWS CLI (aws s3api get-bucket-tagging), and I can retrieve the tag via get_native_tags()
- Given I tag a Lambda function with control-plane tag, when the tag is applied, then it is stored in FalkorDB only (control-plane tags don't propagate to MiniStack), Lambda native tags are handled separately via add_native_tag(), and both namespaces coexist without collision
- Given I query resources by project tag (key="project", value="microservice-a"), when the query executes with tenant filtering (tenant_id="123456789012"), then all resources with that control-plane tag in the tenant are returned, resources span multiple service types (S3, Lambda, DynamoDB), and resources from other tenants are never included
- Given I attempt to apply native tags to a non-taggable service (e.g., SQS queue), when add_native_tag() is called, then the tag is stored in FalkorDB (namespace:"native"), no boto3 call is made to MiniStack, and a warning is logged ("SQS does not support native tagging")

## Spec Change Log

### 2026-10-02 - Review Loop 1

**Triggering findings:**
1. Missing OpenTelemetry traces for tag operations (violates observability.md Part 2)
2. Missing AUDIT logs for data modifications (violates observability.md - tag add/remove are data changes requiring WHO/WHAT/WHEN/BEFORE/AFTER)
3. Tag key/value validation doesn't enforce AWS constraints (128 char key max, 256 char value max, additional allowed characters)
4. Reserved AWS prefixes (`aws:`, `AWS:`) not blocked for native tags
5. S3 tagging has race condition (read-modify-write last-writer-wins)
6. Sync operation crashes on invalid keys from MiniStack (should skip/warn, not fail)
7. Tenant isolation not validated in MiniStack client tagging methods
8. Error handling inconsistency between add/remove native tags

**Amendments:**
- **Tasks section**: Add OpenTelemetry instrumentation task for all tag operations (add/remove/query)
- **Tasks section**: Replace operational logging with AUDIT logging for data modifications (add_control_plane_tag, remove_control_plane_tag, add_native_tag, remove_native_tag)
- **Boundaries & Constraints - Always**: Add explicit "Follow observability.md: emit OpenTelemetry traces, use AUDIT logs for data modifications"
- **Boundaries & Constraints - Always**: Add "Enforce AWS tag constraints: keys ≤128 chars, values ≤256 chars, block `aws:`/`AWS:` prefixes for native tags"
- **Design Notes**: Add AWS validation rules and reserved prefix blocking
- **Design Notes**: Document S3 race condition (read-modify-write), note optimistic locking deferred
- **Design Notes**: Add sync error handling (skip invalid keys, log warning, continue)
- **Verification**: Add observability checks: grep for AUDIT logs, verify OpenTelemetry calls
- **Tasks section**: Add test for remove_native_tag boto3 failure
- **Tasks section**: Add test for sync with invalid keys from MiniStack

**Known-bad state avoided:**
- Unobservable tag operations (no traces, no audit trail)
- Tag keys/values that break AWS/MiniStack compatibility
- Sync failures on external invalid data
- Concurrent S3 tag updates silently losing data

**KEEP instructions (preserve in re-implementation):**
- Dual tagging architecture (control-plane + native namespaces via namespace property)
- Tenant isolation via tenant_id filtering on all queries
- Idempotent operations (MERGE for add, graceful for remove)
- Comprehensive test structure (unit + integration split)
- Boto3 client extensions with _retry_with_backoff pattern
- Tag key Cypher injection prevention (alphanumeric validation - extend, don't remove)
- Graceful boto3 failure handling (FalkorDB succeeds, boto3 warning logged)

## Design Notes

**AWS Tag Validation Rules:**
```python
# Tag key constraints (AWS standard)
MAX_TAG_KEY_LENGTH = 128
ALLOWED_KEY_CHARS = alphanumeric + "_-.: /=+@"  # extends current alphanumeric + "_-."

# Tag value constraints
MAX_TAG_VALUE_LENGTH = 256
ALLOWED_VALUE_CHARS = any (no restriction beyond length)

# Reserved prefixes (block for native tags only)
AWS_RESERVED_PREFIXES = ["aws:", "AWS:"]

def validate_aws_tag(key, value, is_native=False):
    if len(key) > MAX_TAG_KEY_LENGTH:
        raise ValueError(f"Tag key exceeds {MAX_TAG_KEY_LENGTH} characters")
    if len(value) > MAX_TAG_VALUE_LENGTH:
        raise ValueError(f"Tag value exceeds {MAX_TAG_VALUE_LENGTH} characters")
    if is_native and any(key.startswith(prefix) for prefix in AWS_RESERVED_PREFIXES):
        raise ValueError(f"Native tags cannot use reserved prefix: {AWS_RESERVED_PREFIXES}")
    # Cypher injection prevention: alphanumeric + allowed special chars
    if not re.match(r'^[a-zA-Z0-9_\-.:/=+@\s]+$', key):
        raise ValueError("Tag key contains invalid characters")
```

**Observability Requirements:**
All tag operations (add/remove/query) must emit:
1. **OpenTelemetry traces:** Use `@trace.start_as_current_span()` decorator on public functions
2. **AUDIT logs:** Data modifications (add_control_plane_tag, remove_control_plane_tag, add_native_tag, remove_native_tag) require structured AUDIT logs with:
   - WHO: tenant_id, user_id (if available)
   - WHAT: resource_id, action (TAG_ADDED / TAG_REMOVED), tag key/value
   - WHEN: timestamp (ISO 8601)
   - BEFORE/AFTER: old tags dict / new tags dict
   - status: SUCCESS / FAILURE

Example AUDIT log:
```python
log_audit(
    "Resource tag added",
    event_type="TAG_ADDED",
    actor={"id": tenant_id, "type": "TENANT"},
    target={"type": "RESOURCE", "id": resource_id},
    action="CREATE",
    status="SUCCESS",
    changes={"before": old_tags, "after": new_tags}
)
```

**Native Tag Write-Through Pattern (S3 Example):**
```python
async def add_native_tag(resource_id: str, key: str, value: str, tenant_id: str):
    # 0. Validate AWS constraints
    validate_aws_tag(key, value, is_native=True)
    
    # 1. Store in FalkorDB (always succeeds or raises)
    await add_tag_to_graph(resource_id, key, value, namespace="native", tenant_id=tenant_id)
    
    # 2. Write to MiniStack (if service supports native tagging)
    resource_type = extract_resource_type(resource_id)  # "s3:bucket"
    if resource_type in TAGGABLE_SERVICES:
        try:
            client = MiniStackClient()
            if resource_type == "s3:bucket":
                existing_tags = await client.get_bucket_tagging(bucket_name)
                new_tags = {**existing_tags, key: value}
                await client.put_bucket_tagging(bucket_name, new_tags)
        except Exception as e:
            logger.warning(f"Native tag write to MiniStack failed: {e}")
            # FalkorDB update succeeded, boto3 failed - partial success
            
    # 3. AUDIT log
    log_audit("Native tag added", resource_id=resource_id, key=key, value=value, tenant_id=tenant_id)
```

**Sync Error Handling Pattern:**
```python
async def sync_native_tags_from_ministack(resource_id: str):
    ministack_tags = await get_tags_from_ministack(resource_id)
    
    for key, value in ministack_tags.items():
        try:
            validate_aws_tag(key, value, is_native=True)
            await add_native_tag(resource_id, key, value, tenant_id)
        except ValueError as e:
            # Skip invalid keys, log warning, continue with remaining tags
            logger.warning(f"Skipping invalid tag from MiniStack: {key}={value}, error: {e}")
            continue
```

**S3 Race Condition (Known Limitation):**
S3 tagging uses read-modify-write pattern (get existing → merge → put all). Concurrent tag additions to the same bucket result in last-write-wins; earlier tag is lost. Full fix requires optimistic locking (e.g., ETags, conditional PUT) - **deferred to future story**. Document this limitation in API docs.

**Boto3 Tagging API Differences:**
- **S3:** `put_bucket_tagging(Bucket, Tagging={'TagSet': [{'Key': k, 'Value': v}]})` - replaces all tags (read-modify-write required)
- **Lambda:** `tag_resource(Resource=arn, Tags={'key': 'value'})` - merges with existing (atomic)
- **DynamoDB:** `tag_resource(ResourceArn, Tags=[{'Key': k, 'Value': v}])` - merges with existing (atomic)

**Namespace Isolation:**
Control-plane and native tags are stored in separate relationship properties via `namespace` field. Queries filter by namespace to prevent collision. A resource can have BOTH control-plane tag "project:microservice-a" AND native tag "project:prod" without conflict.

## Verification

**Commands:**
- `pytest tests/test_tagging_control_plane.py -v` -- expected: all unit tests pass
- `pytest tests/test_tagging_native.py -v` -- expected: all unit tests pass
- `pytest tests/integration/test_tagging_e2e.py -v` -- expected: write-through integration test passes
- `mypy control_plane/tagging/` -- expected: no type errors
- `ruff check control_plane/tagging/` -- expected: no lint errors

**Observability Verification:**
- `grep -r "log_audit\|logger.audit" control_plane/tagging/` -- expected: AUDIT logs present in add_control_plane_tag, remove_control_plane_tag, add_native_tag, remove_native_tag
- `grep -r "@trace\|start_as_current_span" control_plane/tagging/` -- expected: OpenTelemetry tracing present in all public functions
- `grep -r "event_type.*TAG_" control_plane/tagging/` -- expected: AUDIT logs use TAG_ADDED / TAG_REMOVED event types
- `grep -r "changes.*before.*after" control_plane/tagging/` -- expected: AUDIT logs include BEFORE/AFTER state

**AWS Validation Verification:**
- `grep -r "MAX_TAG_KEY_LENGTH\|MAX_TAG_VALUE_LENGTH" control_plane/tagging/` -- expected: AWS length constraints enforced
- `grep -r "AWS_RESERVED_PREFIXES\|aws:" control_plane/tagging/` -- expected: Reserved prefix blocking present
- `pytest tests/test_tagging_native.py::test_aws_reserved_prefix_blocked -v` -- expected: test exists and passes
- `pytest tests/test_tagging_control_plane.py::test_tag_key_too_long -v` -- expected: test exists and passes
## Suggested Review Order

**Foundation - Tag Model**

- Defines TAGGABLE_SERVICES, AWS constraints (128 char key, 256 char value), reserved prefix list
  [`models.py:1`](../../control_plane/tagging/models.py#L1)

**Cross-Cutting - Observability**

- Structured AUDIT logging (WHO/WHAT/WHEN/BEFORE/AFTER) and OpenTelemetry tracing decorator
  [`observability.py:1`](../../control_plane/observability.py#L1)

**Control-Plane Tags - FalkorDB Only**

- Add tag: creates Tag node + TAGGED_WITH relationship with namespace="control_plane", includes AUDIT log
  [`control_plane.py:31`](../../control_plane/tagging/control_plane.py#L31)

- Query resources by tag: tenant-scoped lookup across all service types via TAGGED_WITH index
  [`control_plane.py:254`](../../control_plane/tagging/control_plane.py#L254)

- Remove tag: idempotent delete with AUDIT logging
  [`control_plane.py:143`](../../control_plane/tagging/control_plane.py#L143)

- Get all tags for resource: queries namespace="control_plane" relationships
  [`control_plane.py:204`](../../control_plane/tagging/control_plane.py#L204)

**Native Tags - Dual-Write FalkorDB + MiniStack**

- AWS validation: enforces 128 char key max, 256 char value max, blocks reserved prefixes for native tags
  [`native.py:71`](../../control_plane/tagging/native.py#L71)

- Add native tag: dual-write to FalkorDB + boto3, graceful boto3 failure handling (partial success)
  [`native.py:179`](../../control_plane/tagging/native.py#L179)

- Sync from MiniStack: polls boto3, skips invalid keys, logs warning, continues with remaining
  [`native.py:526`](../../control_plane/tagging/native.py#L526)

- Remove native tag: dual-delete from FalkorDB + boto3, returns partial success on boto3 failure
  [`native.py:357`](../../control_plane/tagging/native.py#L357)

- Get native tags: queries namespace="native" relationships
  [`native.py:502`](../../control_plane/tagging/native.py#L502)

- Extract resource type/name from ARN: parses S3/Lambda/DynamoDB ARNs for boto3 calls
  [`native.py:115`](../../control_plane/tagging/native.py#L115)

**Public API**

- Exports all public functions, constants, and enums
  [`__init__.py:1`](../../control_plane/tagging/__init__.py#L1)

**Tests - Control-Plane**

- 23 unit tests: add/remove/get, query with tenant filtering, AWS validation, idempotency
  [`test_tagging_control_plane.py:1`](../../tests/test_tagging_control_plane.py#L1)

**Tests - Native**

- 26 unit tests: AWS validation, reserved prefix blocking, boto3 failure handling, sync with invalid keys
  [`test_tagging_native.py:1`](../../tests/test_tagging_native.py#L1)

**Tests - Integration**

- 8 E2E tests: write-through verification, cross-service queries, drift detection
  [`test_tagging_e2e.py:1`](../../tests/integration/test_tagging_e2e.py#L1)
