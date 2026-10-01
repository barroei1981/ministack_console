# Story MSCL-10: S3 Object Browser and Operations

**Epic:** Epic 2 - S3 Service Management  
**Story Points:** 8  
**Priority:** P1  
**Dependencies:** MSCL-8, MSCL-9

## User Story

As a **developer**,  
I want **to browse, upload, download, and delete objects in S3 buckets**,  
So that **I can manage S3 content without using AWS CLI**.

## Acceptance Criteria

**Given** I am viewing a bucket's Objects tab  
**When** the page loads  
**Then** I see a file browser interface showing all objects in the bucket  
**And** objects are displayed in a table with columns: Key (name), Size, Last Modified, Storage Class  
**And** folders are visually distinguished from files (folder icon)

**Given** I am browsing objects with nested folders  
**When** I click on a folder  
**Then** I navigate into that folder (prefix filter applied)  
**And** breadcrumbs show the current path: bucket-name / folder1 / folder2 /  
**And** I can click breadcrumbs to navigate back

**Given** I click "Upload" button  
**When** the upload dialog opens  
**Then** I can select multiple files from my computer  
**And** I can set metadata/tags for uploaded files (optional)  
**And** I see a progress bar during upload

**Given** I upload a file  
**When** the upload completes  
**Then** the file appears in the object list immediately  
**And** a toast notification confirms "File uploaded successfully"  
**And** the API endpoint is POST `/api/resources/s3/buckets/{name}/objects`

**Given** I select an object and click "Download"  
**When** the download initiates  
**Then** a pre-signed URL is generated via the API  
**And** the browser downloads the file using the pre-signed URL  
**And** the download works without exposing credentials

**Given** I select one or more objects and click "Delete"  
**When** the confirmation modal appears  
**Then** I see a list of objects to be deleted  
**And** I must type "delete" to confirm  
**And** on confirmation, objects are deleted via API  
**And** deleted objects disappear from the list

**Given** I right-click on an object  
**When** the context menu opens  
**Then** I see options: "Download", "Copy S3 URI", "Copy ARN", "Delete", "Properties"  
**And** "Copy S3 URI" copies `s3://bucket-name/object-key` to clipboard  
**And** "Properties" shows object metadata, tags, and pre-signed URL

**Given** a bucket has 10,000 objects  
**When** I view the object list  
**Then** pagination loads 1000 objects per page  
**And** I can navigate to next/previous pages  
**And** the list loads in <2 seconds

**Given** I want to create a folder  
**When** I click "Create folder"  
**Then** I can enter a folder name  
**And** the folder is created as an object with key `folder-name/` (trailing slash)  
**And** the folder appears in the list immediately

## Technical Notes

**Implementation Files:**
- `web_ui/src/components/services/S3/ObjectBrowser.tsx` - File browser UI
- `web_ui/src/components/services/S3/ObjectUpload.tsx` - Upload modal
- `web_ui/src/hooks/useS3Objects.ts` - S3 object operations hook
- `api/services/s3.py` - S3 object operations (list, upload, download, delete)
- `api/routes/resources.py` - S3 object endpoints

**S3 Object Operations (Backend):**
```python
# api/services/s3.py (additions)

class S3Service:
    async def list_objects(self, bucket_name: str, prefix: str = '', 
                          page_size: int = 1000) -> dict:
        """List objects in bucket with pagination"""
        response = self.client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix,
            MaxKeys=page_size
        )
        
        objects = []
        for obj in response.get('Contents', []):
            objects.append({
                'key': obj['Key'],
                'size': obj['Size'],
                'last_modified': obj['LastModified'].isoformat(),
                'storage_class': obj.get('StorageClass', 'STANDARD')
            })
        
        return {
            'objects': objects,
            'is_truncated': response.get('IsTruncated', False),
            'next_token': response.get('NextContinuationToken')
        }
    
    async def upload_object(self, bucket_name: str, key: str, 
                           file_content: bytes, metadata: dict = None) -> dict:
        """Upload object to S3"""
        extra_args = {}
        if metadata:
            extra_args['Metadata'] = metadata
        
        self.client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=file_content,
            **extra_args
        )
        
        return {'bucket': bucket_name, 'key': key, 'size': len(file_content)}
    
    async def download_object(self, bucket_name: str, key: str) -> str:
        """Generate pre-signed URL for object download"""
        url = self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=3600  # 1 hour
        )
        return url
    
    async def delete_objects(self, bucket_name: str, keys: List[str]) -> dict:
        """Delete multiple objects"""
        objects_to_delete = [{'Key': key} for key in keys]
        
        response = self.client.delete_objects(
            Bucket=bucket_name,
            Delete={'Objects': objects_to_delete}
        )
        
        deleted = response.get('Deleted', [])
        errors = response.get('Errors', [])
        
        return {'deleted_count': len(deleted), 'errors': errors}
```

