---
title: 'MSCL-1: FalkorDB Setup and Schema Definition'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'e5cb953a6480486d6844665fd848323e585ed624'
context: 
  - 'docs/planning-artifacts/architecture.md'
  - 'docs/planning-artifacts/prd.md'
  - '.harness/decisions/2026-10-01-architecture-control-plane-with-mcp.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** MiniStack Console requires a resource graph to track tenant → project → resource relationships and dependencies (e.g., which Lambda uses which SQS queue). Currently no graph database is configured and no schema is defined for storing this relationship data.

**Approach:** Set up FalkorDB as the graph database with Docker Compose, define the complete node and relationship schema (Tenant, Project, Resource, ServiceType nodes with OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF relationships), implement schema initialization logic, and create base query operations for graph CRUD.

## Boundaries & Constraints

**Always:**
- Use FalkorDB (Redis-based graph database) per AD-2
- Follow Hybrid Schema Evolution Strategy per AD-11: core structure (node/relationship types) is fixed and stable; resource metadata uses flexible JSON `state` property
- Create indexes on: Resource.tenant_id, Resource.type, Resource.name, Project.name
- Enable persistence (appendonly mode) to survive control-plane restarts per NFR-3
- Use Python 3.11+ with type hints

**Ask First:**
- Changes to core node types or relationship types (requires migration strategy per AD-11)
- Alternative to FalkorDB (contradicts AD-2)

**Never:**
- Store resource state in files or relational databases (graph is single source of truth per AD-2)
- Skip indexes (required for query performance per NFR-1: <500ms queries)
- Hard-code connection strings (must be configurable)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First-time schema init | FalkorDB empty, no nodes/indexes | Schema initialized: all node types, relationships, indexes created | Fail fast if FalkorDB unavailable |
| Schema already initialized | FalkorDB has existing nodes | Idempotent: verify schema exists, no-op or add missing indexes | Log warning if schema mismatch detected |
| Create test resource node | Valid Resource dict (id, type, name, tenant_id, arn, state) | Node created, query returns it by id/tenant_id/type | Raise ValueError on missing required fields |
| FalkorDB connection failure | FalkorDB not running or wrong port | Connection error raised | Retry 3 times with exponential backoff, then fail |
| Data persistence test | Create node, restart FalkorDB container, query | Node still exists after restart | Fail if data not persisted (appendonly config issue) |

</frozen-after-approval>

## Code Map

**New files to create:**
- `docker-compose.yml` -- FalkorDB service configuration with persistence and port mapping
- `control_plane/__init__.py` -- Package marker
- `control_plane/graph/__init__.py` -- Graph module package marker
- `control_plane/graph/schema.py` -- Schema definition (node types, relationship types, indexes) and initialization function
- `control_plane/graph/query.py` -- FalkorDB connection management, base CRUD operations (create_node, create_relationship, query_nodes), health check

**No existing files to modify** -- this is greenfield foundation work.

## Tasks & Acceptance

**Execution:**
- [x] `docker-compose.yml` -- Create FalkorDB service with falkordb/falkordb:latest image, expose port 6380, configure volume for data persistence, enable appendonly mode -- Required for AD-10 (Docker-First Deployment) and NFR-3 (data persistence)
- [x] `control_plane/graph/schema.py` -- Define SCHEMA constant with all node types (Tenant, Project, Resource, ServiceType) and relationship types (OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF); implement `initialize_schema()` to create indexes; implement `verify_schema()` to check all types exist -- Required for FR-2 (Resource Graph) and AD-11 (Hybrid Schema Evolution)
- [x] `control_plane/graph/query.py` -- Implement FalkorDB connection via falkordb-py or redis-py with graph commands; implement `create_node(label, properties)`, `create_relationship(from_node, rel_type, to_node, properties)`, `query_nodes(label, filters)`, `health_check()` -- Required for FR-2 (Resource Graph CRUD operations)
- [x] `tests/test_graph_schema.py` -- Unit tests for schema initialization idempotency, index creation verification, node type existence checks -- Required for quality gates
- [x] `tests/test_graph_query.py` -- Integration tests for create node, create relationship, query by tenant_id/type/name, health check -- Required for quality gates
- [x] `tests/test_persistence.py` -- Integration test: create node, restart FalkorDB container via docker-compose, verify node still exists -- Required for NFR-3 (data persists across restarts)

