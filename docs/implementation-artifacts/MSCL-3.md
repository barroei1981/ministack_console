# Story MSCL-3: Multi-Tenant Isolation and Tenant Management

**Epic:** Epic 1 - Control-Plane Foundation  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-1, MSCL-2

## User Story

As a **developer working with multiple MiniStack tenants**,  
I want **strict isolation between tenants with automatic tenant detection**,  
So that **resources from different tenants never mix and I can switch contexts safely**.

## Acceptance Criteria

**Given** multiple MiniStack tenants exist (different 12-digit access keys)  
**When** resources are polled from MiniStack  
**Then** each resource is tagged with its tenant_id (extracted from access key)  
**And** resources are stored in FalkorDB with tenant_id property  
**And** Tenant nodes are created automatically if they don't exist

**Given** I query resources via the API with a specific tenant_id  
**When** the query executes  
**Then** only resources belonging to that tenant are returned  
**And** resources from other tenants are never included  
**And** cross-tenant queries are explicitly blocked

**Given** I create a Project in a specific tenant  
**When** the Project is saved to FalkorDB  
**Then** a (Tenant)-[:OWNS]->(Project) relationship is created  
**And** the project's tenant_id matches the tenant  
**And** queries for that tenant's projects return the new project

**Given** I switch between tenants in the UI  
**When** I select a different tenant from the dropdown  
**Then** all subsequent API calls are scoped to the new tenant  
**And** the UI refreshes to show only that tenant's resources  
**And** no resources from the previous tenant are visible

**Given** a tenant has 10,000 resources  
**When** I query that tenant's resources  
**Then** the query completes in <500ms  
**And** uses the tenant_id index for efficient lookup

## Technical Notes

**Implementation Files:**
- `control_plane/tenants/isolation.py` - Tenant boundary enforcement
- `control_plane/tenants/switcher.py` - Tenant context management
- `api/middleware/tenant_context.py` - Middleware for tenant scoping
- `control_plane/graph/query.py` - Tenant-aware graph queries

**Tenant Detection:**
```python
def extract_tenant_id(aws_access_key: str) -> str:
    """Extract 12-digit tenant ID from MiniStack access key"""
    # MiniStack access key IS the tenant ID (12 digits)
    if len(aws_access_key) == 12 and aws_access_key.isdigit():
        return aws_access_key
    else:
        raise ValueError(f"Invalid MiniStack access key: {aws_access_key}")
```

**Tenant Node Creation:**
```cypher
MERGE (t:Tenant {id: $tenant_id})
ON CREATE SET t.name = $tenant_id, t.created_at = timestamp()
RETURN t
```

**Tenant-Scoped Queries:**
```cypher
// Get all resources for a tenant
MATCH (r:Resource {tenant_id: $tenant_id})
RETURN r

// Get all projects for a tenant
MATCH (t:Tenant {id: $tenant_id})-[:OWNS]->(p:Project)
RETURN p

// Get resources in a tenant's project
MATCH (t:Tenant {id: $tenant_id})-[:OWNS]->(p:Project {name: $project_name})-[:CONTAINS]->(r:Resource)
RETURN r
```

**API Middleware:**
```python
@app.middleware("http")
async def enforce_tenant_isolation(request: Request, call_next):
    """Ensure all queries are tenant-scoped"""
    tenant_id = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id")
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant_id")
    
    # Attach tenant_id to request state
    request.state.tenant_id = tenant_id
    
    response = await call_next(request)
    return response
```

**Testing:**
- Unit tests: Tenant extraction, tenant node creation, isolation enforcement
- Integration tests: Multi-tenant queries, cross-tenant isolation verification
- Performance tests: 10,000 resources per tenant, query performance <500ms

**NFRs Addressed:**
- NFR-2 (Scalability): Support 100 tenants simultaneously
- NFR-2 (Scalability): Support 10,000 resources per tenant with <500ms queries
- FR-3: Multi-Tenant Support

**Architecture Decisions:**
- AD-6: Multi-Tenant Isolation by Access Key
