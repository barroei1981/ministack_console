# Story MSCL-1: FalkorDB Setup and Schema Definition

**Epic:** Epic 1 - Control-Plane Foundation  
**Story Points:** 3  
**Priority:** P0 - Critical Path  
**Dependencies:** None (foundation story)

## User Story

As a **developer**,  
I want **FalkorDB to be set up with the resource graph schema**,  
So that **the control-plane can store and query resource relationships**.

## Acceptance Criteria

**Given** FalkorDB is not yet configured  
**When** the system starts for the first time  
**Then** FalkorDB initializes with the complete graph schema  
**And** all required node types are created (Tenant, Project, Resource, ServiceType)  
**And** all required relationship types are defined (OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF)  
**And** indexes are created on: `Resource.tenant_id`, `Resource.type`, `Resource.name`, `Project.name`

**Given** FalkorDB schema is initialized  
**When** I query the schema metadata  
**Then** I can verify all node types exist  
**And** I can verify all relationship types are defined  
**And** I can verify all indexes are active

**Given** the schema is complete  
**When** I attempt to create a test resource node  
**Then** the node is created successfully with all required properties  
**And** I can query it back by ID, tenant_id, and type

## Technical Notes

**Implementation Files:**
- `control_plane/graph/schema.py` - FalkorDB schema definition and initialization
- `control_plane/graph/query.py` - Base graph query operations
- `docker-compose.yml` - FalkorDB service configuration

**FalkorDB Schema (Cypher):**
```cypher
// Node Types
(:Tenant {id, name, created_at})
(:Project {name, description, tenant_id, created_at})
(:Resource {
    id,              // Unique resource ID
    type,            // e.g., "s3:bucket", "lambda:function"
    name,            // Resource name
    tenant_id,       // Owner tenant
    arn,             // AWS ARN format
    state,           // JSON blob of resource state
    created_at,
    updated_at
})
(:ServiceType {name, category})

// Relationship Types
(:Tenant)-[:OWNS]->(:Project)
(:Project)-[:CONTAINS]->(:Resource)
(:Resource)-[:DEPENDS_ON]->(:Resource)
(:Resource)-[:TAGGED_WITH {key, value}]->(:Tag)
(:Resource)-[:INSTANCE_OF]->(:ServiceType)

// Indexes
CREATE INDEX tenant_id ON Resource(tenant_id)
CREATE INDEX resource_type ON Resource(type)
CREATE INDEX resource_name ON Resource(name)
CREATE INDEX project_name ON Project(name)
```

**Docker Configuration:**
```yaml
falkordb:
  image: falkordb/falkordb:latest
  container_name: falkordb
  ports:
    - "6379:6379"
  volumes:
    - falkordb-data:/data
  command: ["redis-server", "--appendonly", "yes"]
```

**Testing:**
- Unit tests: Schema initialization, node creation, relationship creation
- Integration tests: Full graph CRUD operations
- Verify persistence: Restart FalkorDB and verify data persists

**NFRs Addressed:**
- NFR-3 (Reliability): Data persistence survives control-plane restarts
- NFR-2 (Scalability): Support 10,000 resources per tenant

**Architecture Decisions:**
- AD-2: FalkorDB for Resource Graph
- AD-11: Hybrid Schema Evolution Strategy
