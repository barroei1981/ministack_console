---
title: 'MSCL-6: FastAPI REST API Foundation'
type: 'feature'
created: '2026-10-02'
status: 'in-progress'
review_loop_iteration: 0
baseline_commit: 'a8a96764b4fad262e1c0aae5f5bc64a88c877738'
context:
  - '_lch-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Web UI and MCP Server need a unified API layer to access control-plane data (resources, tenants, projects, dependencies). Currently, FalkorDB operations are scattered across modules with no HTTP interface, making external access impossible.

**Approach:** Build a FastAPI REST API with endpoints for tenants, resources, projects, and graph queries. Add health checks for FalkorDB and MiniStack connections, implement tenant isolation middleware, and provide pagination for large result sets. This becomes the single HTTP gateway for all control-plane reads.

## Boundaries & Constraints

**Always:**
- Reuse existing `control_plane/graph/query.py` functions (query_nodes, query_relationships) — no duplicate Cypher queries
- Reuse existing `control_plane/ministack_client.py` health_check method
- Use FastAPI with Pydantic v2 models for request/response validation
- Implement tenant isolation via middleware — every request must have valid tenant_id context
- Support pagination (default 100 items/page, max 500) for list endpoints
- Follow observability.md: OPERATIONAL logs for API requests, structured logging
- Add CORS middleware for Web UI at localhost:3000
- API runs on port 3001 (configurable via API_PORT env var)
- Response times <500ms per NFR-1 (resource lists under 1000 items)

**Ask First:**
- Authentication mechanism beyond tenant_id (API keys, JWT tokens) — defer to MSCL-8
- Write operations (POST/PUT/DELETE) — defer to later stories (MSCL-9+)
- Rate limiting thresholds beyond 1000 req/min per tenant
- WebSocket/SSE endpoints (covered by MSCL-7)
- GraphQL alternative to REST

**Never:**
- Create new FalkorDB query functions — reuse control_plane/graph/query.py
- Inline Cypher queries in API route handlers
- Bypass tenant isolation checks (every response must filter by tenant_id)
- Return full resource state in lists (use summary fields only)
- Implement write endpoints (MSCL-6 is read-only)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Health check - both healthy | GET /api/health | 200 OK with falkordb.connected=true, ministack.connected=true | N/A |
| Health check - FalkorDB down | FalkorDB connection fails | 503 with falkordb.connected=false | Return partial health status, don't fail entire endpoint |
| List tenants | GET /api/tenants | 200 with tenant list, each with resource_count | Empty list [] if no tenants exist |
| List resources - valid tenant | GET /api/tenants/{id}/resources?page=1&limit=100 | 200 with resources array + pagination metadata | Empty resources [] if tenant has no resources |
| List resources - invalid tenant | GET /api/tenants/999999999999/resources | 404 Not Found with error message | Clear error: "Tenant 999999999999 not found" |
| List resources - page beyond end | GET .../resources?page=999 | 200 with empty resources[], pagination shows total | Empty array, not 404 |
| Query dependencies - valid resource | GET /api/graph/dependencies?resource_id=s3-bucket-x | 200 with list of DEPENDS_ON relationships | Empty array [] if no dependencies |
| Query dependencies - missing resource_id | GET /api/graph/dependencies | 400 Bad Request with validation error | FastAPI validation: "resource_id query param required" |
| Large result set | GET .../resources with 5000 resources | Paginated responses, max 500 per page | Enforce limit <= 500, ignore higher values |
| Malformed pagination params | GET .../resources?page=-1&limit=abc | 422 Unprocessable Entity | Pydantic validation error with field details |

</frozen-after-approval>

## Code Map

**Reuse from MSCL-1 (FalkorDB Schema + Graph Operations):**
- `control_plane/graph/query.py:262-333` -- `query_nodes()` for fetching tenants, projects, resources
- `control_plane/graph/query.py:335-398` -- `query_relationships()` for dependency queries
- `control_plane/graph/query.py:112-128` -- `health_check()` for FalkorDB status

