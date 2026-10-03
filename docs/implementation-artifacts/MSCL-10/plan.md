# MSCL-10 Implementation Plan

## Story Context
**MSCL-10: S3 Object Browser and Operations**

Epic 2: S3 Service Management (story 4 of 4)

## Alignment

- **Epic**: Epic-2 — S3 Service Management (complete CRUD for S3 buckets + object operations via web UI)
- **PRD requirement**: FR-5 (S3 Service Dashboard) — object browser portion with upload/download/delete operations
- **Architecture constraint**: Control-plane architecture (AD-4) mandates consistency with AWS Console patterns, SSE for real-time updates when objects change
- **ADRs in scope**: 
  - 2026-10-01-architecture-control-plane-with-mcp.md (Control-plane core)
  - 2026-10-01-definition-of-done-end-to-end.md (End-to-end testing requirements)
- **Reuse decision**: 
  - Extending `api/services/s3.py` S3Service class (add list_objects, upload_object, download_object, delete_objects methods) — same service pattern as bucket operations
  - Reusing `Breadcrumbs.tsx`, `Button.tsx`, `Modal.tsx`, `Toast.tsx`, `Table.tsx` from MSCL-9a/MSCL-9b — established common component pattern
  - Reusing `useSSE.ts` hook from MSCL-9b for real-time object list updates
  - Creating new `ObjectBrowser.tsx`, `ObjectUpload.tsx`, `ObjectProperties.tsx`, `useS3Objects.ts` — no overlap found, these are new object-specific patterns
- **Cross-layer contract**: 
  - `ObjectBrowser.tsx` calls `GET /api/resources/s3/buckets/{name}/objects?tenant_id={id}&prefix={path}` — verify endpoint exists after backend implementation
  - Upload calls `POST /api/resources/s3/buckets/{name}/objects?tenant_id={id}` with multipart/form-data — verify after backend implementation
  - Download calls `GET /api/resources/s3/buckets/{name}/objects/{key}/download?tenant_id={id}` → returns presigned URL — verify after backend implementation
  - Delete calls `DELETE /api/resources/s3/buckets/{name}/objects?tenant_id={id}&keys[]={key}` — verify after backend implementation
- **Confirmed consistent**: YES — approach aligns with control-plane architecture, reuses MSCL-9 foundation, follows AWS Console UX patterns

## Prior-Story Continuity

**MSCL-9b (S3 UI - Bucket Detail):**
- Produced: `BucketDetail.tsx` with three tabs (Overview, Properties, Tags), `Breadcrumbs.tsx`, `Tabs.tsx`, SSE integration
- Integration points for MSCL-10:
  - Add fourth tab "Objects" to `BucketDetail.tsx` at line 202 (Tabs component) → render `ObjectBrowser` component
  - Reuse `Breadcrumbs.tsx` for folder navigation within ObjectBrowser
  - Reuse `useSSE.ts` hook for real-time object creation/deletion events (invalidate object list cache)
  
**MSCL-8 (S3 Backend CRUD):**
- Produced: S3Service class with bucket operations, dual-write pattern, SSE event emission
- Integration points: Extend S3Service with object operations following same patterns (boto3 → SSE events)

## Implementation Tasks

### Phase 1: Backend - S3 Object Operations

#### 1.1 Extend S3Service with Object Methods

**File**: `api/services/s3.py`

Add the following methods to S3Service class:

```python
async def list_objects(
    self, bucket_name: str, prefix: str = "", max_keys: int = 1000
) -> dict[str, Any]:
    """
    List objects in bucket with optional prefix filter.
    
    Args:
        bucket_name: Bucket name
        prefix: Prefix filter (for folder navigation)
        max_keys: Maximum objects to return (pagination)
        
    Returns:
        Dict with objects list, common_prefixes (folders), is_truncated, next_token
    """
    with trace_operation("list_s3_objects", tenant_id=self.tenant_id, bucket=bucket_name, prefix=prefix):
        try:
            response = await asyncio.to_thread(
                self.client.list_objects_v2,
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys,
                Delimiter="/"  # Group by folders
            )
            
            # Parse objects
            objects = []
            for obj in response.get("Contents", []):
                objects.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "storage_class": obj.get("StorageClass", "STANDARD"),
                    "etag": obj.get("ETag", "").strip('"')
                })
            
            # Parse common prefixes (folders)
            folders = []
            for prefix_obj in response.get("CommonPrefixes", []):
                folders.append({"key": prefix_obj["Prefix"]})
            
            result = {
                "objects": objects,
                "folders": folders,
                "is_truncated": response.get("IsTruncated", False),
                "next_token": response.get("NextContinuationToken"),
                "prefix": prefix
            }
            
            log_operational(
                "Listed S3 objects",
                tenant_id=self.tenant_id,
                bucket=bucket_name,
                prefix=prefix,
                object_count=len(objects),
                folder_count=len(folders)
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchBucket":
                raise ValueError(f"Bucket {bucket_name} not found") from e
            raise
```

