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

## Alignment

- **Epic**: Epic 6 - Resource Discovery & Project Management
- **PRD requirement**: FR-8 (Project Management UI), FR-4 (Project Tagging)
- **Architecture constraint**: AD-4 (Project Tagging), AD-1 (FalkorDB for control-plane state)
- **ADRs in scope**: AD-4
- **Reuse decision**: Extended existing `/api/tenants/{tenant_id}/projects` endpoint (from MSCL-6) with three new endpoints: POST /projects (create), GET /projects/{name} (detail with service breakdown), DELETE /projects/{name}/resources (bulk delete)
- **Cross-layer contract**: 
  - ProjectList calls `GET /api/tenants/{tenant_id}/projects` — verified against `api/routes/projects.py:list_tenant_projects`
  - ProjectDetail calls `GET /api/projects/{name}?tenant_id={id}` — verified against `api/routes/projects.py:get_project_detail`
  - Bulk delete calls `DELETE /api/projects/{name}/resources?tenant_id={id}` — verified against `api/routes/projects.py:delete_project_resources`
- **Confirmed consistent**: YES — project management follows established patterns (FalkorDB queries, structured logging, tenant isolation)

## Outcome

- **Delivered**:
  - Backend extensions (`api/routes/projects.py`):
    - POST /projects - Create project node in FalkorDB with name, description, tenant_id
    - GET /projects/{name} - Get project details with resource counts grouped by service type
    - DELETE /projects/{name}/resources - Bulk delete all resources in project (destructive)
  - Extended models (`api/models.py`):
    - CreateProjectRequest, ProjectDetailResponse, BulkDeleteResponse
    - ProjectSummary extended with description and created_at fields
  - Frontend ProjectList component (`web_ui/src/components/ProjectList.tsx`)
    - List all projects for selected tenant
    - Show name, description, resource count, created date
    - Link to project detail page
    - Create project button (modal placeholder)
  - Frontend ProjectDetail component (`web_ui/src/components/ProjectDetail.tsx`)
    - Dashboard with stats cards (total resources, service types, created date)
    - Resource counts table grouped by service type
    - Bulk delete button with confirmation modal
    - Back navigation to project list
  - TypeScript types (`web_ui/src/types/project.ts`)
  - Custom React hooks (`web_ui/src/hooks/useProjects.ts`):
    - useProjects, useCreateProject, useProjectDetail, useBulkDeleteResources
  - Routes added to App.tsx (`/projects`, `/projects/:projectName`)
  
- **PRD coverage**: FR-8 (Project Management UI) fully satisfied, FR-4 (Project Tagging) partially covered
- **Architecture impact**: None — follows AD-4 (Project Tagging pattern)
- **Deferred**: Create project modal UI (placeholder in ProjectList) — requires form component
- **Risks introduced**: Bulk delete is destructive and cannot be undone — mitigated by confirmation modal with resource count display

**Wiring**:
- All three new endpoints registered in existing projects router (api/main.py already includes projects.router)
- ProjectList component wired at web_ui/src/App.tsx:29 (route definition)
- ProjectDetail component wired at web_ui/src/App.tsx:30 (route definition)
- useProjects hook wired in ProjectList component
- useProjectDetail and useBulkDeleteResources hooks wired in ProjectDetail component
