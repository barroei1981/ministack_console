---
title: 'MSCL-9b: S3 UI - Bucket Detail, SSE Updates, Delete'
type: 'feature'
created: '2026-10-03'
status: 'done'
review_loop_iteration: 0
baseline_commit: '7175c67b39ae8531cd449e9e528846856ee1bac2'
context:
  - '_lch-output/implementation-artifacts/epic-2-context.md'
  - '_lch-output/implementation-artifacts/spec-MSCL-9a-s3-ui-list-create.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** MSCL-9a provides bucket list and create functionality, but developers cannot view bucket details, toggle versioning, manage tags, or delete buckets through the UI. Additionally, the UI does not update automatically when buckets are created/modified elsewhere (AWS CLI, other sessions), requiring manual page refresh.

**Approach:** Build Bucket Detail page with breadcrumbs (S3 > Buckets > {name}) and tabbed interface (Overview, Properties, Tags), implement versioning toggle in Properties tab with optimistic updates, add tag management sections (control-plane + native tags), create Delete action with confirmation modal (force delete if bucket has objects), implement SSE real-time updates via EventSource API to auto-refresh bucket list on RESOURCE_CREATED/UPDATED/DELETED events, invalidate TanStack Query cache on SSE events. Requires MSCL-9a (foundation + list + create) as blocking dependency.

## Boundaries & Constraints

**Always:**
- Reuse common components from MSCL-9a (Button, Modal, Toast, Breadcrumbs, Tabs)
- SSE connection via EventSource API to `/api/sse?tenant_id={id}` (from MSCL-7)
- Invalidate TanStack Query cache on SSE events (RESOURCE_CREATED/UPDATED/DELETED for s3:bucket)
- Optimistic updates for versioning toggle (immediate UI update, revert on API error)
- Confirmation modal before delete (show object count, force delete option if non-empty)
- Breadcrumbs navigation: S3 > Buckets > {bucket-name} (Link components)
- Tab persistence in URL (e.g., `/s3/buckets/my-bucket?tab=properties`)
- Toast notifications for all mutations (versioning update, delete success/error)

**Ask First:**
- Tag editing UX (inline edit vs modal) - propose inline for control-plane tags
- SSE reconnection strategy (max attempts, backoff interval) - suggest 5 attempts with exponential backoff
- Object count display in delete modal - backend may not provide this yet (mock for now?)

**Never:**
- Implement object browser (file list, upload, download) - deferred to MSCL-10
- Build WebSocket connection (AD-4 mandates SSE)
- Skip versioning optimistic updates (UX requirement)
- Allow delete without confirmation (safety requirement)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| View bucket detail | Click "my-bucket" in list, navigate to `/s3/buckets/my-bucket?tenant_id={id}` | API call `GET /api/resources/s3/buckets/my-bucket?tenant_id={id}`, render breadcrumbs (S3 > Buckets > my-bucket), tabs (Overview, Properties, Tags), Overview shows ARN, region, versioning status. | 404 → Toast: "Bucket not found", navigate back to list. 500 → Toast: "Failed to load bucket". |
| Toggle versioning | Properties tab, toggle switch from "Disabled" to "Enabled" | Optimistic update (switch immediately), API call `PUT /api/resources/s3/buckets/my-bucket/versioning` with `{enabled: true, tenant_id}`, toast "Versioning enabled" on success. | 404 → Toast: "Bucket not found", revert toggle. 500 → Toast: "Update failed", revert toggle. |
| Delete bucket (empty) | Actions dropdown → "Delete bucket", modal: "Delete my-bucket? (0 objects)", confirm | API call `DELETE /api/resources/s3/buckets/my-bucket?tenant_id={id}`, loading in modal, on 200: toast "Bucket deleted", navigate to list, cache invalidated. | 400 "Bucket not empty" → Show "Force delete?" option. 404 → Toast: "Bucket not found". 500 → Toast: "Delete failed". |
| Delete bucket (force) | Bucket has objects, click "Force Delete" in modal | API call `DELETE /api/resources/s3/buckets/my-bucket?tenant_id={id}&force=true`, modal shows "Deleting {N} objects...", on 200: toast "Bucket and {N} objects deleted", navigate to list. | 500 → Toast: "Delete failed", modal stays open for retry. |
| SSE update (bucket created) | SSE event: `data: {"type": "RESOURCE_CREATED", "resource": {"type": "s3:bucket", "name": "other-bucket"}, "tenant_id": "..."}` | TanStack Query cache invalidated for `['buckets', tenantId]`, bucket list refetches, new bucket appears without page refresh. Subtle toast: "New bucket: other-bucket" (3s auto-dismiss). | EventSource error → Auto-reconnect after 3s (exponential backoff, max 5 attempts). Max attempts exceeded → Persistent warning: "Live updates unavailable, refresh manually". |
| SSE update (versioning changed) | On bucket detail page, SSE event: `RESOURCE_UPDATED` for current bucket | Invalidate bucket detail query, refetch, versioning status updates in Overview/Properties tabs. | Same as above. |