```python
async def upload_object(
    self,
    bucket_name: str,
    key: str,
    file_content: bytes,
    metadata: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Upload object to S3 bucket.
    
    Args:
        bucket_name: Bucket name
        key: Object key (path)
        file_content: File content as bytes
        metadata: Optional object metadata
        
    Returns:
        Dict with upload result: {bucket, key, size, etag}
    """
    with trace_operation("upload_s3_object", tenant_id=self.tenant_id, bucket=bucket_name, key=key):
        try:
            extra_args = {}
            if metadata:
                extra_args["Metadata"] = metadata
            
            response = await asyncio.to_thread(
                self.client.put_object,
                Bucket=bucket_name,
                Key=key,
                Body=file_content,
                **extra_args
            )
            
            result = {
                "bucket": bucket_name,
                "key": key,
                "size": len(file_content),
                "etag": response.get("ETag", "").strip('"')
            }
            
            log_operational(
                "Uploaded S3 object",
                tenant_id=self.tenant_id,
                bucket=bucket_name,
                key=key,
                size=len(file_content)
            )
            
            # Emit SSE event for object creation
            await event_bus.publish(
                "RESOURCE_CREATED",
                {
                    "type": "s3:object",
                    "bucket": bucket_name,
                    "key": key,
                    "size": len(file_content)
                },
                self.tenant_id
            )
            
            log_audit(
                "S3 object uploaded",
                event_type="OBJECT_UPLOADED",
                actor={"id": self.tenant_id, "type": "TENANT"},
                target={"type": "s3:object", "id": f"{bucket_name}/{key}"},
                action="CREATE",
                status="SUCCESS",
                changes={"before": None, "after": result}
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchBucket":
                raise ValueError(f"Bucket {bucket_name} not found") from e
            raise
```

```python
async def download_object(self, bucket_name: str, key: str) -> str:
    """
    Generate presigned URL for object download.
    
    Args:
        bucket_name: Bucket name
        key: Object key
        
    Returns:
        Presigned URL (expires in 1 hour)
    """
    with trace_operation("download_s3_object", tenant_id=self.tenant_id, bucket=bucket_name, key=key):
        try:
            url = await asyncio.to_thread(
                self.client.generate_presigned_url,
                "get_object",
                Params={"Bucket": bucket_name, "Key": key},
                ExpiresIn=3600  # 1 hour
            )
            
            log_operational(
                "Generated presigned URL for S3 object",
                tenant_id=self.tenant_id,
                bucket=bucket_name,
                key=key
            )
            
            return url
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchBucket":
                raise ValueError(f"Bucket {bucket_name} not found") from e
            elif error_code == "NoSuchKey":
                raise ValueError(f"Object {key} not found") from e
            raise
```

```python
async def delete_objects(
    self, bucket_name: str, keys: list[str]
) -> dict[str, Any]:
    """
    Delete multiple objects from bucket.
    
    Args:
        bucket_name: Bucket name
        keys: List of object keys to delete
        
    Returns:
        Dict with deletion result: {deleted_count, errors}
    """
    with trace_operation("delete_s3_objects", tenant_id=self.tenant_id, bucket=bucket_name, key_count=len(keys)):
        try:
            objects_to_delete = [{"Key": key} for key in keys]
            
            response = await asyncio.to_thread(
                self.client.delete_objects,
                Bucket=bucket_name,
                Delete={"Objects": objects_to_delete}
            )
            
            deleted = response.get("Deleted", [])
            errors = response.get("Errors", [])
            
            result = {
                "deleted_count": len(deleted),
                "errors": errors
            }
            
            log_operational(
                "Deleted S3 objects",
                tenant_id=self.tenant_id,
                bucket=bucket_name,
                deleted_count=len(deleted),
                error_count=len(errors)
            )
            
            # Emit SSE events for each deleted object
            for obj in deleted:
                await event_bus.publish(
                    "RESOURCE_DELETED",
                    {
                        "type": "s3:object",
                        "bucket": bucket_name,
                        "key": obj["Key"]
                    },
                    self.tenant_id
                )
            
            log_audit(
                "S3 objects deleted",
                event_type="OBJECTS_DELETED",
                actor={"id": self.tenant_id, "type": "TENANT"},
                target={"type": "s3:object", "id": f"{bucket_name}/*"},
                action="DELETE",
                status="SUCCESS",
                changes={"before": keys, "after": None}
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchBucket":
                raise ValueError(f"Bucket {bucket_name} not found") from e
            raise
```