**Object Browser Component:**
```typescript
// components/services/S3/ObjectBrowser.tsx
import { useState } from 'react';
import { useS3Objects } from '../../hooks';

export function ObjectBrowser({ bucketName }) {
  const [currentPrefix, setCurrentPrefix] = useState('');
  const { objects, loading, uploadObject, deleteObjects, downloadObject } = useS3Objects(bucketName, currentPrefix);
  const [selectedObjects, setSelectedObjects] = useState([]);
  
  const folders = getFolders(objects, currentPrefix);
  const files = getFiles(objects, currentPrefix);
  
  const handleUpload = async (files: FileList) => {
    for (const file of files) {
      const key = currentPrefix + file.name;
      await uploadObject(key, file);
    }
  };
  
  const handleDownload = async (objectKey: string) => {
    const url = await downloadObject(objectKey);
    window.open(url, '_blank');
  };
  
  const handleDelete = async () => {
    if (confirm(`Delete ${selectedObjects.length} objects?`)) {
      await deleteObjects(selectedObjects);
      setSelectedObjects([]);
    }
  };
  
  return (
    <div className="object-browser">
      <Breadcrumbs>
        <BreadcrumbItem onClick={() => setCurrentPrefix('')}>{bucketName}</BreadcrumbItem>
        {currentPrefix.split('/').filter(Boolean).map((part, i, arr) => (
          <BreadcrumbItem 
            key={i}
            onClick={() => setCurrentPrefix(arr.slice(0, i + 1).join('/') + '/')}
          >
            {part}
          </BreadcrumbItem>
        ))}
      </Breadcrumbs>
      
      <div className="actions">
        <Button onClick={() => document.getElementById('file-input').click()}>
          Upload
        </Button>
        <Button onClick={handleDelete} disabled={selectedObjects.length === 0}>
          Delete
        </Button>
        <input
          id="file-input"
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => handleUpload(e.target.files)}
        />
      </div>
      
      <Table
        columns={[
          { key: 'key', label: 'Name', render: (key, obj) => (
            obj.isFolder ? 
              <FolderIcon onClick={() => setCurrentPrefix(key)} /> :
              <FileIcon />
          )},
          { key: 'size', label: 'Size', render: formatBytes },
          { key: 'last_modified', label: 'Last Modified', render: formatDate }
        ]}
        data={[...folders, ...files]}
        selectable
        onSelectionChange={setSelectedObjects}
      />
    </div>
  );
}
```

**API Endpoints:**
```python
# api/routes/resources.py (additions)

@router.get("/buckets/{name}/objects")
async def list_s3_objects(
    name: str, 
    tenant_id: str = Query(...), 
    prefix: str = '',
    page_size: int = 1000
):
    service = S3Service(tenant_id)
    return await service.list_objects(name, prefix, page_size)

@router.post("/buckets/{name}/objects")
async def upload_s3_object(
    name: str,
    key: str,
    file: UploadFile,
    tenant_id: str = Query(...)
):
    service = S3Service(tenant_id)
    content = await file.read()
    return await service.upload_object(name, key, content)

@router.get("/buckets/{name}/objects/{key:path}/download")
async def download_s3_object(name: str, key: str, tenant_id: str = Query(...)):
    service = S3Service(tenant_id)
    url = await service.download_object(name, key)
    return {'download_url': url}

@router.delete("/buckets/{name}/objects")
async def delete_s3_objects(
    name: str,
    keys: List[str],
    tenant_id: str = Query(...)
):
    service = S3Service(tenant_id)
    return await service.delete_objects(name, keys)
```

**Testing:**
- Unit tests: Object list parsing, folder/file distinction, pre-signed URL generation
- Integration tests: Upload file → download file → delete file
- E2E tests: Full object browser workflow with nested folders
- Performance tests: List 10,000 objects in <2s

**NFRs Addressed:**
- NFR-1 (Performance): List 10,000 objects <2s
- FR-5: S3 Service Dashboard (object browser portion)

**Architecture Decisions:**
- AD-7: AWS Console Clone UI (file browser matches AWS S3 console)