</frozen-after-approval>

## Code Map

**MSCL-9a (reuse):**
- `web_ui/src/components/common/Button.tsx` -- Reuse for delete button, force delete button
- `web_ui/src/components/common/Modal.tsx` -- Reuse for delete confirmation modal
- `web_ui/src/components/common/Toast.tsx` -- Reuse for all notifications
- `web_ui/src/hooks/useS3.ts` -- Extend with useBucket, useUpdateVersioning, useDeleteBucket hooks
- `web_ui/src/api/client.ts` -- Reuse Axios instance
- `web_ui/src/types/s3.ts` -- Extend with UpdateVersioningRequest, DeleteBucketResponse types

**MSCL-8 Backend (reuse):**
- `api/routes/resources.py:175-247` -- GET /api/resources/s3/buckets/{name} endpoint
- `api/routes/resources.py:250-326` -- DELETE /api/resources/s3/buckets/{name} endpoint
- `api/routes/resources.py:329-407` -- PUT /api/resources/s3/buckets/{name}/versioning endpoint
- `api/routes/sse.py:22-99` -- GET /api/sse endpoint (SSE stream)

**New components:**
- `web_ui/src/components/common/Breadcrumbs.tsx` -- Breadcrumb navigation (array of {label, href})
- `web_ui/src/components/common/Tabs.tsx` -- Tab navigation (active tab state, URL sync)
- `web_ui/src/components/services/S3/BucketDetail.tsx` -- Bucket detail page with tabs
- `web_ui/src/components/services/S3/BucketDelete.tsx` -- Delete confirmation modal (separate from BucketDetail for reusability)
- `web_ui/src/hooks/useSSE.ts` -- SSE hook (EventSource connection, cache invalidation)

## Tasks & Acceptance

**Execution:**
- [x] `web_ui/src/components/common/Breadcrumbs.tsx` -- Breadcrumb component: props `items` (array of {label, href}), render as Link chain with separator, Tailwind styling
- [x] `web_ui/src/components/common/Tabs.tsx` -- Tab component: props `tabs` (array of {id, label, content}), `activeTab`, `onTabChange`, sync active tab to URL query param `?tab={id}`, Tailwind styling
- [x] `web_ui/src/hooks/useSSE.ts` -- SSE hook: `useSSE(tenantId)` creates EventSource connection to `/api/sse?tenant_id={id}`, parse JSON events, invalidate TanStack Query cache on RESOURCE_CREATED/UPDATED/DELETED (filter by resource type s3:bucket), auto-reconnect on error (exponential backoff, max 5 attempts), return connection status
- [x] `web_ui/src/hooks/useS3.ts` -- Extend with: `useBucket(name, tenantId)` (useQuery for bucket detail), `useUpdateVersioning()` (useMutation with optimistic update), `useDeleteBucket()` (useMutation with cache invalidation and navigation on success)
- [x] `web_ui/src/types/s3.ts` -- Add types: `UpdateVersioningRequest` (enabled: boolean, tenant_id: string), `DeleteBucketResponse` (deleted: string, objects_deleted: number)
- [x] `web_ui/src/components/services/S3/BucketDetail.tsx` -- Bucket detail page: breadcrumbs (S3 > Buckets > {name}), bucket name as h1, Tabs component with Overview tab (definition list: ARN, region, versioning status), Properties tab (versioning toggle switch with useUpdateVersioning), Tags tab (two sections: "Control-Plane Tags" and "Native Tags" with read-only display for MVP), Actions dropdown (Delete option opens BucketDelete modal), useBucket hook, useSSE hook for real-time updates
- [x] `web_ui/src/components/services/S3/BucketDelete.tsx` -- Delete modal: props `bucketName`, `objectCount`, show confirmation: "Delete {bucketName}? ({objectCount} objects)", buttons: Cancel, Delete (if empty), Force Delete (if non-empty), useDeleteBucket mutation, loading state, close on success, navigate to list on success
- [x] `web_ui/src/components/services/S3/BucketList.tsx` -- Update: add useSSE hook for real-time updates, show subtle toast on RESOURCE_CREATED event ("New bucket: {name}"), make bucket name column clickable (navigate to `/s3/buckets/{name}`)
- [x] `web_ui/src/App.tsx` -- Add route: `/s3/buckets/:name` (BucketDetail)

