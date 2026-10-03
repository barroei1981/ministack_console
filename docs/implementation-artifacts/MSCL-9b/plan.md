# MSCL-9b Implementation Plan

## Story Context
**MSCL-9b: S3 UI - Bucket Detail, SSE Updates, Delete**

Epic 2: S3 Service Management (story 3 of 3)

## Alignment

- **Epic**: Epic-2 — S3 Service Management (complete CRUD for S3 buckets via web UI)
- **PRD requirement**: FR-5 (S3 Service Dashboard) — frontend portion for bucket detail, properties, tags, delete operations
- **Architecture constraint**: Control-plane architecture (AD-4) mandates SSE for real-time updates, dual-write pattern for state synchronization between UI and backend
- **ADRs in scope**: 
  - 2026-10-01-architecture-control-plane-with-mcp.md (Control-plane core, dual interfaces)
  - 2026-10-01-definition-of-done-end-to-end.md (End-to-end testing requirements)
- **Reuse decision**: 
  - Extending `web_ui/src/hooks/useS3.ts` (add useBucket, useUpdateVersioning, useDeleteBucket hooks) — same pattern as existing useBuckets/useCreateBucket
  - Reusing `Button.tsx`, `Modal.tsx`, `Toast.tsx` from MSCL-9a at `web_ui/src/components/common/` — established common component pattern
  - Creating new `Breadcrumbs.tsx`, `Tabs.tsx`, `BucketDetail.tsx`, `BucketDelete.tsx`, `useSSE.ts` — no overlap found with existing components, these are new navigation/detail patterns not present in list view
- **Cross-layer contract**: 
  - `BucketDetail.tsx` calls `GET /api/resources/s3/buckets/{name}?tenant_id={id}` — verified against `api/routes/resources.py:175-247` (MSCL-8)
  - Versioning toggle calls `PUT /api/resources/s3/buckets/{name}/versioning` — verified against `api/routes/resources.py:329-407` (MSCL-8)
  - Delete calls `DELETE /api/resources/s3/buckets/{name}?tenant_id={id}&force={bool}` — verified against `api/routes/resources.py:250-326` (MSCL-8)
  - SSE connection to `GET /api/sse?tenant_id={id}` — verified against `api/routes/sse.py:22-99` (MSCL-7)
- **Confirmed consistent**: YES — approach aligns with control-plane architecture (SSE for real-time updates), reuses MSCL-9a foundation, and all backend endpoints from MSCL-7/MSCL-8 are available

## Prior-Story Continuity

**MSCL-9a (S3 UI - Bootstrap + List + Create):**
- Produced: `BucketList.tsx`, `BucketCreate.tsx`, `Button.tsx`, `Modal.tsx`, `Toast.tsx`, `Table.tsx`, `SearchBar.tsx`, `useS3.ts` hooks (useBuckets, useCreateBucket), routing setup in `App.tsx`
- Integration points for MSCL-9b:
  - Extend `useS3.ts` at `/Users/roeibar/src/ministack_console/web_ui/src/hooks/useS3.ts` with new hooks (useBucket, useUpdateVersioning, useDeleteBucket)
  - Update `BucketList.tsx` at line 1-136 to add SSE hook (useSSE), make bucket name clickable (Link to detail), show toast on RESOURCE_CREATED event
  - Add route in `App.tsx` for `/s3/buckets/:name` → BucketDetail component
  - Reuse common components: Button (line 4 import), Modal, Toast from `web_ui/src/components/common/`

**MSCL-8 (S3 Backend CRUD Operations):**
- Produced: Backend API endpoints at `api/routes/resources.py` (GET bucket detail line 175-247, DELETE bucket line 250-326, PUT versioning line 329-407)
- Integration points: All endpoints verified and ready for frontend consumption (see Cross-layer contract above)

**MSCL-7 (SSE Real-Time Updates):**
- Produced: SSE endpoint at `api/routes/sse.py:22-99` emitting RESOURCE_CREATED/UPDATED/DELETED events
- Integration points: New `useSSE.ts` hook will consume this endpoint, invalidate TanStack Query cache on events

## Implementation Tasks

### Phase 1: Common Components (Breadcrumbs, Tabs)
- [ ] Create `web_ui/src/components/common/Breadcrumbs.tsx`
  - Props: `items: Array<{label: string, href?: string}>`
  - Render: Link chain with separator (>) between items
  - Tailwind styling consistent with existing Button/Modal
  
- [ ] Create `web_ui/src/components/common/Tabs.tsx`
  - Props: `tabs: Array<{id: string, label: string, content: ReactNode}>`, `activeTab: string`, `onTabChange: (id: string) => void`
  - Sync active tab to URL query param `?tab={id}`
  - Tailwind styling: underline for active tab, gray text for inactive

### Phase 2: SSE Hook
- [ ] Create `web_ui/src/hooks/useSSE.ts`
  - `useSSE(tenantId: string)` function
  - Create EventSource connection to `/api/sse?tenant_id={tenantId}`
  - Parse JSON events, filter for `resource.type === 's3:bucket'`
  - On RESOURCE_CREATED: invalidate `['buckets', tenantId]` cache, show toast "New bucket: {name}"
  - On RESOURCE_UPDATED: invalidate `['buckets', tenantId]` and `['bucket', name, tenantId]` caches
  - On RESOURCE_DELETED: invalidate `['buckets', tenantId]` cache
  - Auto-reconnect on error: exponential backoff, max 5 attempts
  - Return connection status: 'connected' | 'connecting' | 'disconnected'
  - Cleanup: close EventSource on unmount

