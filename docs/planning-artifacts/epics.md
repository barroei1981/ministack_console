---
stepsCompleted: ["step-01-validate-prerequisites"]
inputDocuments: 
  - "docs/planning-artifacts/prd.md (v1.5 FINAL)"
  - "docs/planning-artifacts/architecture.md (v1.5 FINAL)"
---

# ministack_console - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **ministack_console**, decomposing the requirements from the PRD v1.5 and Architecture v1.5 into implementable stories. The project builds a dual-interface control-plane for MiniStack (AWS emulator): Web UI for human developers and MCP Server for AI assistants.

## Requirements Inventory

### Functional Requirements (from PRD v1.5)

#### Control-Plane Core (Critical Path)

**FR-1: Resource Inventory System** (Priority: P0)
- Poll MiniStack API every 30 seconds for resource state
- Store resource metadata: type, ID, name, tenant, project, tags, created_at
- Support incremental updates (not full re-scan)
- Handle MiniStack restarts gracefully
- Track resource lifecycle: created, modified, deleted
- Use MiniStack Internal API for bulk queries where available

**FR-2: Resource Graph** (Priority: P0)
- Detect Lambda → S3 dependencies (via environment variables, IAM policies)
- Detect Lambda → SQS/SNS dependencies (event source mappings)
- Detect S3 → IAM policy relationships
- Detect CloudFormation stack → managed resources
- Graph updates in real-time as resources change
- Query: "What depends on resource X?" returns accurate list
- Query: "What does resource Y depend on?" returns accurate list
- Graph stored in FalkorDB with periodic snapshots

**FR-3: Multi-Tenant Support** (Priority: P0)
- Detect tenant from AWS access key (12-digit MiniStack access key = tenant ID)
- UI: Tenant selector dropdown (list all tenants)
- UI: Filter all resources by selected tenant
- MCP: `ministack://tenant/{id}` resource queries
- Prevent cross-tenant data leakage

**FR-4: Project Tagging** (Priority: P1)
- UI: Assign project to any resource
- UI: Filter resources by project
- MCP: `ministack://project/{name}/resources` query
- Support multiple projects per tenant
- Tag propagation: CloudFormation-created resources inherit project tag

#### Web UI - Human Interface

**FR-5: Service Dashboards (Top 10 Services)** (Priority: P0)
- **Phase 1 MVP - Guaranteed Top 3:**
  1. **S3**: Bucket management, object browser, uploads, download, metadata editor, pre-signed URLs
  2. **Lambda**: Function list, code view, logs, test invocation, environment variable editor
  3. **DynamoDB**: Table browser, item CRUD, query/scan, JSON editor
- **Phase 1 - Community-Driven (Services 4-5):** Selected via early adopter survey + GitHub vote from candidates: SQS, CloudWatch Logs, IAM, SNS, EC2, RDS, ECS
- **Phase 2 (Services 6-10):** IAM, SNS, EC2, RDS, ECS with full CRUD
- **Acceptance Criteria (Per Service):**
  - List view with search/filter
  - Create form with all required parameters
  - Detail view showing full resource configuration
  - Update capabilities (where supported by AWS API)
  - Delete with confirmation
  - Real-time updates via SSE

**FR-6: Resource Explorer** (Priority: P1)
- Full-text search across all resource names/IDs
- Filter by service type, tenant, project, tags
- Quick navigation to resource detail page
- Recent resources list (last 20 accessed)
- Favorites/bookmarks

**FR-7: Resource Graph Visualization** (Priority: P1)
- Interactive graph view (zoom, pan, click nodes)
- Highlight dependencies when selecting resource
- Color-code by service type
- Filter graph by tenant/project
- Export graph as image (PNG/SVG)

**FR-8: Project Management UI** (Priority: P1)
- Projects list page
- Create project form (name, description, tenant)
- Project detail page: all associated resources
- Bulk operations: "Delete all resources in project X"
- Project dashboard: resource counts by service type

