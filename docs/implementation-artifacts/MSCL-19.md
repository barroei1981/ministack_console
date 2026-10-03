# Story MSCL-19: MCP Tools - S3 CRUD Operations

**Epic:** Epic 5 - AI Assistant Integration (MCP Server)  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-17, MSCL-8

## User Story

As an **AI assistant**,  
I want **to create, update, and delete S3 buckets via MCP Tools**,  
So that **I can set up infrastructure on behalf of users via natural language**.

## Acceptance Criteria

**Given** I invoke `create_s3_bucket` tool with parameters: name, tenant_id, project, versioning  
**When** the tool executes  
**Then** a new S3 bucket is created in MiniStack  
**And** the bucket is added to FalkorDB  
**And** I receive a success response with bucket details

**Given** I invoke `delete_s3_bucket` tool with parameters: name, tenant_id, force  
**When** the tool executes  
**Then** the bucket is deleted from MiniStack  
**And** the bucket is removed from FalkorDB  
**And** I receive a confirmation response

**Given** I invoke a tool with invalid parameters  
**When** the tool validates the input  
**Then** I receive a clear error message  
**And** the error explains what's wrong

**Architecture Decisions:** AD-1 (MCP calls REST API), AD-9 (MCP Tools for write), FR-12 (MCP Full CRUD)

## Alignment

- **Epic**: Epic 5 - AI Assistant Integration (MCP Server)
- **PRD requirement**: FR-12 (MCP Tools Write Operations - Full CRUD)
- **Architecture constraint**: AD-1 (MCP calls REST API), AD-9 (MCP Tools for write)
- **ADRs in scope**: AD-1, AD-9
- **Reuse decision**: Extended mcp_server/tools.py with S3 create/delete operations calling REST API
- **Cross-layer contract**: MCP tools call POST/DELETE /api/resources/s3/buckets - verified against api/routes/resources.py
- **Confirmed consistent**: YES - follows thin adapter pattern (AD-1)

## Outcome

- **Delivered**:
  - mcp_server/tools.py - S3 CRUD operations:
    - create_s3_bucket(name, tenant_id, project, versioning, encryption)
    - delete_s3_bucket(name, tenant_id, force)
  - mcp_server/server.py - MCP Tool handlers:
    - list_tools_handler() - Returns Tool definitions with JSON schemas
    - call_tool_handler(name, arguments) - Routes tool calls to functions
    - Error handling with HTTP status codes
  - Tool input schemas with validation and defaults
  
- **PRD coverage**: FR-12 (S3 portion) fully satisfied
- **Architecture impact**: None - follows AD-1 (thin adapter)
- **Deferred**: None
- **Risks introduced**: None

**Wiring**:
- Tools registered via @app.list_tools() and @app.call_tool()
- Each tool maps to async function in tools.py
- HTTP errors propagated to MCP client with clear messages
