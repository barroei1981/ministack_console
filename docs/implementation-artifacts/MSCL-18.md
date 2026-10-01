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
