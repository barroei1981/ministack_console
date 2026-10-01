---
title: 'MSCL-3: Multi-Tenant Isolation and Tenant Management'
type: 'feature'
created: '2026-10-02'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'e6a6ea7cb1757142e5b3c7eb99ebb4dc0d29f119'
context:
  - '_lch-output/implementation-artifacts/epic-1-context.md'
  - 'control_plane/graph/query.py'
  - 'control_plane/inventory/sync.py'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Polling system (MSCL-2) creates Resource nodes without tenant isolation. Multiple MiniStack tenants (different 12-digit access keys) would mix resources in FalkorDB with no boundary enforcement. Queries can't filter by tenant, and there's no automatic Tenant node creation or OWNS relationships.

**Approach:** Extract tenant_id from MiniStack access keys during polling, create Tenant nodes automatically in FalkorDB, enforce all Resource queries are tenant-scoped using the tenant_id index, and add utility functions for tenant-aware operations (create Project with OWNS relationship, list tenants, switch tenant context).

## Boundaries & Constraints

**Always:**
- Extract tenant_id from 12-digit MiniStack access key per AD-6
- Create Tenant nodes via MERGE (idempotent) when first resource from that tenant is discovered
- Use tenant_id index (created in MSCL-1) for all tenant-scoped queries per NFR-1 (<500ms)
- Enforce tenant isolation: every Resource/Project query MUST filter by tenant_id
- Create (Tenant)-[:OWNS]->(Project) relationships when Projects are created
- Use existing graph operations from control_plane/graph/query.py (create_node, query_nodes)

**Ask First:**
- Adding tenant switching in Web UI (deferred to MSCL-7 SSE/UI stories)
- Adding API middleware for HTTP tenant context (deferred to MSCL-6 REST API story)
- Changing tenant ID format from 12-digit access key

**Never:**
- Allow cross-tenant queries (resources from multiple tenants in one result)
- Skip tenant_id validation (must be 12 digits, numeric)
- Create Resources without tenant_id property
- Query Resources without tenant_id filter (except for admin list-all-tenants operations)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First resource from new tenant | Resource with tenant_id "123456789012" | Tenant node created via MERGE, Resource node created with tenant_id | N/A |
| Tenant already exists | Resource with existing tenant_id | Tenant node already exists (MERGE no-op), Resource created with tenant_id | N/A |
| Invalid tenant ID (not 12 digits) | tenant_id "abc" or "123" | ValueError raised | Do not create Resource, log error |
| Query resources by tenant | tenant_id "123456789012" | Returns only resources for that tenant, uses tenant_id index | Returns empty list if tenant has no resources |
| Create Project for tenant | Project with tenant_id "123456789012" | Project node created, (Tenant)-[:OWNS]->(Project) relationship created | Raise ValueError if Tenant doesn't exist |
| List all tenants | No input | Returns all Tenant nodes from FalkorDB | Returns empty list if no tenants |
| Query resources for nonexistent tenant | tenant_id "999999999999" (not in DB) | Returns empty list | No error (valid tenant format, just no resources yet) |
| Cross-tenant query attempt | Query without tenant_id filter | Blocked by tenant-aware wrapper function | Raises ValueError "tenant_id required" |

</frozen-after-approval>

## Code Map

**Reuse from MSCL-1:**
- `control_plane/graph/query.py` -- create_node(), query_nodes() for FalkorDB CRUD (lines 168, 296)
- `control_plane/graph/schema.py` -- SCHEMA defines Tenant node type (line 496), tenant_id index exists

**Reuse from MSCL-2:**
- `control_plane/inventory/sync.py` -- sync_changes() creates Resource nodes (line 50), needs tenant awareness
- `control_plane/inventory/models.py` -- Resource model has tenant_id property (line 20)

**New modules to create:**
- `control_plane/tenants/isolation.py` -- Tenant management: ensure_tenant_exists(), validate_tenant_id(), get_tenant_resources(), create_project_with_ownership()
- `control_plane/tenants/detector.py` -- extract_tenant_id() from MiniStack access key

**Integration points:**
- `control_plane/inventory/sync.py` -- Update sync_changes() to call ensure_tenant_exists() before creating Resources
- `control_plane/ministack_client.py` -- Pass tenant_id (access key) through to Resource creation

## Tasks & Acceptance

