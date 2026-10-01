# Epic 1 Context: Control-Plane Foundation

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Build the foundational control-plane that maintains a real-time inventory of all MiniStack resources across tenants and projects. This epic establishes the core data model, resource polling system, graph database, and multi-tenant isolation that all other features depend on. Developers working on later epics will assume this foundation exists and provides accurate, current resource state.

## Stories

- Story 1.1 (MSCL-1): FalkorDB Setup and Schema
- Story 1.2 (MSCL-2): Resource Poller Core
- Story 1.3 (MSCL-3): Multi-Tenant Detection
- Story 1.4 (MSCL-4): Control-Plane Tagging
- Story 1.5 (MSCL-5): Dependency Detection
- Story 1.6 (MSCL-6): REST API Foundation
- Story 1.7 (MSCL-7): SSE Event System

## Requirements & Constraints

**Resource Inventory:**
- Poll MiniStack API every 30 seconds (configurable) for resource state changes
- Support incremental updates - detect only what changed, not full re-scan each cycle
- Handle MiniStack restarts gracefully: detect via health check endpoint and re-inventory within 1 minute
- Track resource lifecycle: created, modified, deleted events
- Store metadata: type, ID, name, tenant, project, tags, created_at, state (JSON blob)

**Resource Graph:**
- Detect Lambda → S3 dependencies from environment variables and IAM policies
- Detect Lambda → SQS/SNS dependencies from event source mappings
- Detect S3 → IAM policy relationships
- Graph updates in real-time as resources change
- Support queries: "What depends on X?" and "What does X depend on?"

**Multi-Tenant Isolation:**
- Tenant identified by 12-digit MiniStack access key (AWS access key = tenant boundary)
- Every resource has tenant_id property, all queries filter by tenant
- Prevent cross-tenant data leakage at database level

**Tagging System:**
- **Control-plane tags:** Stored in FalkorDB, apply to ALL resources (all services), used for project grouping and logical organization
- **Native MiniStack tags:** Stored in MiniStack via AWS APIs, apply only to services that support native tagging (S3, EC2, Lambda), used for AWS CLI/SDK compatibility
- Write-through: control-plane tags always in FalkorDB, native tags in both FalkorDB and MiniStack

**Performance Targets:**
- Resource list load: <500ms for 1000 resources
- Graph queries: <2s for complex traversals
- SSE event latency: <5 seconds from change detection to UI notification
- Support 10,000 resources per tenant, 100 tenants simultaneously

**Error Handling:**
- Polling failures: Retry twice with exponential backoff (1s, 2s)
- After 3 consecutive failures (90 seconds): mark resources as "stale" with yellow badge
- After 5 consecutive failures (2.5 minutes): show UI alert banner with "Retry Now" button
- Auto-recovery: clear stale markers on successful poll, full re-sync after restart

## Technical Decisions

**Core Backend:**
- Python 3.11+ with FastAPI 0.104+ for REST API
- All business logic resides in REST API layer (no logic duplication in MCP or UI)
- Type hints mandatory, async/await patterns for all I/O operations

**Graph Database:**
- FalkorDB (Redis-based graph database) as single source of truth for resource inventory and relationships
- Run via Docker container alongside MiniStack
- Graph schema: Node types (Tenant, Project, Resource, ServiceType), Relationships (OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF)
- Hybrid schema evolution: Core structure is stable (requires migration), Resource.state property is flexible JSON blob (no schema enforcement)

**Polling Architecture:**
- Background poller runs on 30-second interval (configurable)
- Use boto3 with MiniStack endpoint (localhost:4566)
- Incremental change detection: compare current state to last snapshot
- MiniStack health check via `/_ministack/health` internal API
- On restart detection: full re-inventory of all tenants

**Real-time Updates:**
- Server-Sent Events (SSE) for server→client streaming (not bidirectional WebSocket)
- Event bus publishes changes to all subscribed UI clients
- Event types: RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_DELETED, DEPENDENCY_ADDED, DEPENDENCY_REMOVED, TAGS_UPDATED
- Built-in reconnect logic via native EventSource API

**Multi-Tenant Context:**
- 12-digit MiniStack access key = tenant ID
- Tenant context propagated through all layers (poller → inventory → graph → API → UI)
- FalkorDB queries enforce tenant boundary with WHERE tenant_id = ? filters
- No shared state across tenants

**Data Model:**
- Resource node properties: id, type (e.g., "s3:bucket"), name, tenant_id, arn, state (JSON), created_at, updated_at
- Resource.state contains service-specific metadata with no schema enforcement
- New service types added as new ServiceType nodes (additive, forward-compatible)
- Structural changes (new node types, relationships) require migration scripts documented in `.harness/decisions/`

## Cross-Story Dependencies

**Linear Dependencies:**
- MSCL-1 (FalkorDB setup) must complete before MSCL-2 (poller) can store resources
- MSCL-2 (poller) must complete before MSCL-5 (dependency detection) has data to analyze
- MSCL-3 (multi-tenant) must complete before MSCL-4 (tagging) to ensure tenant isolation in tags
- MSCL-6 (REST API) depends on MSCL-1, MSCL-2, MSCL-3 for data access layer
- MSCL-7 (SSE events) depends on MSCL-2 (poller emits events) and MSCL-6 (API serves SSE endpoint)

**Integration Points:**
- MSCL-6 (REST API) is consumed by Epic 2-4 (service dashboards), Epic 5 (MCP server), Epic 6 (resource explorer)
- MSCL-7 (SSE events) powers real-time UI updates across all service dashboards
- MSCL-5 (dependency detection) data consumed by Epic 6 (graph visualization)

**External Systems:**
- MiniStack API (localhost:4566): boto3 clients for all service polling
- MiniStack Internal API (`/_ministack/health`, `/_ministack/config`): health checks and restart detection
