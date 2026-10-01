# Story MSCL-8: S3 Backend CRUD Operations

**Epic:** Epic 2 - S3 Service Management  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-6 (FastAPI foundation)

## User Story

As a **developer**,  
I want **REST API endpoints for S3 bucket CRUD operations**,  
So that **both the Web UI and MCP Server can manage S3 buckets**.

## Acceptance Criteria

**Given** I query GET `/api/resources/s3/buckets?tenant_id={id}`  
**When** the request is processed  
**Then** I receive all S3 buckets for that tenant  
**And** each bucket includes: name, region, versioning status, tags, created_at  
**And** results are paginated (100 buckets per page)

**Given** I send POST `/api/resources/s3/buckets` with bucket configuration  
**When** the request is processed  
**Then** a new bucket is created in MiniStack via boto3  
**And** the bucket is added to FalkorDB with tenant_id and project tags  
**And** a RESOURCE_CREATED event is emitted  
**And** I receive a 201 Created with the bucket details

**Given** I query GET `/api/resources/s3/buckets/{name}?tenant_id={id}`  
**When** the request is processed  
**Then** I receive full bucket details: versioning, tagging, ACLs, policy  
**And** I receive object count and total size (if available)

**Given** I send DELETE `/api/resources/s3/buckets/{name}?tenant_id={id}`  
**When** the bucket is empty  
**Then** the bucket is deleted from MiniStack  
**And** the bucket is removed from FalkorDB  
**And** all DEPENDS_ON relationships are removed  
**And** a RESOURCE_DELETED event is emitted

**Given** I send DELETE `/api/resources/s3/buckets/{name}?tenant_id={id}&force=true`  
**When** the bucket has objects  
**Then** all objects are deleted first  
**And** the bucket is deleted  
**And** I receive a 200 OK with deletion summary

**Given** I send PUT `/api/resources/s3/buckets/{name}/versioning` with `{"enabled": true}`  
**When** the request is processed  
**Then** versioning is enabled on the bucket in MiniStack  
**And** the bucket state is updated in FalkorDB  
**And** a RESOURCE_UPDATED event is emitted

**Given** I send an invalid bucket name (uppercase, special chars)  
**When** the API validates the request  
**Then** I receive a 400 Bad Request with clear error message  
**And** the error explains AWS S3 bucket naming rules

## Technical Notes

**Implementation Files:**
- `api/services/s3.py` - S3 service layer with boto3 operations
- `api/routes/resources.py` - S3 endpoints (under `/api/resources/s3/`)
- `api/models/s3.py` - Pydantic models for S3 requests/responses

**S3 Service Layer:**
```python
# api/services/s3.py
from botocore.exceptions import ClientError
import boto3

class S3Service:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.client = self._create_client()
    
    def _create_client(self):
        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key='dummy',
            region_name='us-east-1'
        )
        return session.client('s3', endpoint_url='http://localhost:4566')
    
    async def list_buckets(self) -> List[dict]:
        """List all S3 buckets for tenant"""
        response = self.client.list_buckets()
        buckets = []
        
        for bucket in response.get('Buckets', []):
            bucket_name = bucket['Name']
            
            # Get additional details
            try:
                versioning = self.client.get_bucket_versioning(Bucket=bucket_name)
                tags_response = self.client.get_bucket_tagging(Bucket=bucket_name)
                tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagSet', [])}
            except ClientError:
                versioning = {}
                tags = {}
            
            buckets.append({
                'name': bucket_name,
                'created_at': bucket['CreationDate'].isoformat(),
                'versioning': versioning.get('Status', 'Disabled'),
                'tags': tags,
                'tenant_id': self.tenant_id
            })
        
        return buckets
    
    async def create_bucket(self, name: str, project: str = None, 
                           versioning: bool = False) -> dict:
        """Create S3 bucket in MiniStack"""
        # 1. Validate bucket name
        self._validate_bucket_name(name)
        
        # 2. Create bucket in MiniStack
        self.client.create_bucket(Bucket=name)
        
        # 3. Enable versioning if requested
        if versioning:
            self.client.put_bucket_versioning(
                Bucket=name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
        
        # 4. Apply project tag if provided
        if project:
            await self._tag_bucket(name, {'project': project})
        
        # 5. Add to FalkorDB
        resource = {
            'id': f"s3-bucket-{name}",
            'type': 's3:bucket',
            'name': name,
            'tenant_id': self.tenant_id,
            'project': project,
            'arn': f"arn:aws:s3:::{name}",
            'state': {'versioning': 'Enabled' if versioning else 'Disabled'},
            'created_at': datetime.utcnow().isoformat()
        }
        await graph.add_resource(resource)
        
        # 6. Emit event
        await event_bus.publish("RESOURCE_CREATED", resource)
        
        return resource
    
    async def delete_bucket(self, name: str, force: bool = False) -> dict:
        """Delete S3 bucket"""
        # 1. Check if bucket has objects
        objects = self.client.list_objects_v2(Bucket=name).get('Contents', [])
        
        if objects and not force:
            raise ValueError(f"Bucket {name} is not empty. Use force=true to delete.")
        
        # 2. Delete all objects if force=true
        if force and objects:
            for obj in objects:
                self.client.delete_object(Bucket=name, Key=obj['Key'])
        
        # 3. Delete bucket from MiniStack
        self.client.delete_bucket(Bucket=name)
        
        # 4. Remove from FalkorDB
        await graph.delete_resource(f"s3-bucket-{name}")
        
        # 5. Emit event
        await event_bus.publish("RESOURCE_DELETED", {'id': f"s3-bucket-{name}", 'type': 's3:bucket'})
        
        return {'deleted': name, 'objects_deleted': len(objects) if force else 0}
```

**API Endpoints:**
```python
# api/routes/resources.py
from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/resources/s3")

@router.get("/buckets")
async def list_s3_buckets(tenant_id: str = Query(...)):
    service = S3Service(tenant_id)
    return await service.list_buckets()

@router.post("/buckets", status_code=201)
async def create_s3_bucket(request: CreateBucketRequest):
    service = S3Service(request.tenant_id)
    return await service.create_bucket(
        name=request.name,
        project=request.project,
        versioning=request.versioning
    )

@router.delete("/buckets/{name}")
async def delete_s3_bucket(name: str, tenant_id: str = Query(...), force: bool = False):
    service = S3Service(tenant_id)
    return await service.delete_bucket(name, force=force)
```

**Testing:**
- Unit tests: Bucket name validation, boto3 mock operations
- Integration tests: Create bucket in MiniStack → verify in FalkorDB
- E2E tests: API call → bucket created → SSE event → UI updates

**NFRs Addressed:**
- NFR-1 (Performance): List 1000 buckets in <500ms
- FR-5: S3 Service Dashboard (backend portion)

**Architecture Decisions:**
- AD-1: REST API as Core Backend
- AD-5: Python Backend with FastAPI