#### 1.2 Add API Endpoints

**File**: `api/routes/resources.py`

Add these endpoints after existing S3 bucket endpoints:

```python
@router.get("/s3/buckets/{name}/objects")
async def list_s3_objects(
    name: str,
    tenant_id: str = Query(...),
    prefix: str = Query(""),
    max_keys: int = Query(1000, le=1000)
):
    """List objects in S3 bucket with optional prefix filter."""
    service = S3Service(tenant_id)
    return await service.list_objects(name, prefix, max_keys)

@router.post("/s3/buckets/{name}/objects")
async def upload_s3_object(
    name: str,
    key: str = Form(...),
    file: UploadFile = File(...),
    tenant_id: str = Query(...),
    metadata: str = Form(None)  # JSON string
):
    """Upload object to S3 bucket."""
    service = S3Service(tenant_id)
    content = await file.read()
    
    metadata_dict = None
    if metadata:
        import json
        metadata_dict = json.loads(metadata)
    
    return await service.upload_object(name, key, content, metadata_dict)

@router.get("/s3/buckets/{name}/objects/{key:path}/download")
async def download_s3_object(
    name: str,
    key: str,
    tenant_id: str = Query(...)
):
    """Generate presigned URL for object download."""
    service = S3Service(tenant_id)
    url = await service.download_object(name, key)
    return {"download_url": url}

@router.delete("/s3/buckets/{name}/objects")
async def delete_s3_objects(
    name: str,
    keys: list[str] = Query(...),
    tenant_id: str = Query(...)
):
    """Delete multiple objects from bucket."""
    service = S3Service(tenant_id)
    return await service.delete_objects(name, keys)
```

### Phase 2: Frontend - Object Operations Hooks

#### 2.1 Create useS3Objects Hook

**File**: `web_ui/src/hooks/useS3Objects.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import client from '../api/client';
import type {
  S3ObjectListResponse,
  S3Object,
  UploadObjectRequest,
  DeleteObjectsRequest
} from '../types/s3';

export function useS3Objects(
  bucketName: string | null,
  tenantId: string | null,
  prefix: string = ''
) {
  return useQuery<S3ObjectListResponse>({
    queryKey: ['s3-objects', bucketName, tenantId, prefix],
    queryFn: async () => {
      if (!bucketName || !tenantId) {
        return { objects: [], folders: [], is_truncated: false, prefix: '' };
      }
      const response = await client.get<S3ObjectListResponse>(
        `/resources/s3/buckets/${bucketName}/objects`,
        { params: { tenant_id: tenantId, prefix } }
      );
      return response.data;
    },
    enabled: !!bucketName && !!tenantId,
  });
}

export function useUploadObject(bucketName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UploadObjectRequest) => {
      const formData = new FormData();
      formData.append('key', data.key);
      formData.append('file', data.file);
      if (data.metadata) {
        formData.append('metadata', JSON.stringify(data.metadata));
      }

      const response = await client.post(
        `/resources/s3/buckets/${bucketName}/objects`,
        formData,
        {
          params: { tenant_id: data.tenant_id },
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: data.onProgress
        }
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      toast.success('File uploaded successfully');
      // Invalidate object list for current prefix
      const currentPrefix = variables.key.substring(0, variables.key.lastIndexOf('/') + 1);
      queryClient.invalidateQueries({
        queryKey: ['s3-objects', bucketName, variables.tenant_id, currentPrefix]
      });
    },
    onError: () => {
      toast.error('Failed to upload file');
    }
  });
}

export function useDownloadObject(bucketName: string) {
  return useMutation({
    mutationFn: async ({ key, tenant_id }: { key: string; tenant_id: string }) => {
      const response = await client.get<{ download_url: string }>(
        `/resources/s3/buckets/${bucketName}/objects/${key}/download`,
        { params: { tenant_id } }
      );
      return response.data.download_url;
    },
    onSuccess: (url) => {
      window.open(url, '_blank');
    },
    onError: () => {
      toast.error('Failed to download file');
    }
  });
}

export function useDeleteObjects(bucketName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: DeleteObjectsRequest) => {
      const response = await client.delete(
        `/resources/s3/buckets/${bucketName}/objects`,
        {
          params: {
            tenant_id: data.tenant_id,
            keys: data.keys
          }
        }
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      toast.success(`Deleted ${variables.keys.length} object(s)`);
      // Invalidate all object list queries for this bucket
      queryClient.invalidateQueries({
        queryKey: ['s3-objects', bucketName, variables.tenant_id]
      });
    },
    onError: () => {
      toast.error('Failed to delete objects');
    }
  });
}
```