**Acceptance Criteria:**
- Given FalkorDB is not yet configured, when the schema initialization runs for the first time, then FalkorDB initializes with all node types (Tenant, Project, Resource, ServiceType), all relationship types (OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF), and all indexes on Resource.tenant_id, Resource.type, Resource.name, Project.name
- Given FalkorDB schema is initialized, when I query the schema metadata, then I can verify all node types exist, all relationship types are defined, and all indexes are active
- Given the schema is complete, when I create a test Resource node with all required properties (id, type, name, tenant_id, arn, state, created_at, updated_at), then the node is created successfully and I can query it back by id, tenant_id, and type
- Given data is written to FalkorDB, when the FalkorDB container is restarted via docker-compose, then all data persists and can be queried after restart (validates appendonly configuration)

## Spec Change Log

## Design Notes

**FalkorDB Schema Structure (Cypher notation):**
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
    state,           // JSON blob of resource state (flexible per AD-11)
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

// Indexes (for NFR-1 query performance)
CREATE INDEX tenant_id ON Resource(tenant_id)
CREATE INDEX resource_type ON Resource(type)
CREATE INDEX resource_name ON Resource(name)
CREATE INDEX project_name ON Project(name)
```

**Connection Configuration:**
- Default: localhost:6379
- Configurable via environment variable FALKORDB_HOST and FALKORDB_PORT
- Connection pooling for concurrent access (NFR-2: 100 concurrent MCP connections)

**Python FalkorDB Client:**
- Use `falkordb` package (pip install falkordb) for native RedisGraph/FalkorDB support
- Fallback: redis-py with GRAPH commands if falkordb unavailable

## Verification

**Commands:**
- `docker-compose up -d falkordb` -- expected: container starts, health check passes
- `docker-compose ps` -- expected: falkordb service shows "Up" status
- `pytest tests/test_graph_schema.py -v` -- expected: all schema initialization tests pass
- `pytest tests/test_graph_query.py -v` -- expected: all CRUD operation tests pass
- `pytest tests/test_persistence.py -v` -- expected: persistence test passes (restart scenario)
- `python -c "from control_plane.graph.query import health_check; print(health_check())"` -- expected: returns True

**Manual checks:**
- After `docker-compose up`, verify FalkorDB accessible: `redis-cli -p 6379 PING` → PONG
- After schema init, verify indexes exist via FalkorDB CLI or query.py

## Suggested Review Order

**FalkorDB Infrastructure**

- Docker Compose defines FalkorDB service with persistence and health checks
  [`docker-compose.yml:1`](../../docker-compose.yml#L1)

**Graph Schema Definition**

- Schema constant defines all node types (Tenant, Project, Resource, ServiceType, Tag) and relationships (OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF) with indexes
  [`schema.py:496`](../../control_plane/graph/schema.py#L496)

- Idempotent schema initialization creates indexes, handles "already exists" gracefully
  [`schema.py:591`](../../control_plane/graph/schema.py#L591)

- Schema verification queries existing indexes and reports missing ones
  [`schema.py:632`](../../control_plane/graph/schema.py#L632)

**Connection Management & CRUD Operations**

- Connection pooling with retry logic (exponential backoff capped at 60s) and UUID-based test graph isolation
  [`query.py:72`](../../control_plane/graph/query.py#L72)

- Input validation prevents Cypher injection on property keys and filter keys
  [`query.py:196`](../../control_plane/graph/query.py#L196), [`query.py:323`](../../control_plane/graph/query.py#L323)

- Create node with parameterized Cypher query
  [`query.py:168`](../../control_plane/graph/query.py#L168)

- Create relationship matches both nodes then creates edge
  [`query.py:218`](../../control_plane/graph/query.py#L218)

- Query nodes with optional filters and limit
  [`query.py:296`](../../control_plane/graph/query.py#L296)

**Test Coverage**

- Schema initialization tests verify idempotency and index creation
  [`test_graph_schema.py:1`](../../tests/test_graph_schema.py#L1)

- CRUD operation tests cover create/query/delete for all node types
  [`test_graph_query.py:1`](../../tests/test_graph_query.py#L1)

- Persistence tests verify data survives container restarts (requires manual docker-compose restart)
  [`test_persistence.py:1`](../../tests/test_persistence.py#L1)

**Project Configuration**

- Python project dependencies and test configuration
  [`pyproject.toml:1`](../../pyproject.toml#L1)
