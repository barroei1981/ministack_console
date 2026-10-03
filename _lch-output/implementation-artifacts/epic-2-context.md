# Epic 2 Context: S3 Service Management

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Enable developers to fully manage S3 buckets and objects through an AWS Console-style interface. This epic delivers complete CRUD operations for S3 resources with visual bucket browsing, file upload/download, metadata editing, and pre-signed URL generation. By providing a familiar AWS Console experience for S3 management, developers can inspect and manipulate S3 resources without touching the AWS CLI, reducing context-switching and improving local development productivity.

## Stories

- MSCL-8: S3 Backend CRUD Operations
- MSCL-9: S3 UI - Bucket Management
- MSCL-10: S3 UI - Object Browser

## Requirements & Constraints

**Service Coverage:**
S3 is one of the guaranteed MVP top-3 services. Full CRUD management is required at launch.

**User Experience:**
The S3 interface must replicate the AWS Console information architecture and interaction patterns. Developers already familiar with AWS Console should feel at home.

**S3-Specific Functional Requirements:**
- Bucket browser with folder navigation (simulated S3 prefixes)
- File upload with drag-and-drop support
- File download
- Object metadata editor (content-type, cache-control, custom metadata)
- Pre-signed URL generation for temporary access
- Bucket versioning management
- Tagging support (both control-plane and native AWS tags)

**General Service Dashboard Requirements (apply to all services):**
- List view with search/filter (by name, tags, project, tenant)
- Create form with all required parameters
- Detail view showing full resource configuration
- Update capabilities (where supported by AWS API)
- Delete with confirmation
- Real-time updates via SSE events

**Multi-Tenant Isolation:**
All S3 operations must respect tenant boundaries. Buckets are tenant-scoped via the 12-digit MiniStack access key. Cross-tenant bucket access is prohibited.

**Performance:**
UI must load in <2s. API responses for list operations must return in <500ms for up to 1000 buckets.

**Resource Graph Integration:**
S3 buckets must be added to the FalkorDB resource graph with Resource nodes (type: "s3:bucket"). Dependencies (e.g., Lambda → S3, IAM Policy → S3) must be detected and stored as DEPENDS_ON relationships.

## Technical Decisions

**AD-1: REST API as Core Backend**
All S3 business logic resides in the REST API layer. MCP Server (Epic 5) will translate MCP protocol calls to REST API calls with no duplicate logic.

**AD-2: FalkorDB for Resource Graph**
S3 bucket metadata, control-plane tags, and relationships are stored in FalkorDB. FalkorDB is the single source of truth for the resource inventory. Bucket state changes (create/delete/update) must dual-write to both MiniStack (via boto3) and FalkorDB.

**AD-3: Dual Tagging System**
- Control-Plane Tags: Stored in FalkorDB, apply to all S3 buckets, used for project grouping.
- Native MiniStack Tags: Stored in MiniStack via boto3 `put_bucket_tagging`, compatible with AWS CLI/SDK queries, used for AWS-native tooling.

**AD-4: Server-Sent Events for Real-time Updates**
S3 resource changes (bucket created, deleted, versioning updated) must emit SSE events: RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_DELETED. The Web UI subscribes to SSE streams to auto-refresh without polling.

**AD-5: Python Backend with FastAPI**
S3 service implementation uses Python 3.11+, FastAPI async patterns, and boto3 for AWS SDK integration. All code must use type hints and async/await for I/O operations.

**AD-6: Multi-Tenant Isolation by Access Key**
S3 boto3 client is created with the tenant's 12-digit access key as `aws_access_key_id`. Each tenant sees only their own buckets. All S3 API operations filter by tenant_id.

**AWS SDK Integration:**
Use boto3 S3 client with `endpoint_url='http://localhost:4566'` to connect to MiniStack. Standard AWS S3 API operations: `create_bucket`, `list_buckets`, `delete_bucket`, `put_bucket_versioning`, `get_bucket_versioning`, `put_bucket_tagging`, `get_bucket_tagging`.

**FalkorDB Resource Schema:**
S3 buckets are represented as Resource nodes with:
- `id`: "s3-bucket-{name}"
- `type`: "s3:bucket"
- `name`: bucket name
- `tenant_id`: owning tenant's 12-digit access key
- `arn`: "arn:aws:s3:::{name}"
- `state`: JSON blob with bucket configuration (versioning status, region, object count)
- `created_at`, `updated_at`: ISO 8601 timestamps

**Observability:**
All S3 operations must log using structured logging (OPERATIONAL, SECURITY, AUDIT types). OpenTelemetry traces must be emitted for create/delete/update operations. Logs must include tenant_id, bucket_name, and operation type.

## UX & Interaction Patterns

**AWS Console Clone Paradigm:**
Replicate AWS S3 Console layouts and terminology. Use the list→detail→create navigation pattern familiar from AWS Console.

**Visual Design:**
AWS-inspired color scheme: blue header, white content area, orange CTAs (Create Bucket, Upload File).

**Bucket List View:**
Table layout with columns: Name, Created Date, Region, Versioning, Tags, Actions. Search bar at top. Filters for tenant, project, tags. Pagination for >100 buckets.

**Bucket Detail View:**
Tabs: Overview, Objects, Permissions, Properties, Tags. Overview shows bucket configuration. Objects tab shows file browser with folder navigation. Properties tab shows versioning, tagging, lifecycle rules.

**Object Browser:**
Breadcrumb navigation for folder paths (S3 prefixes). File upload via drag-and-drop or file picker. File download on click. Context menu for delete, metadata edit, generate pre-signed URL.

**Real-time Feedback:**
Toast notifications for success/error (e.g., "Bucket created successfully"). SSE-driven auto-refresh when resources change (no manual page refresh needed).

**Accessibility:**
WCAG 2.1 AA compliance. Keyboard navigation support. Screen reader support for all interactive elements.

## Cross-Story Dependencies

**Within Epic 2:**
- MSCL-8 provides the backend API foundation (REST endpoints, S3 service layer)
- MSCL-9 builds the bucket management UI (list, create, delete, versioning) consuming MSCL-8 APIs
- MSCL-10 builds the object browser UI (upload, download, metadata) consuming MSCL-8 APIs

**Dependencies on Epic 1:**
- MSCL-1: FalkorDB schema must exist (Resource nodes, DEPENDS_ON relationships)
- MSCL-2: Resource polling infrastructure (not used by S3 directly, but exists in codebase)
- MSCL-3: Tenant isolation middleware (must be in place for S3 API routes)
- MSCL-4: Dual tagging system (control-plane tags + native tags infrastructure)
- MSCL-6: FastAPI foundation (app setup, middleware, health endpoints)
- MSCL-7: SSE event bus (S3 operations emit events)

**Impact on Epic 5:**
- MCP Server (MSCL-17+) will expose S3 operations via MCP tools (e.g., `list_s3_buckets`, `create_s3_bucket`)
- MCP Server will translate MCP calls to the REST API endpoints built in MSCL-8

**No blocking dependencies from other epics.** Epic 2 can proceed independently once Epic 1 (Control-Plane Foundation) is complete.
