# Implementation Plan: MSCL-8 - S3 Backend CRUD Operations

**Story:** MSCL-8  
**Epic:** Epic 2 - S3 Service Management  
**Started:** 2026-10-02  
**Developer:** dev_agent

## Alignment

- **Epic**: Epic 2 - S3 Service Management (first backend story of 3)
- **PRD requirement**: Section 5.1 "S3 Service Dashboard" — full CRUD management for S3 buckets
- **Architecture constraint**: AD-1 (REST API as Core Backend), AD-2 (FalkorDB for Resource Graph), AD-3 (Dual Tagging System), AD-5 (Python Backend with FastAPI)
- **ADRs in scope**: 
  - AD-1: All S3 logic goes in REST API layer (not MCP server)
  - AD-2: Bucket state persists to FalkorDB graph after creation in MiniStack
  - AD-3: Control-plane tags stored in FalkorDB, native AWS tags applied via boto3
  - AD-4: SSE events fired for RESOURCE_CREATED/UPDATED/DELETED
  - AD-5: Use FastAPI async patterns, boto3 for AWS SDK
- **Reuse decision**: 
  - Considered existing `control_plane.graph` module at `control_plane/graph/query.py` (patterns: create_node, delete_node, query_nodes) — will extend these patterns for S3 bucket nodes
  - Considered existing event bus at `control_plane/events/bus.py` (pattern: publish with event_type, resource, tenant_id) — will reuse for S3 events
  - No existing S3 service found — creating new service layer
- **Cross-layer contract**: 
  - New endpoints `/api/resources/s3/buckets` (GET/POST), `/api/resources/s3/buckets/{name}` (GET/DELETE), `/api/resources/s3/buckets/{name}/versioning` (PUT)
  - No UI callers yet (UI stories are MSCL-9, MSCL-10) — this story provides backend foundation
  - MiniStack API contract: boto3 S3 client at `localhost:4566` (standard AWS S3 API)
- **Confirmed consistent**: YES — approach matches AD-1 through AD-5, follows established patterns from MSCL-6 FastAPI foundation

## Task Breakdown

### Task 1: Create S3 Pydantic Models
**File:** `api/models/s3.py`
- [ ] `CreateBucketRequest` model (name, tenant_id, project, versioning)
- [ ] `BucketResponse` model (name, created_at, versioning, tags, tenant_id, arn)
- [ ] `BucketListResponse` model (buckets list, pagination)
- [ ] `UpdateVersioningRequest` model (enabled: bool)
- [ ] `DeleteBucketResponse` model (deleted: str, objects_deleted: int)
- [ ] Bucket name validation function (AWS S3 naming rules)

### Task 2: Create S3 Service Layer
**File:** `api/services/s3.py`
- [ ] `S3Service` class with tenant-scoped boto3 client
- [ ] `list_buckets()` — query MiniStack for all buckets, enrich with versioning/tags
- [ ] `create_bucket()` — create in MiniStack, add to FalkorDB, emit RESOURCE_CREATED event
- [ ] `get_bucket()` — retrieve bucket details (versioning, tagging, ACLs, object count)
- [ ] `delete_bucket()` — validate empty, delete from MiniStack + FalkorDB, emit RESOURCE_DELETED
- [ ] `delete_bucket_force()` — delete all objects first, then bucket
- [ ] `update_versioning()` — enable/disable versioning, update FalkorDB state, emit RESOURCE_UPDATED
- [ ] Error handling: bucket not found (404), already exists (409), not empty (400)
- [ ] Structured logging via `control_plane.observability`
- [ ] OpenTelemetry tracing for all operations

### Task 3: Create S3 API Routes
**File:** `api/routes/resources.py`
- [ ] Router setup with prefix `/api/resources/s3`
- [ ] `GET /buckets?tenant_id={id}` — list all buckets for tenant
- [ ] `POST /buckets` — create new bucket
- [ ] `GET /buckets/{name}?tenant_id={id}` — get bucket details
- [ ] `DELETE /buckets/{name}?tenant_id={id}&force=false` — delete bucket
- [ ] `PUT /buckets/{name}/versioning` — update versioning status
- [ ] Tenant context extraction from middleware
- [ ] Error responses with proper HTTP status codes
- [ ] OpenAPI/Swagger documentation

### Task 4: Integrate Routes into FastAPI App
**File:** `api/main.py`
- [ ] Import resources router
- [ ] Register router with prefix `/api` and tag `["resources"]`
- [ ] Verify startup logging shows S3 routes registered

### Task 5: Unit Tests
**File:** `tests/test_s3_service.py`
- [ ] Test bucket name validation (valid/invalid names)
- [ ] Test create_bucket with mocked boto3 client
- [ ] Test list_buckets pagination
- [ ] Test delete_bucket (empty bucket)
- [ ] Test delete_bucket_force (with objects)
- [ ] Test update_versioning
- [ ] Test error cases (bucket not found, already exists, not empty)

