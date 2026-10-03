---
title: 'MSCL-8: S3 Backend CRUD Operations'
type: 'feature'
created: '2026-10-02'
status: 'in-review'
review_loop_iteration: 0
baseline_commit: '4a8656f3e9cee99ac5b5b3a5f9407b8a7effe767'
context:
  - '_lch-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Developers cannot manage S3 buckets through the MiniStack Console. The Web UI (MSCL-9) and MCP Server (Epic 5) both require backend API endpoints for S3 bucket operations, but no S3 service layer or REST endpoints exist yet. Without backend CRUD operations, users must fall back to AWS CLI commands to manage buckets, defeating the purpose of the control-plane.

**Approach:** Build the backend foundation for S3 management: create Pydantic request/response models (`api/models/s3.py`), implement an S3 service layer using boto3 to MiniStack (`api/services/s3.py`), and expose REST API endpoints (`api/routes/resources.py`) for bucket CRUD operations (list, create, get, delete, update versioning). Dual-write to MiniStack and FalkorDB, emit SSE events for UI updates, enforce tenant isolation, validate S3 bucket naming rules, and follow patterns from MSCL-6 FastAPI foundation.

## Boundaries & Constraints

**Always:**
- Use boto3 S3 client with `endpoint_url='http://localhost:4566'` to connect to MiniStack
- Create client per tenant using 12-digit access key as `aws_access_key_id`
- Dual-write pattern: Create/update/delete in MiniStack first, then FalkorDB, then emit SSE event
- Validate S3 bucket names (3-63 chars, lowercase alphanumeric + hyphens, no consecutive periods, not IP-formatted)
- Tenant isolation: All operations filter by tenant_id from middleware context
- Use async/await patterns for all I/O operations
- Structured logging via `control_plane.observability` (OPERATIONAL/SECURITY/AUDIT types)
- OpenTelemetry traces for all CRUD operations
- Follow patterns from `api/routes/tenants.py` for route structure
- Follow patterns from `control_plane/graph/query.py` for FalkorDB operations
- Use `control_plane.events.event_bus` singleton for SSE events
- Force-delete must delete all objects before deleting bucket

**Ask First:**
- Object-level operations (upload, download, metadata edit) - these are deferred to MSCL-10
- Pre-signed URL generation - deferred to MSCL-10
- Bucket policies and ACLs beyond basic creation - deferred to MSCL-10
- Pagination strategy for >1000 buckets - current spec assumes ≤1000 buckets per tenant

**Never:**
- Implement object-level operations in this story (MSCL-10 handles objects)
- Skip validation on bucket names (AWS will reject, but we should fail fast with clear errors)
- Allow cross-tenant bucket access (security violation)
- Create routes before MSCL-6 FastAPI app exists (blocking dependency satisfied)
- Use WebSockets instead of SSE for events (AD-4 mandates SSE)
- Store bucket state only in MiniStack without FalkorDB (AD-2 requires graph)
- Implement MCP tools directly (MCP Server in Epic 5 translates to these REST endpoints)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| List buckets | `GET /api/resources/s3/buckets?tenant_id=123456789012` | Returns JSON array of buckets with `[{name, created_at, versioning, tags, tenant_id, arn}]`, HTTP 200 | Boto3 error → HTTP 500, log OPERATIONAL error |
| Create bucket (valid name) | `POST /api/resources/s3/buckets` with `{name: "my-bucket", tenant_id: "123456789012", project: "myproject", versioning: false}` | Bucket created in MiniStack, Resource node in FalkorDB (id: "s3-bucket-my-bucket", type: "s3:bucket"), RESOURCE_CREATED event emitted, HTTP 201 with bucket details | Boto3 BucketAlreadyExists → HTTP 409, log SECURITY event (potential collision) |
| Create bucket (invalid name) | `POST /api/resources/s3/buckets` with `{name: "My-Bucket"}` (uppercase) | HTTP 400 with error: "Invalid bucket name: must be lowercase alphanumeric with hyphens, 3-63 chars" | Validation fails before boto3 call |
| Get bucket | `GET /api/resources/s3/buckets/my-bucket?tenant_id=123456789012` | Returns bucket details: `{name, created_at, versioning, tags, arn, state: {region, object_count, size_bytes}}`, HTTP 200 | Boto3 NoSuchBucket → HTTP 404 |
| Delete bucket (empty) | `DELETE /api/resources/s3/buckets/my-bucket?tenant_id=123456789012&force=false` | Bucket deleted from MiniStack, Resource node deleted from FalkorDB (DETACH DELETE), RESOURCE_DELETED event emitted, HTTP 200 | Bucket not empty → HTTP 400 with error: "Bucket not empty. Use force=true" |
| Delete bucket (force, with objects) | `DELETE /api/resources/s3/buckets/my-bucket?tenant_id=123456789012&force=true` | All objects deleted first (iterate via `list_objects_v2`, `delete_object`), then bucket deleted, HTTP 200 with `{deleted: "my-bucket", objects_deleted: 5}` | Boto3 error during object deletion → HTTP 500, log OPERATIONAL error with object key |
| Update versioning | `PUT /api/resources/s3/buckets/my-bucket/versioning` with `{enabled: true, tenant_id: "123456789012"}` | Versioning enabled via `put_bucket_versioning`, FalkorDB state updated (`state.versioning: "Enabled"`), RESOURCE_UPDATED event emitted, HTTP 200 | Boto3 NoSuchBucket → HTTP 404 |
| Cross-tenant access attempt | `GET /api/resources/s3/buckets/other-tenant-bucket?tenant_id=123456789012` (bucket owned by different tenant) | HTTP 404 (bucket not found for this tenant - do not leak existence) | N/A |

