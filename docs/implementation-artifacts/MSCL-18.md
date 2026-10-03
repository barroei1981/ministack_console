# Story MSCL-18: MCP Resources (Read Operations)

**Epic:** Epic 5 - AI Assistant Integration (MCP Server)  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-17

## User Story

As an **AI assistant**,  
I want **to query MiniStack resources via MCP Resources**,  
So that **I can understand the current environment state**.

## Acceptance Criteria

**Given** I query `ministack://tenants`  
**When** the request is processed  
**Then** I receive a list of all tenants with their IDs and resource counts

**Given** I query `ministack://tenant/{tenant_id}/resources`  
**When** the request is processed  
**Then** I receive all resources for that tenant  
**And** resources are formatted as JSON per MCP spec

**Given** I query `ministack://resources/s3/buckets?tenant_id={id}`  
**When** the request is processed  
**Then** I receive all S3 buckets for that tenant

**Given** I query `ministack://resource/{resource_id}/dependencies`  
**When** the request is processed  
**Then** I receive all resources that the specified resource depends on  
**And** dependency types are included

**Architecture Decisions:** AD-1 (MCP calls REST API), AD-9 (MCP Resources for read)

## Alignment

- **Epic**: Epic 5 - AI Assistant Integration (MCP Server)
- **PRD requirement**: FR-10 (MCP Server Core), FR-11 (MCP Resources Read Operations)
- **Architecture constraint**: AD-1 (MCP thin adapter over REST API), AD-9 (MCP Resources for read)
- **ADRs in scope**: AD-1, AD-9
- **Reuse decision**: Extended MSCL-17 foundation with resources.py (API client functions) and server.py (MCP protocol implementation)
- **Cross-layer contract**: MCP server calls REST API endpoints - verified against api/routes/* files
- **Confirmed consistent**: YES - MCP server acts as thin adapter over REST API (AD-1)

## Outcome

- **Delivered**:
  - mcp_server/resources.py - Async HTTP client functions for all read operations:
    - list_tenants() - GET /api/tenants
    - list_tenant_resources(tenant_id) - GET /api/tenants/{id}/resources
    - list_s3_buckets(tenant_id) - GET /api/resources/s3/buckets
    - list_lambda_functions(tenant_id) - GET /api/resources/lambda/functions
    - list_dynamodb_tables(tenant_id) - GET /api/resources/dynamodb/tables
    - get_resource_dependencies(resource_id, tenant_id) - GET /api/resources/{id}/dependencies
    - search_resources(query, tenant_id, service_type) - GET /api/search/resources
    - get_resource_graph(tenant_id, service_type) - GET /api/graph/resources
  - mcp_server/server.py - MCP protocol server implementation:
    - list_resources_handler() - Returns 8 MCP Resource objects
    - read_resource_handler(uri) - Routes URIs to appropriate API calls
    - main() - Server entry point with stdio transport
    - URI routing: ministack://tenants, ministack://tenant/{id}/resources, etc.
    - Query parameter parsing for filters (tenant_id, service_type, q)
  - Extended pyproject.toml with httpx dependency
  
- **PRD coverage**: FR-11 (MCP Resources Read Operations) fully satisfied
- **Architecture impact**: None - follows AD-1 (thin adapter pattern)
- **Deferred**: None - all ACs satisfied
- **Risks introduced**: None

**Wiring**:
- MCP server reads config.api_base_url from environment (defaults to http://localhost:8000)
- All resource functions use httpx.AsyncClient to call REST API
- MCP read_resource_handler() routes URIs to resource functions
- Server runs via stdio transport (MCP standard)