**Acceptance Criteria:**
- Given I click bucket name "my-bucket" in list, when detail page loads, then I see breadcrumbs (S3 > Buckets > my-bucket), tabs (Overview, Properties, Tags), and Overview shows ARN, region, versioning status
- Given I'm on Properties tab, when I toggle versioning from Disabled to Enabled, then toggle updates immediately (optimistic), API call `PUT .../versioning` is made, toast "Versioning enabled" appears on success
- Given versioning toggle fails (500 error), when API returns error, then toggle reverts to original state, toast "Update failed" appears
- Given I click Actions → Delete on an empty bucket, when I confirm in modal, then API call `DELETE .../my-bucket` is made, toast "Bucket deleted" appears, I'm navigated to bucket list, bucket removed from table
- Given bucket has objects, when I click Delete, then modal shows "Force delete?" option, clicking it calls `DELETE?force=true`, toast "Bucket and {N} objects deleted" appears
- Given SSE connection is active and bucket created via AWS CLI, when RESOURCE_CREATED event arrives, then bucket list refetches automatically, new bucket appears, subtle toast "New bucket: {name}" appears
- Given I'm viewing bucket detail and versioning is changed elsewhere, when RESOURCE_UPDATED event arrives, then bucket detail refetches, versioning status updates in Overview and Properties tabs

## Spec Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Design Notes

**SSE Cache Invalidation:**
```typescript
// web_ui/src/hooks/useSSE.ts
import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import toast from 'react-hot-toast';

export function useSSE(tenantId: string) {
  const queryClient = useQueryClient();
  
  useEffect(() => {
    const eventSource = new EventSource(`${import.meta.env.VITE_API_BASE_URL}/sse?tenant_id=${tenantId}`);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.resource?.type === 's3:bucket') {
        if (data.type === 'RESOURCE_CREATED') {
          queryClient.invalidateQueries({ queryKey: ['buckets', tenantId] });
          toast.success(`New bucket: ${data.resource.name}`, { duration: 3000 });
        } else if (data.type === 'RESOURCE_UPDATED') {
          queryClient.invalidateQueries({ queryKey: ['buckets', tenantId] });
          queryClient.invalidateQueries({ queryKey: ['bucket', data.resource.name, tenantId] });
        } else if (data.type === 'RESOURCE_DELETED') {
          queryClient.invalidateQueries({ queryKey: ['buckets', tenantId] });
        }
      }
    };
    
    return () => eventSource.close();
  }, [tenantId, queryClient]);
}
```

**Optimistic Versioning Toggle:**
```typescript
// web_ui/src/hooks/useS3.ts
export function useUpdateVersioning() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ bucketName, enabled, tenantId }) => {
      const { data } = await apiClient.put(`/resources/s3/buckets/${bucketName}/versioning`, {
        enabled,
        tenant_id: tenantId,
      });
      return data;
    },
    onMutate: async ({ bucketName, enabled, tenantId }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['bucket', bucketName, tenantId] });
      
      // Snapshot current value
      const previous = queryClient.getQueryData(['bucket', bucketName, tenantId]);
      
      // Optimistically update
      queryClient.setQueryData(['bucket', bucketName, tenantId], (old: any) => ({
        ...old,
        versioning: enabled ? 'Enabled' : 'Suspended',
        state: { ...old.state, versioning: enabled ? 'Enabled' : 'Suspended' },
      }));
      
      return { previous };
    },
    onError: (err, variables, context) => {
      // Revert on error
      queryClient.setQueryData(['bucket', variables.bucketName, variables.tenantId], context?.previous);
      toast.error('Failed to update versioning');
    },
    onSuccess: () => {
      toast.success('Versioning updated');
    },
  });
}
```

