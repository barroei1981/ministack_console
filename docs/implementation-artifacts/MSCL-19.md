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
