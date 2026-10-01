# Story MSCL-2: MiniStack Integration and Resource Polling

**Epic:** Epic 1 - Control-Plane Foundation  
**Story Points:** 8  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-1 (FalkorDB schema must exist)

## User Story

As a **developer**,  
I want **the control-plane to automatically poll MiniStack and track all resources**,  
So that **I have a real-time inventory of my local AWS environment**.

## Acceptance Criteria

**Given** MiniStack is running on localhost:4566  
**When** the control-plane starts  
**Then** it connects to MiniStack successfully  
**And** begins polling every 30 seconds (configurable)  
**And** detects the MiniStack health status

**Given** MiniStack has resources (S3 buckets, Lambda functions, DynamoDB tables)  
**When** the poller runs  
**Then** all resources are discovered and stored in FalkorDB  
**And** each resource has: id, type, name, tenant_id, arn, state, created_at, updated_at  
**And** resources are grouped by tenant (12-digit access key)

**Given** a new resource is created in MiniStack  
**When** the next poll cycle runs  
**Then** the new resource is detected and added to FalkorDB  
**And** a RESOURCE_CREATED event is emitted

**Given** a resource is deleted from MiniStack  
**When** the next poll cycle runs  
**Then** the resource is removed from FalkorDB  
**And** a RESOURCE_DELETED event is emitted

**Given** a resource is modified in MiniStack  
**When** the next poll cycle runs  
**Then** the resource state is updated in FalkorDB  
**And** a RESOURCE_UPDATED event is emitted

**Given** MiniStack is unreachable  
**When** the poller attempts to connect  
**Then** it retries 2 times with exponential backoff (1s, 2s)  
**And** after 3 consecutive failures, marks all resources as "stale"  
**And** logs the error for debugging

**Given** MiniStack restarts (state cleared)  
**When** the poller detects the restart via health check  
**Then** it performs a full re-inventory  
**And** clears all stale markers  
**And** completes within 1 minute

## Technical Notes

**Implementation Files:**
- `control_plane/inventory/poller.py` - Main polling loop and change detection
- `control_plane/inventory/detector.py` - Change detection logic
- `control_plane/inventory/sync.py` - Sync resources to FalkorDB
- `control_plane/ministack_client.py` - boto3 wrapper for MiniStack
- `config.py` - Polling interval configuration

**boto3 Client Configuration:**
```python
import boto3
from botocore.config import Config

config = Config(
    region_name='us-east-1',
    signature_version='s3v4',
    retries={'max_attempts': 3}
)

session = boto3.Session(
    aws_access_key_id=tenant_access_key,  # 12-digit MiniStack tenant ID
    aws_secret_access_key='dummy',
    region_name='us-east-1'
)

# Service clients
s3 = session.client('s3', endpoint_url='http://localhost:4566', config=config)
lambda_client = session.client('lambda', endpoint_url='http://localhost:4566')
dynamodb = session.resource('dynamodb', endpoint_url='http://localhost:4566')
```

**Polling Algorithm:**
```python
async def poll_ministack():
    while True:
        try:
            # 1. Health check MiniStack
            if not ministack_healthy():
                await detect_restart()
                continue
            
            # 2. Poll each service (S3, Lambda, DynamoDB, etc.)
            for service in enabled_services:
                resources = await fetch_resources(service)
                changes = detect_changes(resources, last_snapshot)
                
                # 3. Update inventory
                for change in changes:
                    if change.type == "CREATED":
                        await inventory.add_resource(change.resource)
                    elif change.type == "MODIFIED":
                        await inventory.update_resource(change.resource)
                    elif change.type == "DELETED":
                        await inventory.delete_resource(change.resource_id)
                    
                    # 4. Emit event for SSE
                    await event_bus.publish(change)
            
            await asyncio.sleep(30)  # Configurable interval
        except Exception as e:
            logger.error(f"Poll error: {e}")
            await asyncio.sleep(5)
```

**Phase 1 Services to Poll:**
- S3: `list_buckets()`, `get_bucket_versioning()`, `get_bucket_tagging()`
- Lambda: `list_functions()`, `get_function()`, `get_function_configuration()`
- DynamoDB: `list_tables()`, `describe_table()`

**Testing:**
- Unit tests: Change detection algorithm, tenant extraction
- Integration tests: Full polling cycle with real MiniStack
- E2E tests: Create resource in MiniStack → verify appears in FalkorDB within 30s

**NFRs Addressed:**
- NFR-1 (Performance): Real-time updates <5s latency (30s poll + processing)
- NFR-3 (Reliability): MiniStack restart handling with 1 minute re-inventory
- AD-8: Resource Polling Strategy (30s interval, incremental updates)
- AD-12: Hybrid Polling Error Handling (retry, staleness, alerts)

**Architecture Decisions:**
- AD-8: Resource Polling Strategy
- AD-12: Hybrid Polling Error Handling