</frozen-after-approval>

## Code Map

**Reuse from MSCL-6 (FastAPI Foundation):**
- `api/main.py` -- FastAPI app instance, middleware setup, router registration
- `api/routes/tenants.py:14-32` -- Route pattern with Query params for tenant_id
- `api/routes/__init__.py` -- Router exports (add resources router)
- `api/middleware/tenant_context.py` -- TenantContextMiddleware (extracts tenant_id)
- `api/models.py:26-33` -- Pydantic model patterns (TenantResponse, ResourceSummary)

**Reuse from MSCL-1 (FalkorDB Schema):**
- `control_plane/graph/query.py:130-182` -- `create_node(label, properties)` for Resource nodes
- `control_plane/graph/query.py:518-558` -- `delete_node(label, node_id)` for cleanup
- `control_plane/graph/query.py:262-333` -- `query_nodes(label, filters, limit)` for listing

**Reuse from MSCL-7 (SSE Events):**
- `control_plane/events/__init__.py` -- `event_bus` singleton export
- `control_plane/events/bus.py:86-126` -- `EventBus.publish(event_type, resource, tenant_id)` for RESOURCE_CREATED/UPDATED/DELETED

**Reuse from MSCL-4 (Observability):**
- `control_plane/observability.py:1-70` -- `log_operational()`, `log_security()`, `trace_operation()` decorator

**New modules to create:**
- `api/models/s3.py` -- Pydantic models: CreateBucketRequest, BucketResponse, BucketListResponse, UpdateVersioningRequest, DeleteBucketResponse
- `api/services/s3.py` -- S3Service class with boto3 operations
- `api/routes/resources.py` -- REST endpoints for S3 resources

**Integration points:**
- `api/main.py:109` -- Add `app.include_router(resources.router, prefix="/api", tags=["resources"])`

## Tasks & Acceptance

**Execution:**
- [x] `api/models/s3.py` -- Create Pydantic models for S3 requests/responses with bucket name validation function
- [x] `api/services/s3.py` -- Implement S3Service class with tenant-scoped boto3 client, list/create/get/delete/update operations, dual-write to FalkorDB, SSE event emission, structured logging, OpenTelemetry tracing
- [x] `api/routes/resources.py` -- Create REST endpoints (GET/POST/DELETE /buckets, PUT /buckets/{name}/versioning) with tenant isolation via middleware
- [x] `api/main.py` -- Register resources router
- [x] `tests/test_s3_service.py` -- Unit tests for S3Service: bucket name validation, mocked boto3 operations, error handling
- [x] `tests/test_api_s3.py` -- Integration tests: full CRUD cycle (create → list → get → update versioning → delete), force delete with objects, tenant isolation, verify FalkorDB state, verify SSE events fired

**Acceptance Criteria:**
- Given I send `GET /api/resources/s3/buckets?tenant_id=123456789012`, when the request is processed, then I receive all S3 buckets for that tenant with pagination metadata
- Given I send `POST /api/resources/s3/buckets` with valid bucket config, when processed, then bucket is created in MiniStack (verifiable via `aws s3 ls --endpoint-url=http://localhost:4566`), bucket node exists in FalkorDB graph (query via `/api/graph/resources?type=s3:bucket`), RESOURCE_CREATED SSE event is emitted, and I receive HTTP 201 with bucket details
- Given I send `GET /api/resources/s3/buckets/my-bucket?tenant_id=123456789012`, when processed, then I receive full bucket details including versioning status, tags, and ARN
- Given I send `DELETE /api/resources/s3/buckets/my-bucket?tenant_id=123456789012` for an empty bucket, when processed, then bucket is deleted from MiniStack, bucket node removed from FalkorDB, RESOURCE_DELETED event emitted, and I receive HTTP 200
- Given I send `DELETE /api/resources/s3/buckets/my-bucket?tenant_id=123456789012&force=true` for a bucket with objects, when processed, then all objects are deleted first, then bucket is deleted, and I receive HTTP 200 with deletion summary
- Given I send `PUT /api/resources/s3/buckets/my-bucket/versioning` with `{enabled: true}`, when processed, then versioning is enabled in MiniStack, bucket state updated in FalkorDB, RESOURCE_UPDATED event emitted, and I receive HTTP 200
- Given I send an invalid bucket name (uppercase, special chars, <3 or >63 chars), when validated, then I receive HTTP 400 with clear error explaining S3 naming rules
- Given Tenant A creates a bucket, when Tenant B queries buckets, then Tenant B does not see Tenant A's bucket (tenant isolation enforced)

