# Story MSCL-12: Lambda UI Components (AWS Console Clone)

**Epic:** Epic 3 - Lambda Service Management  
**Story Points:** 8  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-11

## User Story

As a **developer**,  
I want **AWS Console-style UI for managing Lambda functions**,  
So that **I can create, view, and manage Lambda functions without using AWS CLI**.

## Acceptance Criteria

**Given** I navigate to the Lambda service page  
**When** the page loads  
**Then** I see a list of all Lambda functions for the selected tenant  
**And** I see columns: Function name, Runtime, Last modified, Memory, Timeout  
**And** I see an orange "Create function" button

**Given** I click "Create function"  
**When** the form modal opens  
**Then** I see fields for: Function name, Runtime (dropdown), Handler, Memory size, Timeout, Environment variables, Project tag  
**And** I can upload a ZIP file containing the function code

**Given** I click on a function name  
**When** the detail page loads  
**Then** I see tabs: Configuration, Code, Environment variables, Permissions, Monitoring  
**And** the Configuration tab shows all function settings  
**And** the Code tab shows a code editor (read-only for Phase 1, editable in future)

**Given** I am on the function detail page  
**When** I click "Test" button  
**Then** I can enter a test payload (JSON)  
**And** the function is invoked with the payload  
**And** I see the response and execution logs

**Architecture Decisions:** AD-7 (AWS Console Clone UI)
