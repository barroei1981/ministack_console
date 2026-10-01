# Story MSCL-5: Resource Dependency Detection

**Epic:** Epic 1 - Control-Plane Foundation  
**Story Points:** 8  
**Priority:** P1  
**Dependencies:** MSCL-1, MSCL-2

## User Story

As a **developer**,  
I want **automatic detection of resource dependencies (Lambda→S3, Lambda→SQS, etc.)**,  
So that **I can visualize my architecture and understand impact before deleting resources**.

## Acceptance Criteria

**Given** a Lambda function has environment variables referencing an S3 bucket ARN  
**When** dependency detection runs  
**Then** a `(:Resource)-[:DEPENDS_ON]->(:Resource)` relationship is created from Lambda to S3  
**And** I can query "What does this Lambda depend on?" and see the S3 bucket

**Given** a Lambda function has an event source mapping to an SQS queue  
**When** dependency detection runs  
**Then** a DEPENDS_ON relationship is created from Lambda to SQS  
**And** the relationship metadata includes the mapping type

**Given** an S3 bucket has a bucket policy referencing IAM roles  
**When** dependency detection runs  
**Then** a DEPENDS_ON relationship is created from S3 to IAM role  
**And** policy details are stored in relationship properties

**Given** a CloudFormation stack manages multiple resources  
**When** dependency detection runs  
**Then** DEPENDS_ON relationships are created from stack to all managed resources  
**And** I can query "What resources are in this stack?"

**Given** a dependency no longer exists (Lambda env var removed)  
**When** dependency detection runs  
**Then** the DEPENDS_ON relationship is removed from FalkorDB  
**And** a DEPENDENCY_REMOVED event is emitted

**Given** I query "What depends on this S3 bucket?"  
**When** the query executes  
**Then** all resources with DEPENDS_ON relationships to that bucket are returned  
**And** the dependency type is included (e.g., "environment_variable", "event_source")

## Technical Notes

**Implementation Files:**
- `control_plane/graph/relationships.py` - Dependency detection logic
- `control_plane/inventory/detector.py` - Resource introspection
- `api/routes/graph.py` - Graph query endpoints

**Dependency Detection Patterns:**

**Lambda → S3:**
```python
async def detect_lambda_s3_dependencies(lambda_resource):
    """Detect S3 dependencies from Lambda environment variables and IAM policy"""
    dependencies = []
    
    # 1. Environment variables
    env_vars = lambda_resource.state.get("Environment", {}).get("Variables", {})
    for key, value in env_vars.items():
        if "arn:aws:s3:::" in value:
            bucket_name = value.split("arn:aws:s3:::")[-1].split("/")[0]
            s3_resource = await graph.find_resource(type="s3:bucket", name=bucket_name)
            if s3_resource:
                dependencies.append({
                    "target_id": s3_resource.id,
                    "type": "environment_variable",
                    "metadata": {"env_var": key}
                })
    
    # 2. IAM policy ARNs (if policy is inline)
    # ... parse IAM policy for S3 resource ARNs
    
    return dependencies
```

**Lambda → SQS/SNS:**
```python
async def detect_lambda_event_sources(lambda_resource):
    """Detect event source mappings"""
    dependencies = []
    
    # Query MiniStack for event source mappings
    mappings = lambda_client.list_event_source_mappings(
        FunctionName=lambda_resource.name
    ).get("EventSourceMappings", [])
    
    for mapping in mappings:
        event_source_arn = mapping["EventSourceArn"]
        
        # Parse ARN to determine service (SQS, SNS, DynamoDB Stream, etc.)
        if ":sqs:" in event_source_arn:
            queue_name = event_source_arn.split(":")[-1]
            sqs_resource = await graph.find_resource(type="sqs:queue", name=queue_name)
            if sqs_resource:
                dependencies.append({
                    "target_id": sqs_resource.id,
                    "type": "event_source_mapping",
                    "metadata": {"mapping_uuid": mapping["UUID"]}
                })
    
    return dependencies
```

**S3 → IAM:**
```python
async def detect_s3_iam_dependencies(s3_resource):
    """Detect IAM dependencies from S3 bucket policy"""
    dependencies = []
    
    try:
        policy = s3_client.get_bucket_policy(Bucket=s3_resource.name)
        policy_json = json.loads(policy["Policy"])
        
        # Parse policy for IAM principal ARNs
        for statement in policy_json.get("Statement", []):
            principal = statement.get("Principal", {})
            if isinstance(principal, dict) and "AWS" in principal:
                arns = principal["AWS"] if isinstance(principal["AWS"], list) else [principal["AWS"]]
                
                for arn in arns:
                    if ":iam:" in arn and ":role/" in arn:
                        role_name = arn.split(":role/")[-1]
                        iam_resource = await graph.find_resource(type="iam:role", name=role_name)
                        if iam_resource:
                            dependencies.append({
                                "target_id": iam_resource.id,
                                "type": "bucket_policy",
                                "metadata": {"statement_effect": statement.get("Effect")}
                            })
    except ClientError:
        # Bucket has no policy
        pass
    
    return dependencies
```

**Graph Queries:**
```cypher
// What does resource X depend on?
MATCH (source:Resource {id: $resource_id})-[dep:DEPENDS_ON]->(target:Resource)
RETURN target, dep.type, dep.metadata

// What depends on resource Y?
MATCH (source:Resource)-[dep:DEPENDS_ON]->(target:Resource {id: $resource_id})
RETURN source, dep.type, dep.metadata

// Transitive dependencies (what X depends on, and what those depend on)
MATCH path = (source:Resource {id: $resource_id})-[:DEPENDS_ON*1..3]->(target:Resource)
RETURN path
```

**Testing:**
- Unit tests: Each detection pattern, ARN parsing, relationship creation
- Integration tests: Create Lambda with S3 dependency → verify DEPENDS_ON created
- E2E tests: Delete S3 bucket with dependents → system warns about dependencies

**NFRs Addressed:**
- FR-2: Resource Graph with dependency detection
- NFR-1 (Performance): Graph render <1s for 500 nodes

**Architecture Decisions:**
- AD-2: FalkorDB for Resource Graph