**FR-9: Tenant Management UI** (Priority: P2)
- Tenants list page (all 12-digit access keys)
- Tenant detail page: projects, resource counts
- Tenant switcher in header (persistent across sessions)
- Per-tenant resource limits and quotas display

#### MCP Server - AI Assistant Interface

**FR-10: MCP Server Core** (Priority: P0)
- MCP server runs on configurable port (default: 3100)
- Supports MCP protocol v1.0
- Authentication: API key-based (generate keys in UI)
- Rate limiting: 1000 requests/minute per API key
- Logging: All queries logged for debugging
- Use official MCP SDK for Python or TypeScript

**FR-11: MCP Resources - Read Operations** (Priority: P0)
- MCP resources expose all tenant, project, and resource queries:
  - `ministack://tenants` - List all tenants
  - `ministack://tenant/{tenant_id}/resources` - All resources in tenant
  - `ministack://tenant/{tenant_id}/projects` - All projects in tenant
  - `ministack://project/{project_name}/resources` - Project resources
  - `ministack://resources/{service_type}` - Resources by type
  - `ministack://resource/{resource_id}/details` - Full details
  - `ministack://resource/{resource_id}/dependencies` - What resource depends on
  - `ministack://resource/{resource_id}/dependents` - What depends on resource
- All resources return JSON with standard schema
- Queries filter by tenant/project/tags
- Queries support pagination (100 items per page)
- Error handling: 404 for non-existent, 400 for invalid queries

**FR-12: MCP Tools - Write Operations (Full CRUD)** (Priority: P0)
- **Phase 1 Tools (Top 3 Services + 2 Community-Voted):**
  - `create_s3_bucket`, `delete_s3_bucket`
  - `create_lambda_function`, `update_lambda_function`, `delete_lambda_function`
  - `create_dynamodb_table`, `delete_dynamodb_table`
  - `create_sqs_queue`, `delete_sqs_queue`, `send_sqs_message` (if SQS voted)
  - `tag_resource` (assign project tag)
  - `bulk_create_stack` (create multiple resources from JSON definition)
- **Acceptance Criteria:**
  - All tools validate input parameters
  - Create/update/delete tools call MiniStack API and update control-plane immediately
  - Tools return resource ID and details on success
  - Tools return clear error messages with actionable guidance
  - Delete tools require confirmation parameter
  - Bulk operations support atomic rollback (all-or-nothing via checkpoint pattern)
  - Audit log: All invocations logged with API key, timestamp, parameters, outcome
  - Rate limiting: Max 100 write operations per minute per API key

**FR-13: MCP Prompts - Use Case Templates** (Priority: P2)
- Prompts: `list_environment_state`, `generate_terraform_for_project`, `explain_resource_dependencies`, `suggest_cleanup`
- Prompts return structured context for AI assistants
- Prompts support parameters (tenant_id, project_name)
- Prompts include examples in responses

**FR-14: Extended Service Coverage** (Priority: P2 - Post-MVP)
- Add full CRUD support for remaining 50+ MiniStack services
- Service categories: Infrastructure (CloudFormation, VPC, Route53, ACM, CloudFront), Compute (ECS, EKS, Batch), Data (RDS Aurora, ElastiCache, Athena, Glue), Analytics & ML (Kinesis, EMR, SageMaker, Bedrock)
- Each service has list/detail/create/delete UI
- Service-specific features (e.g., CloudFormation drift detection)
- MCP resources and tools for each service type

### Non-Functional Requirements (from PRD v1.5)

**NFR-1: Performance**
- UI Initial Load: <2 seconds (CRITICAL)
- Resource List Load: <500ms for 1000 resources (CRITICAL)
- Graph Render: <1 second for 500 nodes
- MCP Query Response: <500ms for simple queries (CRITICAL)
- MCP Query Response: <2s for complex graph queries (CRITICAL)
- Real-time Updates: <5 seconds latency
- MiniStack Poll Interval: 30 seconds (configurable)