**Reuse from MSCL-2 (MiniStack Client):**
- `control_plane/ministack_client.py:103-137` -- `health_check()` for MiniStack connection status

**Reuse from MSCL-4 (Observability):**
- `control_plane/observability.py` -- structured logging patterns (though need to add log_operational)

**New modules to create:**
- `api/__init__.py` -- Package init
- `api/main.py` -- FastAPI app setup, middleware, CORS
- `api/models.py` -- Pydantic models (HealthResponse, TenantResponse, ResourceResponse, etc.)
- `api/routes/health.py` -- Health check endpoint
- `api/routes/tenants.py` -- Tenant list + tenant resources endpoints
- `api/routes/projects.py` -- Project resources endpoint
- `api/routes/graph.py` -- Dependency query endpoints
- `api/middleware/tenant_context.py` -- Tenant isolation middleware
- `api/middleware/rate_limit.py` -- Rate limiting (simple in-memory for Phase 1)

**Test structure:**
- `tests/test_api_health.py` -- Health endpoint tests
- `tests/test_api_tenants.py` -- Tenant endpoint tests
- `tests/test_api_resources.py` -- Resource list tests with pagination
- `tests/test_api_graph.py` -- Graph dependency query tests
- `tests/integration/test_api_e2e.py` -- Full request/response cycle

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- Add fastapi>=0.104.0, uvicorn>=0.24.0 to dependencies
- [x] `api/__init__.py` -- Create package, export main app
- [x] `api/models.py` -- Define Pydantic models: HealthResponse (status, ministack dict, falkordb dict), TenantResponse (id, name, resource_count, created_at), ResourceSummary (id, type, name, tenant_id, project, tags, created_at, state subset), PaginatedResourceResponse (resources list, pagination dict), DependencyResponse (from_node_id, to_node_id, type, metadata)
- [x] `api/main.py` -- Create FastAPI app with title/version, add CORS middleware (allow localhost:3000), add tenant_context middleware, add rate_limit middleware
- [x] `api/routes/health.py` -- Implement GET /api/health: call graph.health_check() + ministack_client.health_check(), return 200 if both OK else 503
- [x] `api/routes/tenants.py` -- Implement GET /api/tenants: query_nodes("Tenant"), count resources per tenant via query, return list
- [x] `api/routes/tenants.py` -- Implement GET /api/tenants/{tenant_id}/resources?page=1&limit=100: validate tenant exists, query_nodes("Resource", filters={"tenant_id"}), paginate results, return ResourceSummary list + pagination metadata
- [x] `api/routes/projects.py` -- Implement GET /api/tenants/{tenant_id}/projects: query_nodes("Project", filters={"tenant_id"}), group resources by project, return project list with resource counts
- [x] `api/routes/projects.py` -- Implement GET /api/projects/{project_name}/resources?tenant_id={id}: validate tenant_id provided, query_nodes("Resource", filters={"tenant_id", "project"}), return resources
- [x] `api/routes/graph.py` -- Implement GET /api/graph/dependencies?resource_id={id}: call query_relationships(resource_id, "Resource", "DEPENDS_ON"), return dependency list
- [x] `api/routes/graph.py` -- Implement GET /api/graph/dependents?resource_id={id}: query reverse DEPENDS_ON relationships (match pattern (a)-[:DEPENDS_ON]->(b) where b.id = resource_id), return dependents
- [x] `api/middleware/tenant_context.py` -- Extract tenant_id from query param or header, validate format (12 digits), store in request.state.tenant_id
- [x] `api/middleware/rate_limit.py` -- Simple in-memory rate limiter: track requests per tenant per minute, enforce 1000 req/min limit, return 429 if exceeded
- [x] `control_plane/observability.py` -- Add log_operational() helper function for OPERATIONAL logs (consistency with log_audit)
- [x] `tests/test_api_health.py` -- Unit tests: health check with both services up, FalkorDB down, MiniStack down
- [x] `tests/test_api_tenants.py` -- Unit tests: list tenants (empty, multiple), list tenant resources (valid tenant, invalid tenant, pagination)
- [x] `tests/test_api_graph.py` -- Unit tests: query dependencies (found, not found, missing resource_id param)
- [x] `tests/integration/test_api_e2e.py` -- Integration test: start API server, create resources in FalkorDB, query via API, verify response format + pagination

