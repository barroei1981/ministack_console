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

## Alignment

- **Epic**: Epic 6 - Resource Discovery & Project Management
- **PRD requirement**: FR-6 (Resource Explorer with full-text search)
- **Architecture constraint**: AD-14 (Hybrid LocalStorage for UI state), AD-1 (FalkorDB for control-plane state)
- **ADRs in scope**: AD-14 (LocalStorage pattern)
- **Reuse decision**: Created new `/api/search/resources` endpoint with FalkorDB Cypher queries — no existing search infrastructure to extend
- **Cross-layer contract**: ResourceExplorer component calls `GET /api/search/resources?q={query}&tenant_id={id}&service_type={type}&project={name}` — verified against `api/routes/search.py:search_resources`
- **Confirmed consistent**: YES — search endpoint follows established patterns (FalkorDB query, structured logging, tenant filtering)

## Outcome

- **Delivered**:
  - Backend search endpoint (`api/routes/search.py`) with FalkorDB Cypher queries
  - Case-insensitive search across resource names and IDs
  - Filter support: tenant_id, service_type (s3/lambda/dynamodb), project
  - Frontend ResourceExplorer component (`web_ui/src/components/ResourceExplorer.tsx`)
  - Search input with real-time results display
  - Service type filter dropdown
  - Project filter input
  - Results table with resource details (name, type, ID, project) and links to detail pages
  - Recent resources list (last 20 accessed) with LocalStorage persistence
  - TypeScript types (`web_ui/src/types/search.ts`)
  - Custom React hook (`web_ui/src/hooks/useResourceSearch.ts`)
  - Route added to App.tsx (`/explorer`)
  
- **PRD coverage**: FR-6 (Resource Explorer) fully satisfied
- **Architecture impact**: None — follows established patterns (AD-1, AD-14)
- **Deferred**: None
- **Risks introduced**: None

**Wiring**:
- `search_resources` endpoint wired at `api/main.py:111` (router registration)
- ResourceExplorer component wired at `web_ui/src/App.tsx:27` (route definition)
- useResourceSearch hook wired in ResourceExplorer component
- LocalStorage integration for recent resources (RECENT_RESOURCES_KEY)