**NFR-2: Scalability**
- Resources: Support 10,000 resources per tenant
- Tenants: Support 100 tenants simultaneously
- Concurrent Users (UI): 50 users
- Concurrent MCP Connections: 100 connections
- Graph Complexity: 500 nodes, 2000 edges

**NFR-3: Reliability**
- Uptime: 99% (local development tool)
- Data Persistence: Resource graph survives control-plane restarts
- MiniStack Restart Handling: Detect restart, re-inventory within 1 minute
- Error Recovery: UI shows clear error messages, retries failed API calls (3 attempts)

**NFR-4: Security**
- MCP Authentication: API key required for all MCP requests
- API Key Management: Generate/revoke keys via UI
- Audit Logging: All write operations logged (who, what, when)
- No External Dependencies: All data stays local
- Secret Handling: IAM credentials displayed with show/hide toggle

**NFR-5: Usability**
- Responsive Design: UI works on desktop (1920x1080) and laptop (1366x768)
- Accessibility: WCAG 2.1 AA compliance (keyboard navigation, screen reader support)
- Error Messages: Clear, actionable error messages (not raw AWS error codes)
- Onboarding: First-time user tutorial (5 minutes)
- Documentation: Inline help text for all forms

**NFR-6: Compatibility**
- MiniStack Versions: Support MiniStack 3.0+ (current major version)
- Browsers: Chrome 100+, Firefox 100+, Safari 15+, Edge 100+
- MCP Clients: Compatible with Claude Desktop, Claude Code, custom MCP clients
- Operating Systems: macOS, Linux, Windows (via WSL2)

**NFR-7: Deployment**
- Deployment Model: Docker container or standalone binary
- Resource Usage: <500MB RAM, <100MB disk
- Startup Time: <10 seconds
- Configuration: Single config file (YAML or TOML)
- Ports: Configurable (defaults: UI 3000, MCP 3100, API 3001)

### Additional Requirements (from Architecture v1.5)

#### Architecture Decisions (Technical Implementation Requirements)

**AD-1: REST API as Core Backend**
- All business logic resides in REST API layer
- MCP Server is thin protocol adapter (no business logic)
- MCP translates protocol calls to REST API HTTP calls
- Single source of truth for business logic

**AD-2: FalkorDB for Resource Graph**
- All resource relationships and metadata stored in FalkorDB
- FalkorDB is single source of truth for inventory
- Redis-based, in-memory with persistence
- Graph schema: Nodes (Tenant, Project, Resource, ServiceType), Relationships (OWNS, CONTAINS, DEPENDS_ON, TAGGED_WITH, INSTANCE_OF)

**AD-3: Dual Tagging System**
- **Control-Plane Tags:** Stored in FalkorDB, apply to ALL resources, used for project grouping
- **Native MiniStack Tags:** Stored in MiniStack via AWS APIs, apply to taggable services only (S3, EC2), used for AWS CLI/SDK compatibility
- Write-through strategy: control-plane tags always in FalkorDB, native tags in both

**AD-4: Server-Sent Events (SSE) for Real-time Updates**
- Real-time updates from control-plane to Web UI use SSE
- Server→client streaming (not bidirectional WebSocket)
- Built-in reconnect mechanism
- FastAPI SSE endpoints
- Event types: RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_DELETED, DEPENDENCY_ADDED, DEPENDENCY_REMOVED, TAGS_UPDATED

**AD-5: Python Backend with FastAPI**
- Backend written in Python 3.11+ using FastAPI 0.104+
- boto3 for AWS SDK integration
- Type hints mandatory (mypy compliance)
- Async/await patterns for all I/O operations

**AD-6: Multi-Tenant Isolation by Access Key**
- Tenants identified by 12-digit MiniStack access key
- Every resource has `tenant_id` property
- All queries filter by tenant
- UI has tenant selector dropdown
- MiniStack access key = tenant boundary (no cross-tenant leakage)

**AD-7: AWS Console Clone UI Paradigm**
- Web UI replicates AWS Console information architecture
- Service pages structured like AWS Console equivalents
- Consistent with AWS terminology
- Familiar layouts: list→detail→create pattern
- AWS-inspired color scheme (blue header, white content, orange CTAs)

