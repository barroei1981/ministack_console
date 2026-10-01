# Story MSCL-22: Resource Explorer with Full-Text Search

**Epic:** Epic 6 - Resource Discovery & Project Management  
**Story Points:** 5  
**Priority:** P1  
**Dependencies:** MSCL-6, MSCL-9

## User Story

As a **developer**,  
I want **to search across all resources by name, ID, or tag**,  
So that **I can quickly find resources without navigating service-by-service**.

## Acceptance Criteria

**Given** I am on the Resource Explorer page  
**When** I enter a search query (e.g., "prod")  
**Then** I see all resources matching the query in name, ID, or tags  
**And** results span multiple service types (S3, Lambda, DynamoDB, etc.)

**Given** I apply filters (service type, project, tenant)  
**When** the filters are applied  
**Then** only resources matching all filters are shown  
**And** filter state persists in LocalStorage

**Given** I view the recent resources list  
**When** the page loads  
**Then** I see the last 20 resources I accessed  
**And** I can click to navigate to their detail pages

**Architecture Decisions:** AD-14 (Hybrid LocalStorage for filter state), FR-6 (Resource Explorer)