**Acceptance Criteria:**
- Given the API is running, when I GET /api/health, then I receive 200 OK with FalkorDB connection status and MiniStack connection status
- Given 3 tenants exist in FalkorDB, when I GET /api/tenants, then I receive a list of 3 tenants with their resource counts
- Given tenant "123456789012" has 150 resources, when I GET /api/tenants/123456789012/resources?page=1&limit=100, then I receive 100 resources and pagination shows total=150, next=/api/tenants/123456789012/resources?page=2
- Given tenant "123456789012" has project "microservice-a" with 5 resources, when I GET /api/tenants/123456789012/projects, then the response includes "microservice-a" with resource_count=5
- Given a Lambda resource depends on an S3 bucket, when I GET /api/graph/dependencies?resource_id={lambda_id}, then I receive the S3 bucket in the dependencies list with type="environment_variable"
- Given an S3 bucket has 3 dependent Lambdas, when I GET /api/graph/dependents?resource_id={bucket_id}, then I receive all 3 Lambdas in the response
- Given I query /api/tenants without providing tenant_id in request context, when tenant isolation middleware processes the request, then I receive 400 Bad Request
- Given I send 1001 requests in one minute to tenant "123456789012" endpoints, when rate limiting is enforced, then the 1001st request receives 429 Too Many Requests

## Spec Change Log

## Design Notes

**Middleware Stack Order (outer to inner):**
```python
app = FastAPI(title="MiniStack Console API", version="1.0.0")

# 1. CORS (outermost - must see all responses)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], ...)

# 2. Tenant context extraction
@app.middleware("http")
async def tenant_context_middleware(request, call_next):
    # Extract tenant_id from query/header, validate, store in request.state
    ...

# 3. Rate limiting (uses request.state.tenant_id)
@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # Check rate limit for request.state.tenant_id
    ...

# 4. Routes (innermost)
app.include_router(health.router, prefix="/api")
app.include_router(tenants.router, prefix="/api")
```

**Pagination Response Format:**
```json
{
  "resources": [...],
  "pagination": {
    "page": 1,
    "limit": 100,
    "total": 250,
    "next": "/api/tenants/123456789012/resources?page=2&limit=100",
    "prev": null
  }
}
```

**Tenant Isolation Pattern:**
All resource queries MUST filter by tenant_id from request context:
```python
tenant_id = request.state.tenant_id  # validated by middleware
resources = query_nodes("Resource", filters={"tenant_id": tenant_id})
```

Never trust tenant_id from URL path alone — always validate via middleware.

## Verification

**Commands:**
- `pytest tests/test_api_health.py -v` -- expected: all health endpoint tests pass
- `pytest tests/test_api_tenants.py -v` -- expected: all tenant/resource list tests pass
- `pytest tests/test_api_graph.py -v` -- expected: all graph query tests pass
- `pytest tests/integration/test_api_e2e.py -v` -- expected: end-to-end API tests pass
- `mypy api/` -- expected: no type errors
- `ruff check api/` -- expected: no lint errors
- `uvicorn api.main:app --port 3001` then `curl http://localhost:3001/api/health` -- expected: 200 OK with health status

**Manual checks:**
- Start API server, create test resources in FalkorDB, query via curl/httpie, verify response format matches spec
- Send >1000 requests to same tenant, verify 429 response on excess
- Query with invalid tenant_id, verify 400/404 responses with clear error messages