### Task 6: Integration Tests
**File:** `tests/test_api_s3.py`
- [ ] Test POST /buckets → bucket appears in MiniStack (verify with AWS CLI)
- [ ] Test GET /buckets → returns created bucket
- [ ] Test POST /buckets → bucket node exists in FalkorDB graph
- [ ] Test POST /buckets → RESOURCE_CREATED event fires via SSE
- [ ] Test PUT /versioning → versioning updated in MiniStack + FalkorDB
- [ ] Test DELETE /buckets → bucket removed from MiniStack + FalkorDB
- [ ] Test DELETE /buckets → RESOURCE_DELETED event fires
- [ ] Test DELETE with force → objects deleted first
- [ ] Test tenant isolation (tenant A cannot see tenant B buckets)

### Task 7: End-to-End Verification
**Per `.harness/decisions/2026-10-01-definition-of-done-end-to-end.md`:**
- [ ] Golden path: POST bucket → GET bucket → PUT versioning → DELETE bucket
- [ ] Verify each step persists to MiniStack (aws s3 ls)
- [ ] Verify each step persists to FalkorDB graph
- [ ] Verify SSE events fire for each mutation
- [ ] Cross-layer contract: API endpoint shapes match what UI will expect (see MSCL-9 story)

## Implementation Notes

**Boto3 Client Pattern:**
- Create client per tenant using 12-digit access key as `aws_access_key_id`
- Use `endpoint_url='http://localhost:4566'` to connect to MiniStack
- Client initialization in `S3Service.__init__()` per tenant

**Dual-Write Pattern:**
1. Create resource in MiniStack via boto3
2. Add resource node to FalkorDB via `control_plane.graph.create_node`
3. Emit SSE event via `control_plane.events.event_bus.publish`
4. Return response to API caller

**FalkorDB Resource Schema:**
```python
{
    'id': f"s3-bucket-{name}",
    'type': 's3:bucket',
    'name': name,
    'tenant_id': tenant_id,
    'project': project,  # Control-plane tag
    'arn': f"arn:aws:s3:::{name}",
    'state': {
        'versioning': 'Enabled' | 'Disabled',
        'region': 'us-east-1',
        'object_count': 0,  # Optional
        'size_bytes': 0     # Optional
    },
    'created_at': datetime.utcnow().isoformat(),
    'updated_at': datetime.utcnow().isoformat()
}
```

**S3 Bucket Naming Rules (Validation):**
- 3-63 characters long
- Lowercase alphanumeric and hyphens only
- Must start and end with alphanumeric
- No consecutive periods
- Not formatted as IP address (e.g., 192.168.1.1)
- No uppercase or underscores

## Testing Strategy

**Unit Tests (fast):**
- Mock boto3 client responses
- Test validation logic in isolation
- Test error handling paths

**Integration Tests (MiniStack required):**
- Start MiniStack and FalkorDB via docker-compose
- Real boto3 calls to localhost:4566
- Verify dual-write to MiniStack + FalkorDB
- Verify SSE events fire

**End-to-End Tests:**
- Golden path: create → read → update → delete
- Verify with AWS CLI: `aws --endpoint-url=http://localhost:4566 s3 ls`
- Verify graph state via graph API: `GET /api/graph/resources?type=s3:bucket`

## Definition of Done

Per `testing.md` and `alignment.md`:

✅ **All Acceptance Criteria met:**
- AC1: List buckets with pagination ✅
- AC2: Create bucket → MiniStack + FalkorDB + event ✅
- AC3: Get bucket details ✅
- AC4: Delete empty bucket ✅
- AC5: Force delete bucket with objects ✅
- AC6: Update versioning ✅
- AC7: Invalid bucket name validation ✅

✅ **End-to-end verification:**
- Bucket created in MiniStack (verifiable via AWS CLI)
- Bucket node in FalkorDB graph
- SSE events fire for mutations
- API retrieves bucket successfully
- Delete cleans up MiniStack + graph + fires event

✅ **Code quality:**
- Lint passes (ruff check)
- Type-check passes (mypy)
- Unit tests pass
- Integration tests pass
- Structured logging with OPERATIONAL/SECURITY/AUDIT types
- OpenTelemetry traces for all operations
- No hardcoded secrets
- No stubs or TODOs

✅ **Cross-layer contract:**
- API endpoint shapes match story specification
- UI stories (MSCL-9, MSCL-10) can consume these endpoints without changes

✅ **Wiring proof:**
- All new exports have verified call sites (routes → service → graph/event_bus)

✅ **Observability:**
- Structured logs with tenant_id, bucket_name, operation
- OpenTelemetry spans for create/delete/update operations
- Logs linked to traces via trace_id/span_id
