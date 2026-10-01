# Story MSCL-14: DynamoDB Backend CRUD Operations

**Epic:** Epic 4 - DynamoDB Service Management  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-6

## User Story

As a **developer**,  
I want **REST API endpoints for DynamoDB table CRUD operations**,  
So that **I can manage DynamoDB tables programmatically**.

## Acceptance Criteria

**Given** I query GET `/api/resources/dynamodb/tables?tenant_id={id}`  
**When** the request is processed  
**Then** I receive all DynamoDB tables for that tenant  
**And** each table includes: name, key schema, provisioned throughput, item count

**Given** I send POST `/api/resources/dynamodb/tables` with table configuration  
**When** the request is processed  
**Then** a new table is created in MiniStack  
**And** the table is added to FalkorDB  
**And** a RESOURCE_CREATED event is emitted

**Given** I query GET `/api/resources/dynamodb/tables/{name}/items`  
**When** the request is processed  
**Then** I receive a paginated list of table items (scan operation)  
**And** I can specify filters and projections

**Given** I send PUT `/api/resources/dynamodb/tables/{name}/items` with item data  
**When** the request is processed  
**Then** the item is created or updated in the table  
**And** a RESOURCE_UPDATED event is emitted

**Architecture Decisions:** AD-1 (REST API as Core Backend), AD-5 (Python + FastAPI)
