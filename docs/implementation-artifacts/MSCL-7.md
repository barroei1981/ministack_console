# Story MSCL-7: Server-Sent Events (SSE) for Real-Time Updates

**Epic:** Epic 1 - Control-Plane Foundation  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-2, MSCL-6

## User Story

As a **developer using the Web UI**,  
I want **real-time updates when resources change in MiniStack**,  
So that **I don't have to manually refresh to see new resources, modifications, or deletions**.

## Acceptance Criteria

**Given** the Web UI is open and connected to the SSE endpoint  
**When** a new S3 bucket is created in MiniStack  
**Then** within 5 seconds, I receive a RESOURCE_CREATED event  
**And** the UI automatically adds the new bucket to the list without page refresh

**Given** I have an SSE connection active  
**When** a Lambda function's configuration is updated in MiniStack  
**Then** within 35 seconds (poll interval + processing), I receive a RESOURCE_UPDATED event  
**And** the UI updates the function's details automatically

**Given** an SSE connection is active  
**When** a DynamoDB table is deleted in MiniStack  
**Then** within 35 seconds, I receive a RESOURCE_DELETED event  
**And** the UI removes the table from the list automatically

**Given** a new dependency is detected (Lambda→S3)  
**When** dependency detection completes  
**Then** I receive a DEPENDENCY_ADDED event  
**And** the graph visualization updates to show the new edge

**Given** a dependency is removed (Lambda env var deleted)  
**When** dependency detection detects the removal  
**Then** I receive a DEPENDENCY_REMOVED event  
**And** the graph visualization updates to remove the edge

**Given** I am viewing a resource's tags  
**When** tags are updated via the API or directly in MiniStack  
**Then** I receive a TAGS_UPDATED event  
**And** the UI refreshes the tag display

**Given** my SSE connection drops (network issue)  
**When** the connection is lost  
**Then** the browser automatically reconnects using EventSource's built-in reconnect  
**And** I don't lose any events (events are queued server-side for reconnect)

**Given** 10 concurrent users have SSE connections to the same tenant  
**When** a resource event occurs  
**Then** all 10 connections receive the event  
**And** the server handles 10 concurrent SSE streams without performance degradation

## Technical Notes

**Implementation Files:**
- `api/routes/sse.py` - SSE endpoint
- `control_plane/event_bus.py` - Pub/sub event bus for distributing events
- `web_ui/hooks/useSSE.ts` - React hook for SSE client

**Event Bus (Server-Side):**
```python
from typing import Dict, List
import asyncio

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
    
    async def subscribe(self, tenant_id: str) -> asyncio.Queue:
        """Subscribe to events for a tenant"""
        queue = asyncio.Queue()
        if tenant_id not in self.subscribers:
            self.subscribers[tenant_id] = []
        self.subscribers[tenant_id].append(queue)
        return queue
    
    async def unsubscribe(self, tenant_id: str, queue: asyncio.Queue):
        """Unsubscribe from events"""
        if tenant_id in self.subscribers:
            self.subscribers[tenant_id].remove(queue)
    
    async def publish(self, event_type: str, resource: dict):
        """Publish an event to all subscribers of this tenant"""
        tenant_id = resource.get('tenant_id')
        if tenant_id in self.subscribers:
            event = {
                'type': event_type,
                'resource': resource,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            for queue in self.subscribers[tenant_id]:
                await queue.put(event)

event_bus = EventBus()
```

**SSE Endpoint:**
```python
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()

@router.get("/api/sse")
async def sse_endpoint(tenant_id: str = Query(...)):
    """Server-Sent Events stream for real-time updates"""
    
    async def event_generator():
        queue = await event_bus.subscribe(tenant_id)
        
        try:
            while True:
                # Wait for next event
                event = await queue.get()
                
                # Format as SSE
                yield f"data: {json.dumps(event)}\n\n"
        
        except asyncio.CancelledError:
            await event_bus.unsubscribe(tenant_id, queue)
            raise
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
```

**SSE Client (React):**
```typescript
// hooks/useSSE.ts
import { useEffect } from 'react';
import { useResourceStore } from '../store';

export function useSSE(tenantId: string) {
  const { updateResource, deleteResource } = useResourceStore();
  
  useEffect(() => {
    const eventSource = new EventSource(
      `http://localhost:3001/api/sse?tenant_id=${tenantId}`
    );
    
    eventSource.onmessage = (event) => {
      const change = JSON.parse(event.data);
      
      if (change.type === 'RESOURCE_CREATED' || change.type === 'RESOURCE_UPDATED') {
        updateResource(change.resource);
      } else if (change.type === 'RESOURCE_DELETED') {
        deleteResource(change.resource_id);
      } else if (change.type === 'DEPENDENCY_ADDED') {
        // Trigger graph re-render
      } else if (change.type === 'DEPENDENCY_REMOVED') {
        // Trigger graph re-render
      } else if (change.type === 'TAGS_UPDATED') {
        updateResource(change.resource);
      }
    };
    
    eventSource.onerror = () => {
      // Auto-reconnect handled by EventSource
      console.error('SSE connection error');
    };
    
    return () => eventSource.close();
  }, [tenantId]);
}
```

**Event Types:**
- `RESOURCE_CREATED`: New resource discovered in MiniStack
- `RESOURCE_UPDATED`: Resource state changed
- `RESOURCE_DELETED`: Resource removed from MiniStack
- `DEPENDENCY_ADDED`: New dependency relationship detected
- `DEPENDENCY_REMOVED`: Dependency no longer exists
- `TAGS_UPDATED`: Resource tags modified

**Integration with Poller:**
```python
# In control_plane/inventory/sync.py
async def sync_resource(resource):
    # 1. Update FalkorDB
    await graph.upsert_resource(resource)
    
    # 2. Emit SSE event
    await event_bus.publish("RESOURCE_UPDATED", resource)
```

**Testing:**
- Unit tests: Event bus subscribe/publish, event serialization
- Integration tests: Create resource → verify SSE event received
- E2E tests: Browser receives event → UI updates automatically
- Load tests: 100 concurrent SSE connections

**NFRs Addressed:**
- NFR-1 (Performance): Real-time updates <5s latency
- NFR-2 (Scalability): 10 concurrent SSE connections per tenant

**Architecture Decisions:**
- AD-4: Server-Sent Events (SSE) for Real-time Updates