## Verification

**Commands:**
- `cd web_ui && npm run dev` -- expected: No errors, SSE connection visible in DevTools Network tab
- `cd web_ui && npm run build` -- expected: TypeScript compiles successfully

**Manual checks:**
- Navigate to `/s3/buckets/test-bucket?tenant_id={id}` -- expected: Breadcrumbs, tabs, detail content visible
- Toggle versioning -- expected: Immediate UI update, PUT request in Network tab, toast notification
- Create bucket via AWS CLI while UI open -- expected: Bucket appears in list within 2s, toast notification
- Delete bucket with objects -- expected: Modal shows "Force delete?" option, DELETE?force=true on confirm

## Suggested Review Order

**SSE Real-time Updates**

- EventSource connection with exponential backoff reconnection (3s → 48s max, 5 attempts)
  [`useSSE.ts:1`](../../web_ui/src/hooks/useSSE.ts#L1)

- Cache invalidation on RESOURCE_CREATED/UPDATED/DELETED events for s3:bucket resources
  [`useSSE.ts:60`](../../web_ui/src/hooks/useSSE.ts#L60)

- BucketList integrates SSE hook for automatic list refresh without manual page reload
  [`BucketList.tsx:26`](../../web_ui/src/components/services/S3/BucketList.tsx#L26)

**Bucket Detail Page**

- Main detail component with breadcrumbs, tabs (Overview/Properties/Tags), and actions dropdown
  [`BucketDetail.tsx:1`](../../web_ui/src/components/services/S3/BucketDetail.tsx#L1)

- Versioning toggle with optimistic updates — immediate UI update, reverts on API error
  [`BucketDetail.tsx:113`](../../web_ui/src/components/services/S3/BucketDetail.tsx#L113)

- useBucket hook fetches bucket detail, enabled only when name and tenantId are present
  [`useS3.ts:55`](../../web_ui/src/hooks/useS3.ts#L55)

- useUpdateVersioning mutation with optimistic update pattern (snapshot, update, revert on error)
  [`useS3.ts:69`](../../web_ui/src/hooks/useS3.ts#L69)

**Delete Functionality**

- Delete modal with force delete option for non-empty buckets, object count display
  [`BucketDelete.tsx:1`](../../web_ui/src/components/services/S3/BucketDelete.tsx#L1)

- useDeleteBucket mutation with cache invalidation and navigation to list on success
  [`useS3.ts:123`](../../web_ui/src/hooks/useS3.ts#L123)

**Common Components**

- Breadcrumb navigation with Link chain and separator, supports optional hrefs
  [`Breadcrumbs.tsx:1`](../../web_ui/src/components/common/Breadcrumbs.tsx#L1)

- Tabs component with URL query param sync (?tab={id}), active tab styling
  [`Tabs.tsx:1`](../../web_ui/src/components/common/Tabs.tsx#L1)

**Routing & Integration**

- BucketDetail route added at /s3/buckets/:name with tenantId query param preservation
  [`App.tsx:24`](../../web_ui/src/App.tsx#L24)

- Bucket name column now clickable Link to detail page, preserves tenantId in URL
  [`BucketList.tsx:44`](../../web_ui/src/components/services/S3/BucketList.tsx#L44)

**Types & Translations**

- UpdateVersioningRequest and DeleteBucketResponse types for new API contracts
  [`s3.ts:26`](../../web_ui/src/types/s3.ts#L26)

- Translation keys for detail page, tabs, delete modal, versioning controls
  [`en.json:32`](../../web_ui/src/i18n/locales/en.json#L32)
