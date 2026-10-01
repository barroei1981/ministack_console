# Product Requirements Document: MiniStack Console

**Project:** ministack_console  
**Version:** 1.5 (FINAL)  
**Date:** 2026-10-01  
**Status:** Ready for Approval  
**Owner:** Product Management  

---

## 1. Overview

### 1.1 Product Vision

MiniStack Console is a **dual-interface control-plane** for MiniStack, the open-source AWS emulator. It provides both **human developers** and **AI assistants** with complete visibility and management capabilities for local AWS development environments.

### 1.2 Problem Statement

**Current State:**
- MiniStack (https://github.com/ministackorg/ministack) emulates 60+ AWS services on localhost:4566
- Developers must use AWS CLI, boto3, or Terraform for ALL operations
- NO web UI or visual management tools
- NO resource-to-project-to-tenant tracking
- AI assistants (Claude, GPT, etc.) are **blind** to local dev environment state
- Context switching between "what exists?" (manual inspection) and "write code" (AI assistance)

**Pain Points:**
1. **Developer Experience:** No AWS Console equivalent for local development
2. **AI Development:** AI assistants generate code based on assumptions, not reality
3. **Multi-tenancy:** No tracking of which resources belong to which tenant/project
4. **Resource Discovery:** No way to visualize dependencies (which Lambda uses which SQS queue)
5. **Debugging:** Hard to inspect CloudWatch logs, SES emails, SNS messages without CLI

### 1.3 Solution

Build a **control-plane with dual interfaces**:

**Human Interface (Web UI):**
- Full CRUD management console for all 60+ MiniStack services
- AWS Console-like experience for local development
- Visual dashboards, resource management, log inspection
- Project and tenant management

**AI Assistant Interface (MCP Server):**
- Expose control-plane state via Model Context Protocol (MCP)
- Enable AI assistants to query AND manage environment state (full CRUD)
- AI assistants as first-class operators, not just observers
- Create, update, delete resources via natural language commands
- Provide context-aware code generation and infrastructure setup
- Resource and relationship queries

**Core Innovation:**
Central control-plane maintains a **resource graph** tracking:
- Tenant → Project → Resources
- Resource dependencies (Lambda → SQS, S3 → IAM policies)
- Single source of truth for both humans and AI

### 1.4 Strategic Goals

1. **Developer Productivity:** Reduce time spent inspecting local AWS resources by 70%
2. **AI-Assisted Development:** Enable environment-aware AI code generation
3. **Open Source Leadership:** First comprehensive management console for local AWS emulation
4. **Developer Adoption:** 10,000 developers using MiniStack Console within 12 months of release

---

## 2. Success Criteria

### 2.1 Launch Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Service Coverage** | 20+ services at launch | Count of services with full CRUD UI |
| **MCP Adoption** | 1,000 AI-assisted sessions in first month | MCP server connection logs |
| **MCP Write Operations** | 100+ successful resource creations via MCP in first month | MCP write operation audit logs |
| **Developer Usage** | 5,000 MAU (Monthly Active Users) | Analytics tracking |
| **Resource Graph Accuracy** | >95% correct dependency mapping | Automated validation tests |
| **Performance** | UI loads in <2s, MCP queries <500ms | Performance monitoring |
| **Documentation** | 100% API coverage, 50+ use case examples | Doc coverage report |

### 2.2 User Satisfaction Metrics

- **NPS Score:** >40 within 6 months
- **GitHub Stars:** 2,000+ stars within first year
- **Support Tickets:** <10 critical bugs per month after launch
- **AI Context Accuracy:** 90% of AI-generated code runs without modification (measured via user surveys)

---

## 3. User Personas

### 3.1 Primary Persona: Full-Stack Developer (Alex)

**Profile:**
- Builds microservices locally using MiniStack
- Uses Lambda, S3, DynamoDB, SQS daily
- Wants visual tools like AWS Console for local dev
- Currently switches between terminal (AWS CLI) and code editor constantly

**Goals:**
- Quickly inspect S3 bucket contents without CLI commands
- Visualize SQS message flow and dead-letter queues
- Debug Lambda function logs in a readable format
- Manage IAM policies visually

**Pain Points:**
- Typing `aws s3 ls --endpoint-url=http://localhost:4566` repeatedly
- No visual confirmation of resource creation
- Hard to understand resource relationships

**Success:** Can manage all MiniStack resources without touching AWS CLI

### 3.2 Secondary Persona: AI-Assisted Developer (Jordan)

**Profile:**
- Uses Claude/GPT-4 for code generation
- Works on complex multi-service architectures
- Frustrated when AI generates code for resources that don't exist

**Goals:**
- AI assistant knows which S3 buckets already exist
- AI generates Lambda code that uses actual SQS queue names
- AI can create complete infrastructure stacks via natural language
- Context-aware infrastructure-as-code generation
- Say "Claude, set up a microservice with S3, SQS, Lambda, DynamoDB" and AI executes it

**Pain Points:**
- AI asks "what resources exist?" → manual listing → copy/paste to AI
- AI generates code with placeholder names ("my-bucket-123")
- Disconnect between environment reality and AI assumptions
- After AI generates code, developer must manually create resources via CLI

**Success:** AI assistant queries MCP server, knows actual environment state, AND can create/modify/delete resources directly

### 3.3 Tertiary Persona: DevOps Engineer (Morgan)

**Profile:**
- Manages multi-tenant MiniStack environments
- Needs to track which resources belong to which project/team
- Responsible for environment cleanup and cost visibility

**Goals:**
- Tenant isolation and resource tracking
- Bulk operations (delete all resources in project X)
- Audit trail of resource changes

**Pain Points:**
- No tenant/project tagging in MiniStack
- Manual resource tracking in spreadsheets
- Hard to clean up orphaned resources

**Success:** Complete visibility and control over multi-tenant environments

---

## 4. Functional Requirements

### 4.1 Control-Plane Core (CRITICAL PATH)

#### FR-1: Resource Inventory System
**Priority:** P0  
**Description:** Central inventory of all MiniStack resources across all services and tenants.

**Acceptance Criteria:**
- [ ] Poll MiniStack API every 30 seconds for resource state
- [ ] Store resource metadata: type, ID, name, tenant, project, tags, created_at
- [ ] Support incremental updates (not full re-scan each poll)
- [ ] Handle MiniStack restarts gracefully (detect and re-inventory)
- [ ] Track resource lifecycle: created, modified, deleted

**Technical Notes:**
- Use MiniStack Internal API (`/_ministack/*`) for bulk queries where available
- Fall back to standard AWS SDK calls per service

#### FR-2: Resource Graph
**Priority:** P0  
**Description:** Directed graph showing dependencies between resources.

**Acceptance Criteria:**
- [ ] Detect Lambda → S3 dependencies (via environment variables, IAM policies)
- [ ] Detect Lambda → SQS/SNS dependencies (event source mappings)
- [ ] Detect S3 → IAM policy relationships
- [ ] Detect CloudFormation stack → managed resources
- [ ] Graph updates in real-time as resources change
- [ ] Query: "What depends on resource X?" returns accurate list
- [ ] Query: "What does resource Y depend on?" returns accurate list

**Technical Notes:**
- Graph stored in memory with periodic snapshots to disk
- Use graph database (e.g., Neo4j) or in-memory graph library

#### FR-3: Multi-Tenant Support
**Priority:** P0  
**Description:** Isolate resources by tenant (12-digit MiniStack access key = tenant ID).

**Acceptance Criteria:**
- [ ] Detect tenant from AWS access key in MiniStack requests
- [ ] UI: Tenant selector dropdown (list all tenants)
- [ ] UI: Filter all resources by selected tenant
- [ ] MCP: `ministack://tenant/{id}` resource queries
- [ ] Prevent cross-tenant data leakage

#### FR-4: Project Tagging
**Priority:** P1  
**Description:** Allow users to tag resources with project names for logical grouping.

**Acceptance Criteria:**
- [ ] UI: Assign project to any resource
- [ ] UI: Filter resources by project
- [ ] MCP: `ministack://project/{name}/resources` query
- [ ] Support multiple projects per tenant
- [ ] Tag propagation: when CloudFormation creates resources, inherit project tag

---

### 4.2 Web UI - Human Interface

#### FR-5: Service Dashboards (Top 10 Services)
**Priority:** P0  
**Description:** Full CRUD management for the 10 most-used MiniStack services.

**Services (Priority Order):**

**Guaranteed MVP (Top 3):**
1. **S3** - Bucket management, object browser, uploads
2. **Lambda** - Function list, code view, logs, test invocation
3. **DynamoDB** - Table browser, item CRUD, query/scan

**Community-Driven (Services 4-5 - To Be Voted):**
- **Candidates:** SQS, CloudWatch Logs, IAM, SNS, EC2, RDS, ECS
- **Selection Method:** Early adopter survey + GitHub community vote

**Phase 2 (Services 6-10):**
6. **IAM** - User/role/policy management, policy editor
7. **SNS** - Topic management, subscription management, message publishing
8. **EC2** - Instance management, start/stop/terminate
9. **RDS** - Database instance management, connection info
10. **ECS** - Cluster/service/task management

**Acceptance Criteria (Per Service):**
- [ ] **List View:** Table showing all resources of this type
- [ ] **Create:** Form to create new resource with all required parameters
- [ ] **Read:** Detail view showing full resource configuration
- [ ] **Update:** Edit resource configuration (where supported by AWS API)
- [ ] **Delete:** Delete resource with confirmation
- [ ] **Search/Filter:** Search by name, filter by tags/project/tenant
- [ ] **Real-time Updates:** Auto-refresh when resources change (WebSocket or polling)

**S3-Specific Requirements:**
- [ ] Bucket browser with folder navigation
- [ ] File upload (drag-and-drop)
- [ ] File download
- [ ] Object metadata editor
- [ ] Pre-signed URL generation

**Lambda-Specific Requirements:**
- [ ] Inline code editor (read-only view)
- [ ] Test event invocation
- [ ] CloudWatch Logs integration (view logs inline)
- [ ] Environment variable editor

**DynamoDB-Specific Requirements:**
- [ ] Table schema viewer
- [ ] Item browser with pagination
- [ ] Query builder (partition key + sort key)
- [ ] Scan with filters
- [ ] Item JSON editor (create/update)

#### FR-6: Resource Explorer
**Priority:** P1  
**Description:** Global search and navigation across all resources.

**Acceptance Criteria:**
- [ ] Full-text search across all resource names/IDs
- [ ] Filter by service type, tenant, project, tags
- [ ] Quick navigation to any resource detail page
- [ ] Recent resources list (last 20 accessed)
- [ ] Favorites/bookmarks

#### FR-7: Resource Graph Visualization
**Priority:** P1  
**Description:** Visual graph showing resource dependencies.

**Acceptance Criteria:**
- [ ] Interactive graph view (zoom, pan, click nodes)
- [ ] Highlight dependencies: "Select resource → highlight connected resources"
- [ ] Color-code by service type
- [ ] Filter graph by tenant/project
- [ ] Export graph as image (PNG/SVG)

#### FR-8: Project Management UI
**Priority:** P1  
**Description:** Create, edit, and manage projects.

**Acceptance Criteria:**
- [ ] Projects list page
- [ ] Create project form (name, description, tenant)
- [ ] Project detail page: all associated resources
- [ ] Bulk operations: "Delete all resources in project X"
- [ ] Project dashboard: resource counts by service type

#### FR-9: Tenant Management UI
**Priority:** P2  
**Description:** Manage multiple MiniStack tenants/accounts.

**Acceptance Criteria:**
- [ ] Tenants list page (all 12-digit access keys)
- [ ] Tenant detail page: projects, resource counts
- [ ] Tenant switcher in header (persistent across sessions)
- [ ] Per-tenant resource limits and quotas display

---

### 4.3 MCP Server - AI Assistant Interface

#### FR-10: MCP Server Core
**Priority:** P0  
**Description:** Implement Model Context Protocol server for AI assistant integration.

**Acceptance Criteria:**
- [ ] MCP server runs on configurable port (default: 3100)
- [ ] Supports MCP protocol v1.0 (https://spec.modelcontextprotocol.io/)
- [ ] Authentication: API key-based (generate keys in UI)
- [ ] Rate limiting: 1000 requests/minute per API key
- [ ] Logging: All queries logged for debugging

**Technical Notes:**
- Use official MCP SDK for Python or TypeScript
- Run as separate process or embedded in control-plane backend

#### FR-11: MCP Resources - Read Operations
**Priority:** P0  
**Description:** Expose MiniStack resources as MCP resources for AI queries.

**MCP Resources (Priority Order):**

```
ministack://tenants
  → List all tenants (12-digit IDs)

ministack://tenant/{tenant_id}/resources
  → All resources in a tenant

ministack://tenant/{tenant_id}/projects
  → All projects in a tenant

ministack://project/{project_name}/resources
  → All resources tagged with project

ministack://resources/s3/buckets
  → All S3 buckets across all tenants

ministack://resources/lambda/functions
  → All Lambda functions

ministack://resources/{service_type}
  → All resources of a given service type

ministack://resource/{resource_id}/details
  → Full details of a specific resource

ministack://resource/{resource_id}/dependencies
  → What this resource depends on

ministack://resource/{resource_id}/dependents
  → What depends on this resource
```

**Acceptance Criteria:**
- [ ] All resources return JSON with standard schema
- [ ] Queries filter by tenant/project/tags
- [ ] Queries support pagination (100 items per page)
- [ ] Queries return relationship data (dependencies)
- [ ] Error handling: 404 for non-existent resources, 400 for invalid queries

#### FR-12: MCP Tools - Write Operations (Full CRUD)
**Priority:** P0  
**Description:** Enable AI assistants to create/modify/delete resources via MCP tools. AI assistants become first-class operators of the environment, not just observers.

**MCP Tools (Phase 1 - Top 3 Guaranteed + 2 Community-Voted):**

```
create_s3_bucket(name, tenant_id, project?, versioning?, public_access?)
  → Create S3 bucket with configuration

delete_s3_bucket(name, tenant_id, force=false)
  → Delete S3 bucket (force=true deletes all objects first)

create_lambda_function(name, runtime, code, handler, environment_vars?, tenant_id, project?)
  → Create Lambda function

update_lambda_function(name, code?, handler?, environment_vars?, tenant_id)
  → Update Lambda function code or configuration

delete_lambda_function(name, tenant_id)
  → Delete Lambda function

create_dynamodb_table(name, partition_key, sort_key?, tenant_id, project?)
  → Create DynamoDB table

delete_dynamodb_table(name, tenant_id)
  → Delete DynamoDB table

create_sqs_queue(name, tenant_id, project?, message_retention_seconds?, visibility_timeout?)
  → Create SQS queue

delete_sqs_queue(name, tenant_id)
  → Delete SQS queue

send_sqs_message(queue_name, message_body, tenant_id)
  → Send message to SQS queue

tag_resource(resource_id, project)
  → Tag resource with project name

bulk_create_stack(stack_definition, tenant_id, project)
  → Create multiple resources from JSON definition (e.g., "microservice stack")
```

**Acceptance Criteria:**
- [ ] All tools validate input parameters
- [ ] Create/update/delete tools call MiniStack API and update control-plane inventory immediately
- [ ] Tools return resource ID and details on success
- [ ] Tools return clear error messages on failure with actionable guidance
- [ ] Delete tools require confirmation parameter (safety mechanism)
- [ ] Bulk operations support atomic rollback (all-or-nothing)
- [ ] Audit log: All tool invocations logged with API key, timestamp, parameters, outcome
- [ ] Rate limiting: Max 100 write operations per minute per API key
- [ ] Tools mirror UI capabilities: if UI can do it, MCP can do it

#### FR-13: MCP Prompts - Use Case Templates
**Priority:** P2  
**Description:** Pre-defined prompt templates for common AI use cases.

**MCP Prompts:**

```
"list_environment_state"
  → Summarize all resources in current tenant

"generate_terraform_for_project"
  → Generate Terraform code for all resources in a project

"explain_resource_dependencies"
  → Explain dependency chain for a resource

"suggest_cleanup"
  → Identify unused/orphaned resources
```

**Acceptance Criteria:**
- [ ] Prompts return structured context for AI assistants
- [ ] Prompts support parameters (tenant_id, project_name)
- [ ] Prompts include examples in responses

---

### 4.4 Extended Service Support (Post-MVP)

#### FR-14: Extended Service Coverage
**Priority:** P2  
**Description:** Add full CRUD support for remaining 50+ MiniStack services.

**Service Categories:**

**Infrastructure Services:**
- CloudFormation (stack management, template viewer, drift detection)
- VPC (network management, security groups, subnets)
- Route53 (hosted zones, DNS records)
- ACM (certificate management)
- CloudFront (distribution management)

**Compute Services:**
- ECS (container orchestration)
- EKS (Kubernetes cluster management)
- Batch (job queues, compute environments)

**Data Services:**
- RDS Aurora (cluster management)
- ElastiCache (Redis/Memcached clusters)
- Athena (query execution, result browser)
- Glue (data catalog, job management)

**Analytics & ML:**
- Kinesis (stream management, data viewer)
- EMR (cluster management)
- SageMaker (endpoint management)
- Bedrock (model invocation, prompt testing)

**Acceptance Criteria:**
- [ ] Each service has list/detail/create/delete UI
- [ ] Service-specific features (e.g., CloudFormation drift detection)
- [ ] MCP resources for each service type
- [ ] Service-specific MCP tools where applicable

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Requirement | Target | Critical? |
|-------------|--------|-----------|
| **UI Initial Load** | <2 seconds | Yes |
| **Resource List Load** | <500ms for 1000 resources | Yes |
| **Graph Render** | <1 second for 500 nodes | No |
| **MCP Query Response** | <500ms for simple queries | Yes |
| **MCP Query Response** | <2s for complex graph queries | Yes |
| **Real-time Updates** | <5 seconds latency | No |
| **MiniStack Poll Interval** | 30 seconds (configurable) | No |

### 5.2 Scalability

- **Resources:** Support 10,000 resources per tenant
- **Tenants:** Support 100 tenants simultaneously
- **Concurrent Users (UI):** 50 users
- **Concurrent MCP Connections:** 100 connections
- **Graph Complexity:** 500 nodes, 2000 edges

### 5.3 Reliability

- **Uptime:** 99% (local development tool, not production SLA)
- **Data Persistence:** Resource graph survives control-plane restarts
- **MiniStack Restart Handling:** Detect restart, re-inventory within 1 minute
- **Error Recovery:** UI shows clear error messages, retries failed API calls (3 attempts)

### 5.4 Security

- **MCP Authentication:** API key required for all MCP requests
- **API Key Management:** Generate/revoke keys via UI
- **Audit Logging:** All write operations logged (who, what, when)
- **No External Dependencies:** All data stays local (no cloud services)
- **Secret Handling:** IAM credentials displayed with "show/hide" toggle

### 5.5 Usability

- **Responsive Design:** UI works on desktop (1920x1080) and laptop (1366x768)
- **Accessibility:** WCAG 2.1 AA compliance (keyboard navigation, screen reader support)
- **Error Messages:** Clear, actionable error messages (not raw AWS error codes)
- **Onboarding:** First-time user tutorial (5 minutes)
- **Documentation:** Inline help text for all forms

### 5.6 Compatibility

- **MiniStack Versions:** Support MiniStack 3.0+ (current major version)
- **Browsers:** Chrome 100+, Firefox 100+, Safari 15+, Edge 100+
- **MCP Clients:** Compatible with Claude Desktop, Claude Code, custom MCP clients
- **Operating Systems:** macOS, Linux, Windows (via WSL2)

### 5.7 Deployment

- **Deployment Model:** Docker container or standalone binary
- **Resource Usage:** <500MB RAM, <100MB disk
- **Startup Time:** <10 seconds
- **Configuration:** Single config file (YAML or TOML)
- **Ports:** Configurable (defaults: UI 3000, MCP 3100, API 3001)

---

## 6. Technical Architecture (Reference)

**Note:** Full technical architecture documented in separate architecture document. See `.harness/decisions/2026-10-01-architecture-control-plane-with-mcp.md` for ADR.

**High-Level Layers:**
```
┌─────────────────────────────────┐
│   Web UI (React/Next.js)        │  ← Human interface
├─────────────────────────────────┤
│   MCP Server (thin adapter)     │  ← AI assistant interface (MCP)
├─────────────────────────────────┤
│   REST API (FastAPI)            │  ← Core backend (CRUD operations)
├─────────────────────────────────┤
│   Control-Plane Core (Python)   │  ← Resource graph, inventory
├─────────────────────────────────┤
│   FalkorDB (Graph Storage)      │  ← Resource graph persistence
├─────────────────────────────────┤
│   MiniStack API (localhost:4566)│  ← AWS service emulator
└─────────────────────────────────┘
```

**Key Technical Decisions:**
- **Backend:** Python (FastAPI for REST API)
- **Frontend:** React with TypeScript
- **REST API:** Core backend - consumed by Web UI, MCP Server, and other integrations
- **MCP:** Thin adapter layer over REST API (de-risks MCP adoption)
- **Graph Storage:** FalkorDB (Redis-based graph database via Docker)
- **Real-time:** Server-Sent Events (SSE) for UI live updates
- **AWS Integration:** boto3 for MiniStack API calls

---

## 7. Constraints

### 7.1 External Constraints

- **MiniStack API Limitations:**
  - Some AWS APIs not fully implemented in MiniStack
  - No native support for resource tagging (control-plane must maintain tags separately)
  - Internal API (`/_ministack/*`) may change between MiniStack versions

- **MCP Protocol:**
  - MCP v1.0 spec still evolving (may require updates)
  - Limited AI client support (primarily Claude Desktop/Code initially)

- **Local Development Context:**
  - Must run on developer laptops (resource-constrained)
  - Cannot assume persistent storage (developers reset MiniStack frequently)

### 7.2 Business Constraints

- **Open Source:** Must be MIT-licensed, community-friendly
- **No Cloud Dependencies:** Cannot require AWS account, external APIs, or paid services
- **Zero Configuration:** Should work out-of-box with MiniStack defaults
- **Timeline:** MVP in 3 months, full service coverage in 6 months

### 7.3 Technical Constraints

- **No Database Requirement:** Use in-memory graph + file snapshots (no PostgreSQL/MySQL dependency)
- **Lightweight:** Total deployment <100MB (to fit in Docker image)
- **Backward Compatibility:** Support MiniStack 3.x versions

---

## 8. Out of Scope (V1)

The following are explicitly **not** included in V1:

### 8.1 Real AWS Integration
- ❌ Managing real AWS resources (only MiniStack)
- ❌ Cost estimation (no real costs in MiniStack)
- ❌ AWS billing integration

### 8.2 Advanced Features
- ❌ Multi-user authentication (single-user dev tool)
- ❌ Role-based access control (RBAC)
- ❌ Compliance scanning (no production data)
- ❌ Infrastructure drift detection (beyond resource graph)
- ❌ Automated testing frameworks integration

### 8.3 MiniStack Extensions
- ❌ Modifying MiniStack core (read-only integration)
- ❌ Performance profiling of MiniStack services
- ❌ MiniStack version management/updates

### 8.4 AI Features Beyond MCP
- ❌ AI-powered resource recommendations
- ❌ Natural language query interface (beyond MCP)
- ❌ Anomaly detection in resource usage

### 8.5 Enterprise Features
- ❌ SSO/SAML integration
- ❌ Audit log export to SIEM
- ❌ High availability (HA) deployment
- ❌ Multi-region support (MiniStack is localhost)

---

## 9. Dependencies

### 9.1 External Dependencies

| Dependency | Version | Purpose | Risk |
|------------|---------|---------|------|
| **MiniStack** | 3.0+ | AWS service emulator | LOW - stable open-source project |
| **boto3 (AWS SDK)** | Latest | AWS API calls to MiniStack | LOW - mature SDK |
| **MCP SDK (Python)** | 1.0+ | Model Context Protocol | MEDIUM - evolving spec |
| **FalkorDB** | Latest | Graph database | LOW - Redis-based, stable |
| **FastAPI** | 0.100+ | Python web framework | LOW - mature |
| **React** | 18+ | UI framework | LOW - stable |
| **TypeScript** | 5+ | Type safety | LOW - stable |

### 9.2 Integration Points

- **MiniStack API:** All AWS service endpoints at `localhost:4566`
- **MiniStack Internal API:** `/_ministack/health`, `/_ministack/config`, etc.
- **REST API:** Core backend at `localhost:3001` (consumed by Web UI, MCP Server, CLI, scripts)
- **MCP Clients:** Claude Desktop, Claude Code, custom MCP clients (via MCP Server adapter)
- **Other AI Tools:** OpenAI, Gemini, etc. (via REST API, not MCP)
- **Docker:** Optional containerized deployment

---

## 10. Open Questions

### 10.1 Technical Decisions (RESOLVED)

1. **Graph Storage:** ✅ **DECIDED: FalkorDB (Docker)**
   - **Rationale:** Redis-based graph database with in-memory performance and persistence. Fast native graph traversal. Docker deployment matches MiniStack's model. Team has Graphiti experience with FalkorDB.
   - **Impact:** Performance ✓, persistence ✓, deployment simplicity ✓

2. **Backend Language:** ✅ **DECIDED: Python**
   - **Rationale:** boto3 is mature for AWS interactions. MCP SDK available (`mcp` Python package). DevOps/infrastructure community prefers Python. Good data processing libraries. Strong typing with type hints.
   - **Impact:** AWS SDK maturity ✓, MCP SDK availability ✓, developer ecosystem ✓

3. **Real-time Updates:** ✅ **DECIDED: Server-Sent Events (SSE)**
   - **Rationale:** Simpler than WebSocket (unidirectional server → client). Built-in reconnect logic. Perfect for status updates and resource change notifications. Less overhead. Easy to implement with FastAPI/Flask.
   - **Impact:** UI responsiveness ✓, server resource efficiency ✓, implementation simplicity ✓

### 10.2 Technical Questions (RESOLVED - Continued)

4. **Resource Tagging:** ✅ **DECIDED: Dual Tagging System (Both)**
   - **Rationale:** Support BOTH control-plane tags (internal) and MiniStack native tags (external) - they serve different purposes.
   - **Implementation:**
     - **Control-Plane Tags (Internal):** Stored in FalkorDB. Purpose: Logical organization within console (project grouping, tenant management). Applies to ALL resources, all services. Examples: `project: microservice-a`, `team: backend`, `environment: dev`
     - **MiniStack Native Tags (External):** Stored in MiniStack via AWS APIs. Purpose: AWS-compatible tags for CLI/SDK workflows. Applies to services that support native tagging (S3, EC2, etc.). Examples: `Name: user-uploads`, `CostCenter: engineering`
   - **Why Both:** Control-plane tags for console users (internal organization). Native tags for CLI/SDK users (AWS workflow compatibility). Different audiences, no conflict.
   - **UI Display:** Both tag types shown clearly labeled. Write-through to MiniStack where supported.
   - **Impact:** Tag persistence ✓, MiniStack compatibility ✓, dual storage ✓, supports both use cases ✓

### 10.3 Product Questions (RESOLVED)

1. **Service Prioritization:** ✅ **DECIDED: Flexible Priority (Option C)**
   - **Rationale:** Start with universally-needed top 3 services, let community vote on services 4-5.
   - **Approach:**
     - **Guaranteed MVP (Top 3):** S3 (object storage), Lambda (serverless compute), DynamoDB (NoSQL database)
     - **Community-Driven (Services 4-5):** Launch early preview with top 3. Survey early adopters via GitHub issue. Prioritize services 4-5 based on vote results.
   - **Benefits:** Core services universally needed (no risk). Community engagement validates real user needs. Flexible roadmap adapts to actual usage. No upfront research delay.
   - **Timeline Impact:** None - proceed with top 3 immediately, community vote runs in parallel
   - **Impact:** Development roadmap ✓, user satisfaction ✓, community engagement ✓

### 10.4 Product Questions (RESOLVED - Continued)

2. **MCP Adoption:** ✅ **DECIDED: Hedged Bet (Option D)**
   - **Rationale:** Build both UI and MCP in Phase 1, but de-risk MCP investment with REST API as core backend.
   - **Architecture Mitigation:**
     - **REST API as Core Backend:** All business logic in REST API
     - **MCP Server as Thin Adapter:** MCP wraps REST API, not standalone implementation
     - **Multiple Interface Options:** REST API consumed by: Web UI, MCP Server, other AI tools (OpenAI, etc.), CLI tools, scripts, integrations
   - **De-Risk Strategy:** If MCP adoption strong → MCP is primary AI interface. If MCP adoption slow → REST API allows other integrations. Project succeeds either way.
   - **Architecture:** `Web UI → REST API ← MCP Server (thin adapter) → Control-Plane`
   - **Benefits:** Not betting exclusively on MCP. REST API has value independent of MCP. Maximum flexibility for integrations.
   - **Impact:** MCP investment de-risked ✓, REST API reusability ✓, multiple integration paths ✓

### 10.5 Product Questions (RESOLVED - Continued)

3. **Deployment Model:** ✅ **DECIDED: Multi-Distribution (Option D)**
   - **Rationale:** Offer both Docker and standalone binary for maximum user reach.
   - **Approach:**
     - **Docker Distribution (Primary):** Docker Compose file including MiniStack + Console. One command: `docker-compose up`. Target: Container-native developers, CI/CD environments.
     - **Standalone Binary (Secondary):** Native binaries for macOS/Linux/Windows. Bundled Python backend + static React frontend. Target: Developers without Docker, lightweight setups.
   - **Phased Rollout:** Phase 1 MVP: Docker-only (simplest to build first). Phase 2: Add standalone binary distribution.
   - **Benefits:** Docker users get easiest installation. Non-Docker users still have option. Matches MiniStack's distribution strategy. Maximum user reach.
   - **Maintenance:** Automated build pipelines (GitHub Actions). Docker: multi-stage build. Binary: PyInstaller + bundled React.
   - **Impact:** Distribution ease ✓, installation UX ✓, user reach maximized ✓

### 10.6 Product Questions (RESOLVED - Continued)

4. **Monetization:** ✅ **DECIDED: Deferred Decision (Option E)**
   - **Rationale:** Launch as 100% free open-source, monitor adoption and demand signals, make data-driven decision post-MVP.
   - **Approach:**
     - **MVP Launch (Months 0-3):** 100% free, 100% open-source (MIT license)
     - **Validation Phase (Months 3-12):** Monitor adoption metrics (MAU, GitHub stars, community engagement). Track demand signals (enterprise inquiries, feature requests). Survey community needs and willingness to pay. Observe competitor landscape.
     - **Decision Point (Month 12):** Evaluate sustainability needs. Community feedback on monetization options. Choose model based on data (open-core, SaaS, support, or stay free).
   - **Benefits:** No upfront commitment constrains product direction. Build trust with community first. Data-driven decision based on actual adoption. Maximum flexibility to pivot.
   - **Communication:** Be transparent: "Currently free, may explore sustainability options post-MVP". MIT license ensures core stays open-source. Community involvement in any future monetization decisions.
   - **Impact:** Long-term sustainability decision deferred ✓, community trust prioritized ✓, flexibility maximized ✓

### 10.7 User Research Questions (RESOLVED)

1. **UI Paradigm:** ✅ **DECIDED: AWS Console Clone**
   - **Rationale:** Familiar to target users (AWS developers). Feature-complete from the start. True "AWS Console experience" as promised in vision. Users already know the paradigm - minimal learning curve. Matches user expectation: "AWS Console for local dev".
   - **Approach:** Study AWS Console's information architecture. Replicate familiar layouts and workflows. Service pages structured like AWS Console equivalents. Consistent with AWS terminology and conventions.
   - **Impact:** User familiarity ✓, feature completeness ✓, learning curve minimized ✓

2. **MCP Use Cases:** ✅ **DECIDED: Full (Comprehensive MCP Capabilities)**
   - **Rationale:** Support full range of AI workflows - from basic CRUD to advanced troubleshooting and templating.
   - **MCP Tools to Build:**
     - **Basic CRUD (Phase 1):** create/update/delete individual resources (S3, Lambda, DynamoDB, SQS, etc.)
     - **Bulk Operations (Phase 1):** `bulk_create_stack()` - Multi-resource setups, complete microservice stacks
     - **Troubleshooting (Phase 2):** `diagnose_access_issue()` - Debug dependency and permission issues, resource dependency analysis
     - **Templating (Phase 2):** `clone_project()` - Clone project resources, resource templates and replication
     - **Audit/Monitoring (Phase 2):** `get_recent_changes()` - Recent changes, resource event history
   - **Phased Approach:** Phase 1: Basic CRUD + Bulk operations. Phase 2: Troubleshooting, templating, audit.
   - **Impact:** Comprehensive AI workflow support ✓, phased delivery ✓, full vision realized ✓

---

## 11. Success Metrics (Detailed)

### 11.1 Adoption Metrics

| Metric | 1 Month | 3 Months | 6 Months | 12 Months |
|--------|---------|----------|----------|-----------|
| **GitHub Stars** | 100 | 500 | 1,000 | 2,000 |
| **Monthly Active Users** | 500 | 2,000 | 5,000 | 10,000 |
| **MCP API Calls** | 10k | 50k | 200k | 1M |
| **Docker Pulls** | 1,000 | 5,000 | 20,000 | 50,000 |

### 11.2 Engagement Metrics

- **Daily Active Users (DAU):** 30% of MAU
- **Session Duration:** Average 15 minutes
- **Feature Usage:** 70% of users use UI, 30% use MCP within first month
- **Return Rate:** 60% of users return within 7 days

### 11.3 Quality Metrics

- **Crash Rate:** <1% of sessions
- **Critical Bugs:** <5 open critical bugs at any time
- **Response Time:** 90th percentile <1 second
- **Support Tickets:** <20 tickets per week after launch

---

## 12. Roadmap

### 12.1 Phase 1: MVP (Months 1-3)

**Goal:** Core control-plane + top 3 services (guaranteed) + 2 community-voted services + full CRUD MCP

**Deliverables:**
- Control-plane core (inventory, graph, multi-tenant)
- Web UI for S3, Lambda, DynamoDB (guaranteed) + 2 community-voted services (full CRUD)
- MCP server with read resources AND write tools (full CRUD for all Phase 1 services)
- Project tagging (dual system: control-plane + native)
- Docker deployment
- Audit logging for all MCP write operations
- Community voting mechanism (GitHub issue)

**Success Criteria:**
- 500 MAU
- 50 GitHub stars
- <10 critical bugs
- 50+ successful AI-driven infrastructure setups via MCP in first month

### 12.2 Phase 2: Extended Services (Months 4-6)

**Goal:** Top 10 services + extended MCP coverage + standalone binary

**Deliverables:**
- IAM, SNS, EC2, RDS, ECS UI support (full CRUD)
- MCP write tools expanded to all top 10 services
- Resource graph visualization
- Advanced MCP features: bulk operations, stack templates
- Rollback capabilities for failed operations
- Standalone binary distribution (macOS, Linux, Windows)

**Success Criteria:**
- 2,000 MAU
- 500 GitHub stars
- 10,000 MCP queries/week
- 500+ MCP write operations/week

### 12.3 Phase 3: Full Coverage (Months 7-12)

**Goal:** All 60+ services + advanced features

**Deliverables:**
- Remaining 50+ services
- Advanced graph queries
- Performance optimizations
- Community-contributed service plugins

**Success Criteria:**
- 10,000 MAU
- 2,000 GitHub stars
- Featured on MiniStack homepage

---

## 13. Appendix

### 13.1 Service Inventory (60+ MiniStack Services)

**Core Services (Top 10):**
1. S3 - Object storage
2. Lambda - Serverless compute
3. DynamoDB - NoSQL database
4. SQS - Message queuing
5. CloudWatch Logs - Log aggregation
6. IAM - Identity and access management
7. SNS - Pub/sub messaging
8. EC2 - Virtual machines
9. RDS - Relational databases
10. ECS - Container orchestration

**Infrastructure (15):**
11. CloudFormation - Infrastructure as code
12. VPC - Virtual private cloud
13. Route53 - DNS service
14. ACM - Certificate management
15. CloudFront - CDN
16. CloudTrail - Audit logging
17. EventBridge - Event bus
18. Step Functions - Workflow orchestration
19. API Gateway - API management
20. Secrets Manager - Secret storage
21. Systems Manager - Parameter store
22. KMS - Key management
23. CloudWatch - Metrics and alarms
24. X-Ray - Distributed tracing
25. CodeCommit - Git repositories

**Data & Analytics (10):**
26. RDS Aurora - Managed PostgreSQL/MySQL
27. ElastiCache - Redis/Memcached
28. Athena - SQL queries on S3
29. Glue - Data catalog and ETL
30. Kinesis - Data streaming
31. EMR - Big data processing
32. Redshift - Data warehouse
33. Lake Formation - Data lake management
34. QuickSight - Business intelligence
35. MSK - Managed Kafka

**AI/ML (5):**
36. SageMaker - Machine learning platform
37. Bedrock - Foundation models
38. Comprehend - Natural language processing
39. Rekognition - Image/video analysis
40. Transcribe - Speech-to-text

**Application Integration (10):**
41. AppSync - GraphQL API
42. SES - Email sending
43. Pinpoint - Customer engagement
44. Cognito - User authentication
45. Amplify - App development platform
46. IoT Core - IoT device management
47. IoT Analytics - IoT data analysis
48. MQ - Message broker
49. AppFlow - Data integration
50. Managed Workflows for Apache Airflow

**Additional Services (10+):**
51. Backup - Backup management
52. Batch - Batch computing
53. EBS - Block storage
54. ECR - Container registry
55. EFS - File storage
56. EKS - Managed Kubernetes
57. ElasticBeanstalk - PaaS
58. FSx - Managed file systems
59. Neptune - Graph database
60. QLDB - Ledger database
61. Timestream - Time series database
62. Transfer Family - File transfer

### 13.2 MCP Protocol Overview

**Model Context Protocol (MCP)** is a standard for integrating external data sources with AI assistants.

**Core Concepts:**
- **Resources:** Read-only data sources (URIs like `ministack://resources/s3/buckets`)
- **Tools:** Functions AI can call (like `create_s3_bucket()`)
- **Prompts:** Pre-defined templates for common queries

**Why MCP:**
- Industry standard backed by Anthropic
- Native support in Claude Desktop and Claude Code
- Extensible protocol for custom integrations

**Reference:** https://spec.modelcontextprotocol.io/

### 13.3 Glossary

- **Control-Plane:** Central management layer that maintains resource inventory and graph
- **MiniStack:** Open-source AWS emulator (https://github.com/ministackorg/ministack)
- **MCP:** Model Context Protocol - standard for AI assistant integrations
- **Resource Graph:** Directed graph showing dependencies between AWS resources
- **Tenant:** Isolated environment in MiniStack (identified by 12-digit access key)
- **Project:** Logical grouping of resources within a tenant
- **CRUD:** Create, Read, Update, Delete operations

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-10-01 | Product Management | Initial draft |
| 1.1 | 2026-10-01 | Product Management | Expanded MCP scope to full CRUD (Phase 1). Resolved technical questions: Python backend, FalkorDB storage, SSE real-time updates. |
| 1.2 | 2026-10-01 | Product Management | Resolved remaining questions: Dual tagging system, flexible service priority (top 3 + community vote), MCP hedged bet (REST API core). |
| 1.3 | 2026-10-01 | Product Management | Resolved deployment model: Multi-distribution (Docker Phase 1, standalone binary Phase 2). |
| 1.4 | 2026-10-01 | Product Management | Resolved monetization: Deferred decision (100% free open-source now, evaluate post-MVP Month 12). |
| 1.5 | 2026-10-01 | Product Management | FINAL: Resolved UI paradigm (AWS Console clone) and MCP use cases (full comprehensive capabilities). All open questions answered. |

---

**Approval:**

- [ ] Product Management: _______________  
- [ ] Engineering: _______________  
- [ ] UX Design: _______________  

**Next Steps:**
1. PRD approval (this gate)
2. Architecture review and technical design doc
3. UI/UX mockups (AWS Console-style) for top 3 services
4. Technical spike: MCP SDK evaluation (Python)
5. Community voting mechanism setup (GitHub issue for services 4-5)
