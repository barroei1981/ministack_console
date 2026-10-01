# Story MSCL-6: FastAPI REST API Foundation

**Epic:** Epic 1 - Control-Plane Foundation  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-1, MSCL-2, MSCL-3

## User Story

As a **developer**,  
I want **a FastAPI-based REST API with core endpoints for resources, tenants, and projects**,  
So that **both the Web UI and MCP Server can access the control-plane data**.

## Acceptance Criteria

**Given** the control-plane API is running on port 3001  
**When** I send GET `/api/health`  
**Then** I receive a 200 OK response with system status  
**And** the response includes FalkorDB connection status and MiniStack connection status

**Given** I query GET `/api/tenants`  
**When** the request is processed  
**Then** I receive a list of all tenants with their IDs, names, and resource counts  
**And** the response is JSON formatted per API spec

**Given** I query GET `/api/tenants/{tenant_id}/resources`  
**When** the request is processed with a valid tenant_id  
**Then** I receive all resources for that tenant  
**And** resources include: id, type, name, tenant_id, project, tags, created_at, state  
**And** pagination is supported (100 items per page)

**Given** I query GET `/api/tenants/{tenant_id}/projects`  
**When** the request is processed  
**Then** I receive all projects for that tenant  
**And** each project includes resource counts by service type

**Given** I query GET `/api/projects/{project_name}/resources` with `tenant_id` query param  
**When** the request is processed  
**Then** I receive all resources in that project  
**And** resources are tenant-scoped (no cross-tenant leakage)

**Given** I query GET `/api/graph/dependencies?resource_id={id}`  
**When** the request is processed  
**Then** I receive all resources that the specified resource depends on  
**And** dependency types are included (environment_variable, event_source, etc.)

**Given** I query GET `/api/graph/dependents?resource_id={id}`  
**When** the request is processed  
**Then** I receive all resources that depend on the specified resource  
**And** the response warns if any dependents exist (for delete operations)

**Given** I send an invalid request (missing tenant_id, malformed data)  
**When** the API processes the request  
**Then** I receive a 400 Bad Request with a clear error message  
**And** the error message is actionable (tells me what's missing/wrong)

**Given** the API receives 1000 requests per minute  
**When** rate limiting is enforced  
**Then** requests within the limit succeed  
**And** requests exceeding the limit receive 429 Too Many Requests  
**And** rate limits are per tenant (1000 reads/min, enforced in later story for writes)

## Technical Notes

**Implementation Files:**
- `api/main.py` - FastAPI app initialization, middleware, CORS
- `api/routes/resources.py` - Resource endpoints
- `api/routes/tenants.py` - Tenant endpoints
- `api/routes/projects.py` - Project endpoints
- `api/routes/graph.py` - Graph query endpoints
- `api/middleware/auth.py` - API key authentication (Phase 1: simple, Phase 2: MCP keys)
- `api/middleware/rate_limit.py` - Rate limiting
- `api/middleware/tenant_context.py` - Tenant isolation middleware
- `api/models/` - Pydantic models for request/response

**API Specification:**

**GET /api/health**
```json
{
  "status": "healthy",
  "ministack": {"connected": true, "endpoint": "http://localhost:4566"},
  "falkordb": {"connected": true, "nodes": 1234}
}
```

**GET /api/tenants**
```json
{
  "tenants": [
    {"id": "123456789012", "name": "123456789012", "resource_count": 42, "created_at": "2026-10-01T12:00:00Z"}
  ]
}
```

**GET /api/tenants/{tenant_id}/resources?page=1&limit=100**
```json
{
  "resources": [
    {
      "id": "s3-bucket-my-bucket",
      "type": "s3:bucket",
      "name": "my-bucket",
      "tenant_id": "123456789012",
      "project": "microservice-a",
      "tags": {
        "control_plane": {"environment": "dev"},
        "native": {"Name": "my-bucket"}
      },
      "created_at": "2026-10-01T12:00:00Z",
      "state": {"versioning": "Enabled", "region": "us-east-1"}
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 100,
    "total": 42,
    "next": "/api/tenants/123456789012/resources?page=2"
  }
}
```

**Middleware Stack:**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MiniStack Console API", version="1.0.0")

# CORS (allow Web UI on port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tenant isolation
app.middleware("http")(enforce_tenant_isolation)

# Rate limiting
app.middleware("http")(rate_limit_middleware)
```

**Testing:**
- Unit tests: Each endpoint, Pydantic model validation, middleware
- Integration tests: Full request/response cycle with FalkorDB
- Performance tests: 1000 requests/min, response time <500ms

**NFRs Addressed:**
- NFR-1 (Performance): API response <500ms for resource lists
- NFR-2 (Scalability): Support 100 concurrent connections
- FR-3: Multi-Tenant Support via API

**Architecture Decisions:**
- AD-1: REST API as Core Backend
- AD-5: Python Backend with FastAPI
- AD-6: Multi-Tenant Isolation by Access Key