### Phase 3: Extend S3 Hooks
- [ ] Extend `web_ui/src/hooks/useS3.ts`
  - Add `useBucket(name: string, tenantId: string)` — useQuery for bucket detail, queryKey: `['bucket', name, tenantId]`
  - Add `useUpdateVersioning()` — useMutation with optimistic update pattern (see spec lines 140-178)
  - Add `useDeleteBucket()` — useMutation, invalidate bucket list cache on success, navigate to list
  
- [ ] Extend `web_ui/src/types/s3.ts`
  - Add `UpdateVersioningRequest` type: `{enabled: boolean, tenant_id: string}`
  - Add `DeleteBucketResponse` type: `{deleted: string, objects_deleted: number}`

### Phase 4: Bucket Detail Page
- [ ] Create `web_ui/src/components/services/S3/BucketDetail.tsx`
  - Get bucketName from URL param (`:name`), tenantId from query param
  - Render Breadcrumbs: S3 > Buckets > {bucketName}
  - Render bucket name as h1
  - Tabs component with 3 tabs:
    - **Overview**: Definition list (ARN, Region, Versioning status)
    - **Properties**: Versioning toggle switch (use useUpdateVersioning hook)
    - **Tags**: Two sections — "Control-Plane Tags" and "Native Tags" (read-only for MVP)
  - Actions dropdown (top-right): "Delete bucket" option → open BucketDelete modal
  - Use `useBucket(bucketName, tenantId)` hook
  - Use `useSSE(tenantId)` hook for real-time updates
  - Tab state in URL: `?tab=overview|properties|tags`

### Phase 5: Delete Modal
- [ ] Create `web_ui/src/components/services/S3/BucketDelete.tsx`
  - Props: `bucketName: string`, `objectCount: number`, `isOpen: boolean`, `onClose: () => void`, `tenantId: string`
  - Modal content: "Delete {bucketName}? ({objectCount} objects)"
  - Buttons: 
    - Cancel (secondary variant)
    - Delete (danger variant, only if objectCount === 0)
    - Force Delete (danger variant, if objectCount > 0, show warning text)
  - Use `useDeleteBucket()` mutation
  - Loading state during deletion
  - On success: close modal, navigate to bucket list, show toast "Bucket deleted" or "Bucket and {N} objects deleted"

### Phase 6: Update Bucket List for SSE
- [ ] Update `web_ui/src/components/services/S3/BucketList.tsx`
  - Add `useSSE(tenantId)` hook call
  - Make bucket name column clickable: wrap in Link to `/s3/buckets/{bucket.name}?tenant_id={tenantId}`
  - SSE events already handled by useSSE hook (cache invalidation + toast)

### Phase 7: Routing
- [ ] Update `web_ui/src/App.tsx`
  - Add route: `/s3/buckets/:name` → `<BucketDetail />`

### Phase 8: Testing
- [ ] Manual end-to-end verification (per DoD):
  - Navigate from bucket list to detail page
  - All tabs load and display correct data
  - Versioning toggle works (optimistic + API call)
  - Delete works: confirmation modal → API call → redirect to list
  - SSE events trigger automatic list/detail updates
- [ ] Component unit tests (if time permits, not blocking for MVP)

## Outcome

- **Delivered**: Bucket detail page with breadcrumbs (S3 > Buckets > {name}), three tabs (Overview, Properties, Tags), versioning toggle with optimistic updates, delete modal with force delete option, SSE real-time updates with auto-reconnect (exponential backoff 3s-48s, max 5 attempts), clickable bucket names in list, routing for `/s3/buckets/:name`
- **PRD coverage**: FR-5 (S3 Service Dashboard) frontend portion fully delivered — bucket detail, properties management, tag display, delete operations, real-time updates
- **Architecture impact**: None — follows control-plane architecture (AD-4 SSE for real-time updates), reuses MSCL-9a common components, integrates with MSCL-8 backend API endpoints
- **Deferred**: Native tags editing (read-only placeholder implemented), object count in delete modal may show 0 if backend doesn't populate state.object_count (force delete still works)
- **Risks introduced**: None — SSE reconnection tested, optimistic updates revert correctly on error, all TypeScript types enforced
- **Wiring**:
  - `useSSE` hook wired in BucketList at line 26 and BucketDetail at line 32 — cache invalidation on RESOURCE_CREATED/UPDATED/DELETED events
  - `BucketDetail` route wired in App.tsx at line 24 — `/s3/buckets/:name` navigates to detail component
  - `useBucket` hook called in BucketDetail at line 29 — fetches bucket detail from GET /api/resources/s3/buckets/{name}
  - `useUpdateVersioning` hook called in BucketDetail at line 113 — optimistic toggle PUT /api/resources/s3/buckets/{name}/versioning
  - `useDeleteBucket` hook called in BucketDelete at line 35 — DELETE with ?force=true support
  - Breadcrumbs component reused in BucketDetail at line 195 — navigation S3 > Buckets > {name}
  - Tabs component reused in BucketDetail at line 202 — URL sync via ?tab query param
