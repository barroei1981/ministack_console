# Story MSCL-4: Dual Tagging System (Control-Plane + Native)

**Epic:** Epic 1 - Control-Plane Foundation  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-1, MSCL-2, MSCL-3

## User Story

As a **developer**,  
I want **two independent tagging systems: control-plane tags (all resources) and native MiniStack tags (taggable services only)**,  
So that **I can organize resources by project while maintaining AWS CLI/SDK compatibility**.

## Acceptance Criteria

**Given** I tag a resource with control-plane tags (e.g., `project: microservice-a`)  
**When** the tag is applied  
**Then** it is stored in FalkorDB as a relationship `(:Resource)-[:TAGGED_WITH {key, value}]->(:Tag)`  
**And** the tag applies to the resource regardless of service type  
**And** I can query resources by control-plane tag

**Given** I tag an S3 bucket with native MiniStack tags (e.g., `Name: my-bucket`)  
**When** the tag is applied  
**Then** it is written to both FalkorDB (namespace: "native") and MiniStack via boto3  
**And** the tag is visible in AWS CLI: `aws s3api get-bucket-tagging`  
**And** I can query resources by native tag in FalkorDB

**Given** I tag a Lambda function with control-plane tags  
**When** the tag is applied  
**Then** the tag is stored in FalkorDB only (control-plane tags don't propagate to MiniStack)  
**And** Lambda native tags are handled separately via MiniStack API

**Given** I query resources by project tag  
**When** the query executes  
**Then** all resources with that project tag are returned  
**And** resources span multiple service types (S3, Lambda, DynamoDB, etc.)

**Given** a CloudFormation stack creates resources  
**When** the stack has control-plane tags  
**Then** all created resources inherit the stack's control-plane tags  
**And** tag propagation is automatic

**Given** I attempt to apply native tags to a non-taggable service (e.g., SQS in some MiniStack versions)  
**When** the tag operation executes  
**Then** the tag is stored in FalkorDB only  
**And** no boto3 call is made to MiniStack  
**And** the system logs a warning

## Technical Notes

**Implementation Files:**
- `control_plane/tagging/control_plane.py` - Control-plane tag operations
- `control_plane/tagging/native.py` - Native MiniStack tag operations
- `api/routes/tags.py` - Tag API endpoints
- `api/models/tag.py` - Pydantic tag models

**Control-Plane Tags (FalkorDB):**
```cypher
// Add control-plane tag
MATCH (r:Resource {id: $resource_id})
CREATE (r)-[:TAGGED_WITH {key: $key, value: $value, namespace: 'control_plane'}]->(:Tag {key: $key})

// Query resources by control-plane tag
MATCH (r:Resource)-[:TAGGED_WITH {key: $key, value: $value, namespace: 'control_plane'}]->(:Tag)
RETURN r

// Get all control-plane tags for a resource
MATCH (r:Resource {id: $resource_id})-[t:TAGGED_WITH {namespace: 'control_plane'}]->(:Tag)
RETURN t.key, t.value
```

**Native MiniStack Tags (boto3 + FalkorDB):**
```python
async def tag_resource_native(resource_id: str, tags: dict):
    """Apply native tags to MiniStack resource (write-through)"""
    resource = await graph.get_resource(resource_id)
    
    # 1. Write to FalkorDB (always)
    await graph.add_tags(resource_id, tags, namespace="native")
    
    # 2. Write to MiniStack (if service supports native tagging)
    if resource.type in TAGGABLE_SERVICES:
        if resource.type == "s3:bucket":
            s3_client.put_bucket_tagging(
                Bucket=resource.name,
                Tagging={'TagSet': [{'Key': k, 'Value': v} for k, v in tags.items()]}
            )
        elif resource.type == "lambda:function":
            lambda_client.tag_resource(
                Resource=resource.arn,
                Tags=tags
            )
    
    # 3. Emit event
    await event_bus.publish("RESOURCE_TAGGED", resource_id, tags)
```

**Taggable Services (Phase 1):**
```python
TAGGABLE_SERVICES = [
    "s3:bucket",
    "lambda:function",
    "dynamodb:table"
]
```

**Tag Data Model:**
```python
class Tag(BaseModel):
    key: str
    value: str
    namespace: Literal["control_plane", "native"]

class ResourceTags(BaseModel):
    control_plane: Dict[str, str]  # Always present
    native: Dict[str, str]          # Only if service supports native tags
```

**Testing:**
- Unit tests: Control-plane tag CRUD, native tag write-through, namespace isolation
- Integration tests: Tag S3 bucket → verify in both FalkorDB and MiniStack
- E2E tests: Query by project tag across multiple service types

**NFRs Addressed:**
- FR-4: Project Tagging
- NFR-6 (Compatibility): AWS CLI/SDK compatibility via native tags

**Architecture Decisions:**
- AD-3: Dual Tagging System