**AD-8: Resource Polling Strategy**
- Background poller runs on 30s interval (configurable)
- Incremental updates only (detect changes, not full scan)
- Detects MiniStack restarts via health check endpoint
- Full re-sync on restart detection

**AD-9: MCP Comprehensive Capabilities**
- **Phase 1:** Basic CRUD (create/update/delete resources) + Bulk operations
- **Phase 2:** Troubleshooting (`diagnose_access_issue`), Templating (`clone_project`), Audit (`get_recent_changes`)
- AI assistants as first-class operators (not just observers)

**AD-10: Docker-First Deployment**
- Primary deployment via Docker Compose
- Docker Compose includes: MiniStack + FalkorDB + Control-Plane API + MCP Server + Web UI
- Single `docker-compose up` command
- Standalone binary deferred to Phase 2

**AD-11: Hybrid Schema Evolution Strategy**
- **Core Structure (Fixed):** Node types and relationships are stable, changes require migration script
- **Resource Metadata (Flexible):** Each Resource node has JSON `state` property with no schema enforcement
- **New Service Types (Additive):** ServiceType nodes added as services implemented, forward-compatible
- **Structural Changes (Rare):** Migration scripts only for core structure changes, document in `.harness/decisions/`

**AD-12: Hybrid Polling Error Handling**
- **Retry Logic (Transient Failures):** 2 retries per poll cycle with exponential backoff (1s, 2s)
- **Staleness Marker (Persistent Issues):** After 3 consecutive failures (90 seconds), mark resources as "stale" with yellow badge in UI
- **Alert System (Critical Failures):** After 5 consecutive failures (2.5 minutes), show UI alert banner with "Retry Now" button
- **Auto-Recovery Detection:** Clear stale markers on successful poll, detect restart via health check, full re-sync on recovery

**AD-13: Transactional Checkpoint for MCP Bulk Operations**
- **Phase 1 (Begin):** `bulk_create_stack_begin(resources)` creates resources sequentially with checkpoints
- **Phase 2 (Action):** AI chooses: `confirm` (keeps created), `rollback` (deletes all), `continue` (retries from checkpoint)
- **Auto-Cleanup:** Transactions expire after 5 minutes if not confirmed/rolled back, auto-rollback to prevent orphaned resources
- **Transaction State:** Stored in FalkorDB with created resource IDs for rollback, transaction log for audit

**AD-14: Hybrid LocalStorage for UI State Persistence**
- **Store in LocalStorage:** Selected tenant ID, active filters, table sorting, view preferences, last visited page
- **Auto-Clear Rules:** Tenant change clears tenant-specific filters, service switch clears service-specific filters, manual reset button, expired state (>30 days) auto-cleared
- **Namespace by Tenant:** Key format `ministack-console:{tenant-id}:{setting}` prevents filter bleed
- **Graceful Degradation:** Fall back to in-memory state if LocalStorage unavailable
- **User Controls:** "Reset to Defaults" button, clear indication when filters applied, toast notification on restore

**AD-15: PyInstaller Standalone Binary Packaging (Phase 2)**
- **Backend Packaging:** Package FastAPI backend with PyInstaller, bundle all Python dependencies, embed React static build
- **FalkorDB Handling:** Bundle separate FalkorDB binary, start as subprocess, alternative: embedded Redis fork or SQLite with graph extensions
- **Static File Serving:** React build embedded in PyInstaller bundle, FastAPI serves from embedded resources
- **Build Process:** Automated builds via GitHub Actions, platform-specific binaries (macOS arm64/x86_64, Linux x86_64, Windows x86_64)
- **Size Optimization:** Strip debug symbols, compress with UPX, target ~80-100MB

### UX Design Requirements

