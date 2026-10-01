# Story MSCL-24: Project Management UI

**Epic:** Epic 6 - Resource Discovery & Project Management  
**Story Points:** 5  
**Priority:** P1  
**Dependencies:** MSCL-6, MSCL-9

## User Story

As a **developer**,  
I want **to create and manage projects to organize resources**,  
So that **I can group related resources and perform bulk operations**.

## Acceptance Criteria

**Given** I navigate to the Projects page  
**When** the page loads  
**Then** I see a list of all projects for the selected tenant  
**And** each project shows: name, description, resource count, created date

**Given** I click "Create project"  
**When** the form opens  
**Then** I can enter: Project name, Description, Tenant selection  
**And** on submit, the project is created in FalkorDB

**Given** I click on a project  
**When** the project detail page loads  
**Then** I see a dashboard with resource counts by service type  
**And** I see a table listing all resources in the project

**Given** I select "Delete all resources in project"  
**When** I confirm the bulk delete  
**Then** all resources in the project are deleted via API  
**And** the project becomes empty

**Architecture Decisions:** FR-8 (Project Management UI), AD-4 (Project Tagging)