## Spec Change Log

## Design Notes

**Boto3 Client Pattern:**
```python
class S3Service:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.client = self._create_client()
    
    def _create_client(self):
        session = boto3.Session(
            aws_access_key_id=self.tenant_id,  # 12-digit tenant ID
            aws_secret_access_key='dummy',      # MiniStack ignores secret
            region_name='us-east-1'
        )
        return session.client('s3', endpoint_url='http://localhost:4566')
```

**Dual-Write Pattern:**
```python
async def create_bucket(self, name: str, project: str = None, versioning: bool = False):
    # 1. Create in MiniStack
    self.client.create_bucket(Bucket=name)
    
    # 2. Enable versioning if requested
    if versioning:
        self.client.put_bucket_versioning(
            Bucket=name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
    
    # 3. Add to FalkorDB
    resource = {
        'id': f"s3-bucket-{name}",
        'type': 's3:bucket',
        'name': name,
        'tenant_id': self.tenant_id,
        'project': project,
        'arn': f"arn:aws:s3:::{name}",
        'state': {'versioning': 'Enabled' if versioning else 'Disabled'},
        'created_at': datetime.utcnow().isoformat()
    }
    await create_node('Resource', resource)
    
    # 4. Emit SSE event
    await event_bus.publish("RESOURCE_CREATED", resource, self.tenant_id)
    
    return resource
```

**FalkorDB Resource Schema:**
```python
{
    'id': 'sa-bucket-my-bucket',           # Unique node ID
    'type': 's3:bucket',                    # Resource type
    'name': 'my-bucket',                    # Bucket name
    'tenant_id': '123456789012',            # Owner tenant
    'project': 'myproject',                 # Control-plane tag
    'arn': 'arn:aws:s3:::my-bucket',        # AWS ARN format
    'state': {
        'versioning': 'Enabled',            # Versioning status
        'region': 'us-east-1',              # AWS region
        'object_count': 0,                  # Optional (not populated in MSCL-8)
        'size_bytes': 0                     # Optional (not populated in MSCL-8)
    },
    'created_at': '2026-10-02T12:34:56Z',
    'updated_at': '2026-10-02T12:34:56Z'
}
```

**S3 Bucket Naming Validation:**
```python
def validate_bucket_name(name: str) -> None:
    if not (3 <= len(name) <= 63):
        raise ValueError("Bucket name must be 3-63 characters")
    if not name.islower():
        raise ValueError("Bucket name must be lowercase")
    if not all(c.isalnum() or c in ['-', '.'] for c in name):
        raise ValueError("Bucket name must contain only lowercase alphanumeric, hyphens, and periods")
    if name.startswith('-') or name.endswith('-'):
        raise ValueError("Bucket name cannot start or end with hyphen")
    if '..' in name:
        raise ValueError("Bucket name cannot contain consecutive periods")
    # Check if IP address format
    if name.replace('.', '').isdigit() and name.count('.') == 3:
        raise ValueError("Bucket name cannot be formatted as IP address")
```

## Verification

**Commands:**
- `ruff check api/models/s3.py api/services/s3.py api/routes/resources.py` -- expected: no lint errors
- `mypy api/models/s3.py api/services/s3.py api/routes/resources.py` -- expected: no type errors
- `pytest tests/test_s3_service.py -v` -- expected: all unit tests pass
- `pytest tests/test_api_s3.py -v` -- expected: all integration tests pass (requires docker-compose up: MiniStack + FalkorDB)
- `aws --endpoint-url=http://localhost:4566 s3 mb s3://test-bucket` -- create bucket via CLI, then `curl http://localhost:3001/api/resources/s3/buckets?tenant_id=123456789012` should include test-bucket (end-to-end verification)

**Manual checks:**
1. Start MiniStack and FalkorDB: `docker-compose up -d`
2. Start FastAPI server: `uvicorn api.main:app --reload`
3. Create bucket via API: `curl -X POST http://localhost:3001/api/resources/s3/buckets -H "Content-Type: application/json" -d '{"name": "my-bucket", "tenant_id": "123456789012", "project": "test", "versioning": false}'`
4. Verify bucket in MiniStack: `aws --endpoint-url=http://localhost:4566 s3 ls` (should show my-bucket)
5. Verify bucket in FalkorDB: `curl http://localhost:3001/api/graph/resources?type=s3:bucket` (should include s3-bucket-my-bucket node)
6. Connect to SSE stream: `curl -N http://localhost:3001/api/sse?tenant_id=123456789012` in separate terminal
7. Create another bucket via API, verify SSE event fires with RESOURCE_CREATED type
8. Delete bucket via API: `curl -X DELETE http://localhost:3001/api/resources/s3/buckets/my-bucket?tenant_id=123456789012`
9. Verify bucket removed from MiniStack and FalkorDB