No separate UX design document exists. PRD specifies:
- **UI Paradigm:** AWS Console clone (see AD-7)
- **Information Architecture:** Service navigation (left sidebar), list→detail→create pattern
- **Visual Design:** AWS-inspired color scheme (blue header, white content, orange CTAs)
- **Terminology:** AWS terms (Bucket, Function, Table, etc.)
- **Layout Density:** Table layouts matching AWS Console density
- **Accessibility:** WCAG 2.1 AA compliance (keyboard navigation, screen reader support)

All UX requirements are embedded in FR-5 through FR-9 (Web UI sections).

### FR Coverage Map

**Phase 1 MVP Coverage:**

| FR | Requirement | Epic | Stories |
|----|-------------|------|---------|
| FR-1 | Resource Inventory System | Epic 1 | MSCL-2 |
| FR-2 | Resource Graph | Epic 1 | MSCL-1, MSCL-5 |
| FR-3 | Multi-Tenant Support | Epic 1 | MSCL-3 |
| FR-4 | Project Tagging | Epic 1 | MSCL-4, Epic 6 (MSCL-24) |
| FR-5 | Service Dashboards (S3) | Epic 2 | MSCL-8, MSCL-9, MSCL-10 |
| FR-5 | Service Dashboards (Lambda) | Epic 3 | MSCL-11, MSCL-12, MSCL-13 |
| FR-5 | Service Dashboards (DynamoDB) | Epic 4 | MSCL-14, MSCL-15, MSCL-16 |
| FR-6 | Resource Explorer | Epic 6 | MSCL-22 |
| FR-7 | Resource Graph Visualization | Epic 6 | MSCL-23 |
| FR-8 | Project Management UI | Epic 6 | MSCL-24 |
| FR-10 | MCP Server Core | Epic 5 | MSCL-17 |
| FR-11 | MCP Resources (Read Operations) | Epic 5 | MSCL-18 |
| FR-12 | MCP Tools (Write Operations) | Epic 5 | MSCL-19, MSCL-20, MSCL-21 |

**Phase 2 Deferred:**
- FR-9: Tenant Management UI (Priority P2)
- FR-13: MCP Prompts (Priority P2)
- FR-14: Extended Service Coverage (Priority P2)

**Architecture Decisions Coverage:**
- AD-1 to AD-15: All covered across stories (see individual story files for AD references)

## Epic List

### Epic 1: Control-Plane Foundation
Users can view and track all MiniStack resources across tenants and projects with automatic real-time updates.
**FRs covered:** FR-1, FR-2, FR-3, FR-4
**Stories:** MSCL-1 through MSCL-7 (7 stories, 39 story points)

### Epic 2: S3 Service Management
Users can fully manage S3 buckets and objects through an AWS Console-style interface.
**FRs covered:** FR-5 (S3 portion)
**Stories:** MSCL-8 through MSCL-10 (3 stories, 21 story points)

### Epic 3: Lambda Service Management
Users can fully manage Lambda functions through an AWS Console-style interface.
**FRs covered:** FR-5 (Lambda portion)
**Stories:** MSCL-11 through MSCL-13 (3 stories, 18 story points)

### Epic 4: DynamoDB Service Management
Users can fully manage DynamoDB tables through an AWS Console-style interface.
**FRs covered:** FR-5 (DynamoDB portion)
**Stories:** MSCL-14 through MSCL-16 (3 stories, 18 story points)

### Epic 5: AI Assistant Integration (MCP Server)
AI assistants can query and manage MiniStack resources via natural language, enabling environment-aware code generation.
**FRs covered:** FR-10, FR-11, FR-12
**Stories:** MSCL-17 through MSCL-21 (5 stories, 28 story points)

### Epic 6: Resource Discovery & Project Management
Users can efficiently search, filter, visualize, and manage resources across projects.
**FRs covered:** FR-6, FR-7, FR-8
**Stories:** MSCL-22 through MSCL-25 (4 stories, 21 story points)

## Summary Statistics

**Total Phase 1 MVP:**
- 6 Epics
- 25 Stories
- 145 Story Points
- 13 Functional Requirements covered
- All 15 Architecture Decisions addressed
