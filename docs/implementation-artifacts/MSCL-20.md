# Story MSCL-20: MCP Tools - Lambda and DynamoDB CRUD Operations

**Epic:** Epic 5 - AI Assistant Integration (MCP Server)  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-17, MSCL-11, MSCL-14

## User Story

As an **AI assistant**,  
I want **to create, update, and delete Lambda functions and DynamoDB tables via MCP Tools**,  
So that **I can provision complete application stacks via natural language**.

## Acceptance Criteria

**Given** I invoke `create_lambda_function` tool with parameters: name, runtime, handler, code (base64), environment variables  
**When** the tool executes  
**Then** a new Lambda function is created in MiniStack  
**And** I receive the function ARN and details

**Given** I invoke `create_dynamodb_table` tool with parameters: name, partition_key, sort_key (optional), billing_mode  
**When** the tool executes  
**Then** a new DynamoDB table is created  
**And** I receive the table ARN and status

**Given** I invoke `delete_lambda_function` or `delete_dynamodb_table` tools  
**When** the tools execute  
**Then** the resources are deleted from MiniStack  
**And** I receive confirmation responses

**Architecture Decisions:** AD-9 (MCP Comprehensive Capabilities - Full CRUD from Phase 1)

## Alignment

- **Epic**: Epic 5 - AI Assistant Integration (MCP Server)
- **PRD requirement**: FR-12 (MCP Tools Write Operations - Full CRUD)
- **Architecture constraint**: AD-9 (MCP Comprehensive Capabilities)
- **ADRs in scope**: AD-9
- **Reuse decision**: Extended mcp_server/tools.py with Lambda and DynamoDB create/delete operations
- **Cross-layer contract**: MCP tools call POST/DELETE /api/resources/{service}/* - verified against api/routes/resources.py
- **Confirmed consistent**: YES - follows thin adapter pattern

## Outcome

- **Delivered**:
  - mcp_server/tools.py - Lambda and DynamoDB CRUD:
    - create_lambda_function(name, runtime, handler, code_base64, tenant_id, project, environment, memory, timeout)
    - delete_lambda_function(name, tenant_id)
    - create_dynamodb_table(name, partition_key, tenant_id, sort_key, billing_mode, project)
    - delete_dynamodb_table(name, tenant_id)
    - bulk_delete_project_resources(project_name, tenant_id)
  - Extended mcp_server/server.py with 5 additional tool definitions
  - Input schemas with proper types and validation
  
- **PRD coverage**: FR-12 (Lambda + DynamoDB portions) fully satisfied
- **Architecture impact**: None
- **Deferred**: None
- **Risks introduced**: None

**Wiring**:
- All tools route through call_tool_handler()
- Lambda functions support base64-encoded ZIP payloads
- DynamoDB tables support partition + optional sort keys
