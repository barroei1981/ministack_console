# Story MSCL-16: DynamoDB Item Browser and JSON Editor

**Epic:** Epic 4 - DynamoDB Service Management  
**Story Points:** 5  
**Priority:** P1  
**Dependencies:** MSCL-14, MSCL-15

## User Story

As a **developer**,  
I want **to browse, create, update, and delete DynamoDB items using a JSON editor**,  
So that **I can manage table data without using AWS CLI**.

## Acceptance Criteria

**Given** I am on a table's Items tab  
**When** the page loads  
**Then** I see a paginated list of items (scan operation)  
**And** I can click "Create item" to add a new item

**Given** I click "Create item"  
**When** the JSON editor opens  
**Then** I can enter item data as JSON  
**And** the editor validates JSON syntax  
**And** on submit, the item is created via API

**Given** I click on an existing item  
**When** the editor opens  
**Then** I can modify the item's JSON  
**And** on save, the item is updated via PutItem API

**Given** I select items and click "Delete"  
**When** I confirm deletion  
**Then** selected items are deleted via BatchWriteItem  
**And** the list updates automatically

**Architecture Decisions:** AD-1 (REST API backend for DynamoDB operations)