#### 2.2 Add TypeScript Types

**File**: `web_ui/src/types/s3.ts` (add to existing file)

```typescript
export interface S3Object {
  key: string;
  size: number;
  last_modified: string;
  storage_class: string;
  etag: string;
}

export interface S3Folder {
  key: string;
}

export interface S3ObjectListResponse {
  objects: S3Object[];
  folders: S3Folder[];
  is_truncated: boolean;
  next_token?: string;
  prefix: string;
}

export interface UploadObjectRequest {
  key: string;
  file: File;
  tenant_id: string;
  metadata?: Record<string, string>;
  onProgress?: (progressEvent: any) => void;
}

export interface DeleteObjectsRequest {
  keys: string[];
  tenant_id: string;
}
```

### Phase 3: Frontend - Object Browser Component

#### 3.1 Create ObjectBrowser Component

**File**: `web_ui/src/components/services/S3/ObjectBrowser.tsx`

Component with:
- Breadcrumb navigation for folders
- Table showing folders (with folder icon) and objects
- Upload button (file input)
- Delete button (bulk delete)
- Click folder to navigate into it
- Click object name to download
- Right-click context menu (future: Copy S3 URI, Copy ARN, Properties)
- Selection checkboxes for bulk delete
- SSE integration via useSSE hook

#### 3.2 Create ObjectUpload Modal

**File**: `web_ui/src/components/services/S3/ObjectUpload.tsx`

Modal with:
- File picker (multiple files supported)
- Upload progress bar per file
- Optional metadata key/value inputs
- Upload to current prefix (folder)

#### 3.3 Integrate into BucketDetail

**File**: `web_ui/src/components/services/S3/BucketDetail.tsx`

Add "Objects" tab to existing three tabs:
- Overview
- Properties
- Tags
- **Objects** (new) → render ObjectBrowser component

### Phase 4: Testing

#### 4.1 Backend Tests
- Unit tests for S3Service object methods
- Integration tests: upload → list → download → delete flow
- Error handling: NoSuchBucket, NoSuchKey, permission errors

#### 4.2 Frontend Tests
- Component tests for ObjectBrowser (folder navigation, selection)
- Hook tests for useS3Objects, useUploadObject, useDeleteObjects
- E2E test: Navigate to bucket → upload file → download file → delete file

#### 4.3 Manual Testing
- Create nested folder structure (folder1/folder2/file.txt)
- Upload multiple files
- Navigate through folders via breadcrumbs
- Bulk delete multiple objects
- SSE updates: upload in one tab, see update in another tab

### Phase 5: i18n and Polish

- Add all UI strings to `web_ui/src/i18n/locales/en.json`
- Error messages, button labels, confirmation prompts
- Accessible ARIA labels for table, buttons, modals

## Outcome

- **Delivered**: S3 Object Browser with folder navigation (breadcrumbs + prefix filtering), file upload with progress tracking, presigned URL downloads (1hr expiry), bulk delete with confirmation modal, real-time SSE updates, selection checkboxes, emoji icons for folders/files
- **PRD coverage**: FR-5 (S3 Service Dashboard) object browser fully delivered — upload, download, delete, folder navigation, pagination-ready API (max 1000 objects), real-time updates
- **Architecture impact**: None — follows control-plane architecture (dual-write pattern for SSE events), reuses MSCL-9 components (Breadcrumbs, Button, Table, Modal), integrates SSE for real-time cache invalidation
- **Deferred**: Context menu (right-click for Copy S3 URI/ARN), object metadata editor, folder creation UI (backend supports it via key with trailing slash), pagination UI (backend ready with max_keys param)
- **Risks introduced**: None — presigned URLs expire after 1hr (security), structured logging/audit trails for all operations, TypeScript types enforced, SSE cache invalidation prevents stale data
- **Wiring**:
  - `list_objects` API at `/resources/s3/buckets/{name}/objects` called by ObjectBrowser at line 49 (useS3Objects hook)
  - `upload_object` API at POST `/resources/s3/buckets/{name}/objects` called by ObjectBrowser at line 113 (useUploadObject mutation)
  - `download_object` API at GET `/resources/s3/buckets/{name}/objects/{key}/download` called by ObjectBrowser at line 153 (useDownloadObject mutation)
  - `delete_objects` API at DELETE `/resources/s3/buckets/{name}/objects` called by ObjectBrowser at line 158 (useDeleteObjects mutation)
  - ObjectBrowser integrated into BucketDetail at line 199 as "Objects" tab
  - Breadcrumbs onClick support added at line 19 for folder navigation without route changes
  - SSE events for s3:object type trigger cache invalidation in useS3Objects hooks (useSSE.ts line 64)