**Execution:**
- [x] `control_plane/tenants/detector.py` -- Implement extract_tenant_id(access_key): validate 12-digit format, return tenant_id -- Required for AD-6 (tenant isolation)
- [x] `control_plane/tenants/isolation.py` -- Implement ensure_tenant_exists(tenant_id): MERGE Tenant node if not exists -- Required for FR-3 (multi-tenant support)
- [x] `control_plane/tenants/isolation.py` -- Implement get_tenant_resources(tenant_id, resource_type=None): query Resources filtered by tenant_id using index -- Required for NFR-1 (<500ms queries)
- [x] `control_plane/tenants/isolation.py` -- Implement create_project_with_ownership(project_name, tenant_id): create Project node and (Tenant)-[:OWNS]->(Project) relationship -- Required for FR-4 (project tagging)
- [x] `control_plane/tenants/isolation.py` -- Implement list_tenants(): return all Tenant nodes -- Required for tenant discovery
- [x] `control_plane/inventory/sync.py` -- Update sync_changes() to call ensure_tenant_exists(resource.tenant_id) before syncing each CREATED resource -- Required for automatic Tenant node creation
- [x] `tests/test_tenant_detector.py` -- Unit tests for tenant ID extraction: valid format, invalid format, edge cases -- Required for quality gates
- [x] `tests/test_tenant_isolation.py` -- Unit tests for tenant operations: ensure_tenant_exists idempotency, get_tenant_resources filtering, create_project_with_ownership -- Required for quality gates
- [x] `tests/integration/test_multi_tenant.py` -- Integration test: create resources for 2 tenants, verify isolation (query tenant A returns only A's resources, not B's) -- Required for AC validation

**Acceptance Criteria:**
- Given multiple MiniStack tenants exist (different 12-digit access keys), when resources are polled from MiniStack, then each resource is tagged with its tenant_id (extracted from access key), resources are stored in FalkorDB with tenant_id property, and Tenant nodes are created automatically if they don't exist
- Given I query resources via get_tenant_resources() with a specific tenant_id, when the query executes, then only resources belonging to that tenant are returned, resources from other tenants are never included, and cross-tenant queries without tenant_id filter raise ValueError
- Given I create a Project in a specific tenant via create_project_with_ownership(), when the Project is saved to FalkorDB, then a (Tenant)-[:OWNS]->(Project) relationship is created, the project's tenant_id matches the tenant, and queries for that tenant's projects return the new project
- Given a tenant has 10,000 resources, when I query that tenant's resources via get_tenant_resources(), then the query completes in <500ms and uses the tenant_id index for efficient lookup

## Spec Change Log

## Design Notes

**Tenant ID Extraction:**
```python
def extract_tenant_id(access_key: str) -> str:
    """Extract tenant ID from MiniStack 12-digit access key."""
    if not access_key or len(access_key) != 12 or not access_key.isdigit():
        raise ValueError(f"Invalid MiniStack access key: {access_key}. Must be 12 digits.")
    return access_key
```

**Tenant Node Creation (Idempotent):**
```python
async def ensure_tenant_exists(tenant_id: str) -> None:
    """Create Tenant node if it doesn't exist (idempotent MERGE)."""
    # Check if tenant already exists
    existing = query_nodes("Tenant", filters={"id": tenant_id})
    if not existing:
        # Create new Tenant node
        create_node("Tenant", {
            "id": tenant_id,
            "name": tenant_id,  # Default name is the ID
            "created_at": datetime.now(UTC).isoformat()
        })
```

**Tenant-Scoped Resource Query:**
```python
def get_tenant_resources(tenant_id: str, resource_type: Optional[str] = None) -> List[Dict]:
    """Get all resources for a tenant, optionally filtered by type.
    
    Uses tenant_id index for performance per NFR-1.
    """
    filters = {"tenant_id": tenant_id}
    if resource_type:
        filters["type"] = resource_type
    
    return query_nodes("Resource", filters=filters)
```

**Project Creation with Ownership:**
```python
def create_project_with_ownership(project_name: str, tenant_id: str, description: str = "") -> Dict:
    """Create Project node and link to Tenant via OWNS relationship."""
    # Verify tenant exists
    tenant = query_nodes("Tenant", filters={"id": tenant_id})
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} does not exist")
    
    # Create Project node
    project = create_node("Project", {
        "name": project_name,
        "description": description,
        "tenant_id": tenant_id,
        "created_at": datetime.now(UTC).isoformat()
    })
    
    # Create OWNS relationship
    create_relationship(
        from_node_id=tenant_id,
        from_label="Tenant",
        rel_type="OWNS",
        to_node_id=project_name,  # Project uses name as ID
        to_label="Project"
    )
    
    return project
```

## Verification

**Commands:**
- `pytest tests/test_tenant_detector.py -v` -- expected: all tenant ID extraction tests pass
- `pytest tests/test_tenant_isolation.py -v` -- expected: all tenant isolation tests pass
- `pytest tests/integration/test_multi_tenant.py -v` -- expected: multi-tenant isolation test passes
- `python -c "from control_plane.tenants.detector import extract_tenant_id; print(extract_tenant_id('123456789012'))"` -- expected: "123456789012"
- `python -c "from control_plane.tenants.isolation import ensure_tenant_exists; import asyncio; asyncio.run(ensure_tenant_exists('123456789012'))"` -- expected: Tenant node created in FalkorDB

**Manual checks:**
- Query FalkorDB after running poller: verify Tenant nodes exist for each unique tenant_id
- Query Resources for one tenant: verify only that tenant's resources returned, no cross-tenant leakage
- Create Project: verify (Tenant)-[:OWNS]->(Project) relationship exists in graph
