# Implementation Plan: MSCL-1 - FalkorDB Setup and Schema Definition

## Alignment

- **Epic**: Epic 1 - Control-Plane Foundation (Users can view and track all MiniStack resources across tenants and projects with automatic real-time updates)
- **PRD requirement**: FR-2 (Resource Graph) - "Graph stored in FalkorDB with periodic snapshots" (line 35 in epics.md)
- **Architecture constraint**: 
  - AD-2: FalkorDB for Resource Graph - "All resource relationships and metadata stored in FalkorDB. Redis-based, in-memory with persistence. Single source of truth for resource inventory."
  - AD-11: Hybrid Schema Evolution Strategy - "Core Structure (Fixed): Node types and relationships are stable, changes require migration script. Resource Metadata (Flexible): JSON state property with no schema enforcement."
  - Architecture doc section 4.1 defines complete FalkorDB schema: Tenant, Project, Resource, ServiceType nodes with OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF relationships
- **ADRs in scope**: 
  - `.harness/decisions/2026-10-01-architecture-control-plane-with-mcp.md` (defines control-plane architecture, establishes FalkorDB as core component)
  - AD-2 and AD-11 detailed in `docs/planning-artifacts/epics.md` lines 213-273
- **Reuse decision**: No existing code (greenfield project). No overlap found. This is the foundation story for the control-plane core.
- **Cross-layer contract**: N/A for this story - infrastructure setup only, no UI/API integration in this story. Backend API and UI components come in later stories (MSCL-6, MSCL-7).
- **Confirmed consistent**: YES
  - Story directly implements FR-2 requirement for FalkorDB-based resource graph
  - Schema matches architecture doc section 4.1 specification exactly
  - Follows AD-11 hybrid strategy: fixed core structure (node/relationship types), flexible resource metadata (JSON state property)
  - Docker setup follows AD-10: Docker-First Deployment
  - No conflicts with any ADR or architecture constraint

## Implementation Approach

### Phase 1: Docker Setup
1. Create `docker-compose.yml` with FalkorDB service
2. Configure persistence (appendonly mode)
3. Expose port 6379

### Phase 2: Schema Definition
1. Create `control_plane/graph/schema.py`
   - Define node types: Tenant, Project, Resource, ServiceType
   - Define relationship types: OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF
   - Schema initialization function
   - Index creation: tenant_id, resource_type, resource_name, project_name

### Phase 3: Base Query Operations
1. Create `control_plane/graph/query.py`
   - FalkorDB connection management
   - Base CRUD operations (create node, create relationship, query)
   - Health check function

### Phase 4: Testing
1. Unit tests for schema initialization
2. Integration tests for CRUD operations
3. Persistence test (restart FalkorDB, verify data persists)

## Task Checklist

- [ ] Create docker-compose.yml with FalkorDB service
- [ ] Create control_plane/graph/schema.py (schema definition)
- [ ] Create control_plane/graph/query.py (base operations)
- [ ] Write unit tests for schema initialization
- [ ] Write integration tests for graph CRUD
- [ ] Test persistence (restart and verify)
- [ ] Verify all indexes are active
- [ ] Document connection configuration
