# Story MSCL-11: Lambda Backend CRUD Operations

**Epic:** Epic 3 - Lambda Service Management  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-6 (FastAPI foundation)

## User Story

As a **developer**,  
I want **REST API endpoints for Lambda function CRUD operations**,  
So that **I can manage Lambda functions programmatically**.

## Acceptance Criteria

**Given** I query GET `/api/resources/lambda/functions?tenant_id={id}`  
**When** the request is processed  
**Then** I receive all Lambda functions for that tenant  
**And** each function includes: name, runtime, handler, memory, timeout, environment variables, last_modified

**Given** I send POST `/api/resources/lambda/functions` with function configuration  
**When** the request is processed  
**Then** a new Lambda function is created in MiniStack via boto3  
**And** the function is added to FalkorDB with tenant_id and project tags  
**And** a RESOURCE_CREATED event is emitted

**Given** I query GET `/api/resources/lambda/functions/{name}?tenant_id={id}`  
**When** the request is processed  
**Then** I receive full function details: code, configuration, environment variables, event sources, layers

**Given** I send PUT `/api/resources/lambda/functions/{name}/code` with new code  
**When** the request is processed  
**Then** the function code is updated in MiniStack  
**And** the function state is updated in FalkorDB  
**And** a RESOURCE_UPDATED event is emitted

**Given** I send PUT `/api/resources/lambda/functions/{name}/configuration`  
**When** the request is processed  
**Then** function configuration is updated (environment vars, memory, timeout)  
**And** changes are reflected in FalkorDB  
**And** a RESOURCE_UPDATED event is emitted

**Given** I send DELETE `/api/resources/lambda/functions/{name}?tenant_id={id}`  
**When** the function is deleted  
**Then** the function is removed from MiniStack  
**And** the function is removed from FalkorDB  
**And** all DEPENDS_ON relationships are removed  
**And** a RESOURCE_DELETED event is emitted

## Technical Notes

**Implementation Files:**
- `api/services/lambda_.py` - Lambda service layer
- `api/routes/resources.py` - Lambda endpoints (under `/api/resources/lambda/`)
- `api/models/lambda.py` - Pydantic models for Lambda requests/responses

**Lambda Service Layer:**
```python
# api/services/lambda_.py
class LambdaService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.client = self._create_client()
    
    def _create_client(self):
        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key='dummy'
        )
        return session.client('lambda', endpoint_url='http://localhost:4566')
    
    async def list_functions(self) -> List[dict]:
        """List all Lambda functions"""
        response = self.client.list_functions()
        functions = []
        
        for func in response.get('Functions', []):
            functions.append({
                'name': func['FunctionName'],
                'runtime': func['Runtime'],
                'handler': func['Handler'],
                'memory': func['MemorySize'],
                'timeout': func['Timeout'],
                'last_modified': func['LastModified'],
                'arn': func['FunctionArn'],
                'environment': func.get('Environment', {}).get('Variables', {}),
                'tenant_id': self.tenant_id
            })
        
        return functions
    
    async def create_function(self, name: str, runtime: str, handler: str,
                             code: bytes, project: str = None, 
                             environment: dict = None, memory: int = 128,
                             timeout: int = 3) -> dict:
        """Create Lambda function"""
        # 1. Create function in MiniStack
        params = {
            'FunctionName': name,
            'Runtime': runtime,
            'Role': f'arn:aws:iam::{self.tenant_id}:role/lambda-execution',
            'Handler': handler,
            'Code': {'ZipFile': code},
            'MemorySize': memory,
            'Timeout': timeout
        }
        
        if environment:
            params['Environment'] = {'Variables': environment}
        
        response = self.client.create_function(**params)
        
        # 2. Add to FalkorDB
        resource = {
            'id': f"lambda-function-{name}",
            'type': 'lambda:function',
            'name': name,
            'tenant_id': self.tenant_id,
            'project': project,
            'arn': response['FunctionArn'],
            'state': {
                'runtime': runtime,
                'handler': handler,
                'memory': memory,
                'timeout': timeout,
                'environment': environment or {}
            },
            'created_at': datetime.utcnow().isoformat()
        }
        await graph.add_resource(resource)
        
        # 3. Detect dependencies
        await self._detect_dependencies(resource)
        
        # 4. Emit event
        await event_bus.publish("RESOURCE_CREATED", resource)
        
        return resource
    
    async def update_function_code(self, name: str, code: bytes) -> dict:
        """Update Lambda function code"""
        response = self.client.update_function_code(
            FunctionName=name,
            ZipFile=code
        )
        
        # Update FalkorDB
        await graph.update_resource(f"lambda-function-{name}", {
            'state.last_modified': response['LastModified']
        })
        
        # Emit event
        await event_bus.publish("RESOURCE_UPDATED", {'id': f"lambda-function-{name}", 'type': 'lambda:function'})
        
        return {'updated': name, 'last_modified': response['LastModified']}
    
    async def delete_function(self, name: str) -> dict:
        """Delete Lambda function"""
        # 1. Delete from MiniStack
        self.client.delete_function(FunctionName=name)
        
        # 2. Remove from FalkorDB
        await graph.delete_resource(f"lambda-function-{name}")
        
        # 3. Emit event
        await event_bus.publish("RESOURCE_DELETED", {'id': f"lambda-function-{name}", 'type': 'lambda:function'})
        
        return {'deleted': name}
    
    async def _detect_dependencies(self, function_resource: dict):
        """Detect Lambda dependencies (S3, SQS, etc.)"""
        # Extract dependencies from environment variables
        env_vars = function_resource['state'].get('environment', {})
        
        for key, value in env_vars.items():
            # S3 bucket references
            if 'arn:aws:s3:::' in value:
                bucket_name = value.split('arn:aws:s3:::')[-1].split('/')[0]
                await graph.create_dependency(
                    source_id=function_resource['id'],
                    target_type='s3:bucket',
                    target_name=bucket_name,
                    dependency_type='environment_variable'
                )
```

**Testing:**
- Unit tests: Function creation, code update, environment variable parsing
- Integration tests: Create function → invoke function → delete function
- Dependency tests: Lambda with S3 env var → verify DEPENDS_ON created

**NFRs Addressed:**
- FR-5: Lambda Service Dashboard (backend portion)
- NFR-1 (Performance): List functions <500ms

**Architecture Decisions:**
- AD-1: REST API as Core Backend
- AD-5: Python Backend with FastAPI
