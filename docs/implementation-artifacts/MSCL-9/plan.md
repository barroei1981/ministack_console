# MSCL-9 Implementation Plan: S3 UI Components (AWS Console Clone)

**Story:** MSCL-9 - S3 UI Components (AWS Console Clone)  
**Epic:** Epic 2 - S3 Service Management  
**Created:** 2026-10-03  
**Status:** Planning

---

## Alignment

- **Epic**: Epic 2 - S3 Service Management (FR-5: Service Dashboards - Top 3 services, S3 is #1)
- **PRD requirement**: FR-5 (S3 Service Dashboard) - web UI portion. PRD section 3.1 (Primary Persona: Full-Stack Developer Alex) wants AWS Console-like visual tools for local dev.
- **Architecture constraint**: AD-7 (AWS Console Clone UI Paradigm) - must match AWS Console visual design. Architecture section 5.2.3.1 (Web UI - Human Interface) specifies React as the frontend framework.
- **ADRs in scope**: 
  - AD-1 (REST API as Core Backend) - frontend consumes `/api/resources/s3/` endpoints
  - None for frontend tech stack yet (will be created in this story)
- **Reuse decision**: No frontend exists yet. This is the first Web UI story. Backend API from MSCL-8 provides `/api/resources/s3/buckets` endpoints at:
  - `GET /api/resources/s3/buckets?tenant_id={id}` (list)
  - `POST /api/resources/s3/buckets` (create)
  - `GET /api/resources/s3/buckets/{name}?tenant_id={id}` (detail)
  - `DELETE /api/resources/s3/buckets/{name}?tenant_id={id}` (delete)
  - `PUT /api/resources/s3/buckets/{name}/versioning` (toggle versioning)
  - SSE endpoint: `GET /api/sse?tenant_id={id}`
- **Cross-layer contract**: 
  - UI will call `GET /api/resources/s3/buckets?tenant_id={id}` expecting JSON: `[{name, region, versioning, tags, created_at, tenant_id}]`
  - UI will call `POST /api/resources/s3/buckets` with `{name, project?, versioning?}` expecting 201 + `{id, type, name, arn, state, created_at}`
  - UI will call `DELETE /api/resources/s3/buckets/{name}?tenant_id={id}` expecting 200 + `{deleted, objects_deleted}`
  - Backend contract verified in MSCL-8 (PR #8) at `api/routes/resources.py` and `api/services/s3.py`
- **Confirmed consistent**: YES - Story aligns with PRD FR-5, Architecture React frontend, and backend API from MSCL-8

---

## Implementation Approach

### Phase 1: Bootstrap Frontend (if needed)

**Decision:** No `web_ui/` directory exists. Need to create React app from scratch.

**Proposed Tech Stack:**
- **Build tool**: Vite (fast, modern, excellent DX)
- **Framework**: React 18 + TypeScript
- **State management**: TanStack Query (React Query) for server state
- **Styling**: Tailwind CSS (utility-first, AWS Console clone possible)
- **Routing**: React Router v6
- **Forms**: React Hook Form + Zod validation
- **HTTP client**: Axios
- **SSE**: EventSource API (native)
- **UI components**: Headless UI (for modals, dropdowns) + custom AWS-styled components

**Rationale:**
- Vite: Faster than CRA, standard modern choice
- TanStack Query: Perfect for API data fetching, caching, SSE integration
- Tailwind: Easy to replicate AWS Console colors/spacing
- TypeScript: Type safety for API contracts

**Directory Structure:**
```
web_ui/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── common/           # Reusable: Button, Table, Modal, etc.
│   │   └── services/
│   │       └── S3/           # S3-specific components
│   │           ├── BucketList.tsx
│   │           ├── BucketDetail.tsx
│   │           ├── BucketCreate.tsx
│   │           └── index.ts
│   ├── hooks/
│   │   ├── useS3.ts          # S3 API operations
│   │   └── useSSE.ts         # Real-time updates
│   ├── api/
│   │   └── client.ts         # Axios instance, base URL config
│   ├── types/
│   │   └── s3.ts             # TypeScript types for S3 resources
│   └── styles/
│       └── aws-theme.css     # AWS Console color scheme
```

### Phase 2: Implement S3 Components

**Components to build:**

1. **BucketList** (main S3 page)
   - Table view of all buckets
   - Search/filter by name
   - Pagination (100/page)
   - "Create bucket" button (opens modal)
   - Row click → navigate to detail

2. **BucketCreate** (modal)
   - Form: bucket name (validated), project dropdown, versioning checkbox
   - Validation: 3-63 chars, lowercase, no spaces, DNS-compliant
   - Submit → API call → toast notification → close modal

3. **BucketDetail** (detail page)
   - Breadcrumbs: S3 > Buckets > {name}
   - Tabs: Overview, Objects (stub), Properties, Tags
   - Overview: ARN, region, versioning status
   - Properties: versioning toggle
   - Tags: Dual tag sections (control-plane, native)
   - Delete button with confirmation modal

4. **Common Components**
   - Button (AWS orange style)
   - Table (sortable columns)
   - Modal
   - Toast notifications
   - SearchBar
   - Breadcrumbs
   - Tabs

**Hooks:**

1. **useS3** - API operations
   - `useBuckets(tenantId)` - list query
   - `useBucket(name, tenantId)` - detail query
   - `useCreateBucket()` - mutation
   - `useDeleteBucket()` - mutation
   - `useUpdateVersioning()` - mutation

2. **useSSE** - Real-time updates
   - Connect to `/api/sse?tenant_id={id}`
   - Listen for `RESOURCE_CREATED`, `RESOURCE_UPDATED`, `RESOURCE_DELETED`
   - Invalidate TanStack Query cache on events

### Phase 3: AWS Console Styling

**Color scheme (CSS variables):**
```css
:root {
  --aws-blue: #232f3e;      /* Header background */
  --aws-orange: #ff9900;    /* Primary action buttons */
  --aws-white: #ffffff;
  --aws-gray-light: #f2f3f3;
  --aws-gray-dark: #545b64;
  --aws-border: #d5dbdb;
}
```

**Layout:**
- Blue header with "S3" title + search bar
- Orange "Create bucket" button (top-right)
- White content area
- AWS font: Amazon Ember or system fallback

### Phase 4: End-to-End Verification

Per `.harness/decisions/2026-10-01-definition-of-done-end-to-end.md`:

1. Start backend: `uvicorn api.main:app --reload`
2. Start frontend: `npm run dev` (Vite dev server)
3. Navigate to `http://localhost:5173` (Vite default)
4. Verify:
   - UI loads (React app renders)
   - Bucket list appears (or empty state if no buckets)
   - Click "Create bucket" → modal opens
   - Fill form: valid name, select project, enable versioning
   - Submit → API call to backend → 201 response → bucket created in MiniStack
   - New bucket appears in list (either via SSE or refetch)
   - Click bucket name → detail page loads
   - View tabs: Overview shows ARN/region, Properties shows versioning toggle
   - Click delete → confirmation modal → confirm → bucket deleted
   - SSE: Create bucket in another terminal via AWS CLI → bucket appears in UI automatically

---

## Tasks

- [ ] Bootstrap Vite + React + TypeScript frontend in `web_ui/`
- [ ] Set up Tailwind CSS with AWS color scheme
- [ ] Create API client (`api/client.ts`) pointing to `http://localhost:8000/api`
- [ ] Define TypeScript types for S3 resources (`types/s3.ts`)
- [ ] Implement `useS3` hook with TanStack Query
- [ ] Implement `useSSE` hook for real-time updates
- [ ] Build common components: Button, Table, Modal, Toast, SearchBar, Breadcrumbs, Tabs
- [ ] Build S3 components: BucketList, BucketCreate, BucketDetail
- [ ] Implement bucket name validation (client-side + server-side)
- [ ] Add confirmation modals for delete operations
- [ ] Test end-to-end: create → list → detail → delete → SSE updates
- [ ] Write unit tests for components (React Testing Library)
- [ ] Run `/lch-code-review` before commit
- [ ] Update `sprint-status.yaml`: MSCL-9 `backlog` → `in-progress` → `review` → `done`

---

## Notes

- Backend runs on `localhost:8000` (FastAPI default)
- Frontend dev server on `localhost:5173` (Vite default)
- CORS: Backend must allow `http://localhost:5173` origin (check `api/main.py`)
- Tenant selection: For MVP, hardcode tenant_id or add dropdown in header
- No ADR exists yet for frontend tech stack - will create one after implementation proves it works
