# Story MSCL-15: DynamoDB UI Components (AWS Console Clone)

**Epic:** Epic 4 - DynamoDB Service Management  
**Story Points:** 8  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-14

## User Story

As a **developer**,  
I want **AWS Console-style UI for managing DynamoDB tables**,  
So that **I can create, browse, and manage DynamoDB tables visually**.

## Acceptance Criteria

**Given** I navigate to the DynamoDB service page  
**When** the page loads  
**Then** I see a list of all DynamoDB tables  
**And** columns show: Table name, Partition key, Sort key, Item count, Created date  
**And** I see an orange "Create table" button

**Given** I click "Create table"  
**When** the form opens  
**Then** I can specify: Table name, Partition key (name + type), Sort key (optional), Billing mode (On-demand/Provisioned)  
**And** the form validates key types (String, Number, Binary)

**Given** I click on a table name  
**When** the detail page loads  
**Then** I see tabs: Overview, Items, Indexes, Monitoring  
**And** the Overview tab shows table schema and settings

**Architecture Decisions:** AD-7 (AWS Console Clone UI)
