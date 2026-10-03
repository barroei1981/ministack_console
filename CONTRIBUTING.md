# Contributing to MiniStack Console

Thank you for considering contributing! This project aims to provide a free, open-source AWS Console clone for MiniStack.

## Ways to Contribute

### 1. Add More AWS Services (Most Needed!)

We have **79 services** left to implement out of 87 total. Each service follows a proven pattern.

**Time Estimate:**
- Basic service (list only): ~30 minutes
- Full CRUD service: ~2 hours
- Complex service (IAM, CloudFormation): ~4-6 hours

**Priority Services:**
1. EC2 (instances, security groups, key pairs)
2. RDS (databases, snapshots)
3. IAM (users, roles, policies)
4. KMS (keys, encryption)
5. CloudWatch (logs, metrics)
6. EventBridge (rules, event buses)
7. Step Functions (state machines)
8. API Gateway (REST APIs)
9. CloudFormation (stacks)
10. ECS (clusters, tasks, services)

See [GitHub Issues](https://github.com/barroei1981/ministack_console/issues) for the full list.

### 2. Improve Documentation

- Add screenshots
- Create video tutorials
- Write blog posts
- Improve API documentation

### 3. Report Bugs

Open an [issue](https://github.com/barroei1981/ministack_console/issues/new) with:
- What you expected
- What happened
- Steps to reproduce
- Browser/OS info

### 4. Suggest Features

Use [GitHub Discussions](https://github.com/barroei1981/ministack_console/discussions) to propose ideas.

## Development Setup

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.11+ (for backend development)
- MiniStack running on localhost:4566

### Clone and Run

```bash
# Clone
git clone https://github.com/barroei1981/ministack_console
cd ministack_console

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Access
open http://localhost:3000  # Web UI
open http://localhost:3001/api/docs  # API docs
```

### Development Mode (Hot Reload)

**Frontend:**
```bash
cd web_ui
npm install
npm run dev
# Access on http://localhost:5173
```

**Backend:**
```bash
cd api
pip install -e .
uvicorn api.main:app --reload --port 3001
```

**MCP Server:**
```bash
cd mcp_server
python -m mcp_server.server_simple
```

## Service Implementation Guide

Adding a new service follows this pattern:

### Step 1: Backend Service Layer

Create `/api/services/{service}.py`:

```python
"""Service layer for {ServiceName} operations."""
import asyncio
import re
from typing import Any
import boto3
from control_plane.graph.query import query_nodes
from control_plane.observability import log_operational, trace_operation

class ServiceNameService:
    def __init__(self, tenant_id: str):
        if not tenant_id or not re.match(r"^\d{12}$", tenant_id):
            raise ValueError("Tenant ID must be exactly 12 digits")
        self.tenant_id = tenant_id
        self.client = self._create_client()

    def _create_client(self) -> Any:
        import os
        endpoint = os.getenv("MINISTACK_ENDPOINT", "http://localhost:4566")
        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key="dummy",
            region_name="us-east-1",
        )
        return session.client("service-name", endpoint_url=endpoint)

    async def list_resources(self) -> list[dict[str, Any]]:
        with trace_operation("list_resources", tenant_id=self.tenant_id):
            try:
                # Query from FalkorDB cache first
                nodes = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"tenant_id": self.tenant_id, "type": "service:resource"},
                )
                log_operational("Listed resources", tenant_id=self.tenant_id, count=len(nodes))
                return nodes
            except Exception as e:
                log_operational("Failed to list resources", tenant_id=self.tenant_id, error=str(e))
                raise
```

### Step 2: Add API Routes

Add to `/api/routes/resources.py`:

```python
@router.get("/resources/service-name/resources")
async def list_service_resources(tenant_id: str = "000000000001"):
    """List resources."""
    try:
        from api.services.service_name import ServiceNameService
        service = ServiceNameService(tenant_id)
        resources = await service.list_resources()
        return {"resources": resources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list: {str(e)}")
```

### Step 3: Add Sync Function

Add to `/api/sync_resources.py`:

```python
async def sync_service_name_resources(tenant_id: str, boto_session: Any):
    """Sync service resources."""
    client = boto_session.client("service-name", endpoint_url=MINISTACK_ENDPOINT)
    
    try:
        # List from MiniStack
        response = client.list_resources()
        
        # Store in FalkorDB
        for resource in response.get("Resources", []):
            resource_node = {
                "id": resource["Id"],
                "name": resource["Name"],
                "tenant_id": tenant_id,
                "type": "service:resource",
                "arn": resource["Arn"],
                "created_at": datetime.now().isoformat(),
            }
            
            create_or_update_node(
                "Resource",
                {"id": resource_node["id"], "tenant_id": tenant_id},
                resource_node,
            )
            
        log_operational(f"Synced {len(response['Resources'])} resources")
    except Exception as e:
        log_operational(f"Sync failed: {e}")
```

### Step 4: Frontend Component

Create `/web_ui/src/components/services/ServiceName/ResourceList.tsx`:

```typescript
import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export const ResourceList: React.FC = () => {
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id') || '000000000001';
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ['service-resources', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/resources/service-name/resources?tenant_id=${tenantId}`
      );
      if (!response.ok) throw new Error('Failed to fetch');
      return response.json() as Promise<{ resources: any[] }>;
    },
    refetchInterval: 10000,
  });

  if (isLoading) return <div style={{ padding: '20px' }}><h2>Resources</h2><p>Loading...</p></div>;
  if (error) return <div style={{ padding: '20px' }}><h2>Resources</h2><p style={{ color: 'red' }}>Error: {(error as Error).message}</p></div>;

  const resources = data?.resources || [];

  return (
    <div style={{ padding: '20px' }}>
      <h2>Service Name Resources</h2>
      {resources.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', backgroundColor: '#f5f5f5', borderRadius: '8px' }}>
          <p style={{ color: '#666' }}>No resources found.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '12px' }}>
          {resources.map((resource: any, i: number) => (
            <div key={i} style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '16px', backgroundColor: 'white' }}>
              <div style={{ fontWeight: 600 }}>{resource.name || 'Resource'}</div>
              <div style={{ fontSize: '14px', color: '#666', marginTop: '8px' }}>{resource.id}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
```

### Step 5: Add Route to App

Add to `/web_ui/src/App.tsx`:

```typescript
import { ResourceList } from './components/services/ServiceName/ResourceList';

// In Routes:
<Route path="/service-name/resources" element={<ResourceList />} />
```

### Step 6: Add to Home Page

Add to `/web_ui/src/components/Home.tsx`:

```typescript
<ServiceCard
  name="Service Name"
  description="Service description"
  path="/service-name/resources"
/>
```

### Step 7: Add MCP Tool (Optional)

Add to `/mcp_server/server_simple.py`:

```python
@mcp.tool()
async def list_service_resources(tenant_id: str = "000000000001") -> str:
    """List service resources."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://api:3001/api/resources/service-name/resources?tenant_id={tenant_id}",
            timeout=10.0
        )
        response.raise_for_status()
        return response.text
```

## Code Style

### Python (Backend)

- **Formatter:** Black (line length 100)
- **Linter:** Ruff
- **Type hints:** Required for all functions
- **Async:** Use `async`/`await` for I/O operations
- **Logging:** Use structured logging (`log_operational`, `log_security`, `log_audit`)

```python
# Good
async def create_resource(name: str, tenant_id: str) -> dict[str, Any]:
    """Create a resource."""
    log_operational("Creating resource", name=name, tenant_id=tenant_id)
    # ...

# Bad
def create_resource(name, tenant_id):
    print(f"Creating {name}")
    # ...
```

### TypeScript (Frontend)

- **Formatter:** Prettier
- **Linter:** ESLint
- **Style:** Functional components with hooks
- **State:** TanStack Query for server state
- **Naming:** PascalCase for components, camelCase for functions

```typescript
// Good
export const ResourceList: React.FC = () => {
  const { data, isLoading } = useQuery({...});
  // ...
};

// Bad
export function resourceList() {
  // ...
}
```

### Git Commit Messages

Follow conventional commits:

```
feat: Add EC2 instance management
fix: Resolve DynamoDB scan timeout
docs: Update contributing guide
perf: Cache S3 bucket metadata
refactor: Extract service factory
```

## Testing

### Manual Testing

Before submitting a PR:

1. **Start the console:** `docker-compose up -d`
2. **Test the service:**
   - List resources (should show empty or existing)
   - Create resource (if CRUD)
   - View resource detail
   - Delete resource (if CRUD)
3. **Check errors:** Open browser console, verify no errors
4. **Test auto-discovery:** Wait 5 minutes, verify resources appear
5. **Test MCP:** Query via MCP tool (if added)

### Automated Testing (Coming Soon)

We're adding:
- Unit tests (pytest for backend, jest for frontend)
- Integration tests
- E2E tests (Playwright)

## Pull Request Process

1. **Fork the repo**
2. **Create a branch:** `git checkout -b feature/ec2-support`
3. **Make changes**
4. **Test locally** (see above)
5. **Commit:** Use conventional commit format
6. **Push:** `git push origin feature/ec2-support`
7. **Open PR** with:
   - Clear description of changes
   - Screenshots (if UI changes)
   - Link to related issue
   - Test results

### PR Checklist

- [ ] Service backend implemented
- [ ] API routes added
- [ ] Sync function added
- [ ] Frontend component created
- [ ] Route registered in App.tsx
- [ ] Added to Home.tsx
- [ ] MCP tool added (optional)
- [ ] Tested manually (all CRUD operations work)
- [ ] No console errors
- [ ] Code follows style guide
- [ ] Commit messages follow convention

## Development Tips

### Debugging

**Backend logs:**
```bash
docker-compose logs -f api
```

**Frontend dev tools:**
```bash
# Open browser console
# React DevTools extension
# Network tab for API calls
```

**MiniStack logs:**
```bash
docker logs mari-ann-ministack -f
```

### Common Issues

**"Service not found" error:**
- Check service name in boto3 client
- Verify MiniStack supports this service
- Check `/resources/{service}` route exists

**"No resources displayed":**
- Check sync function runs (5-minute interval)
- Verify FalkorDB connection
- Check browser console for API errors

**"CORS errors":**
- Verify API_BASE_URL in `.env`
- Check FastAPI CORS middleware

## Release Process

Maintainers will:
1. Review PR
2. Test changes
3. Merge to main
4. Tag release (v1.1.0, v1.2.0, etc.)
5. Update changelog
6. Publish Docker image

## Questions?

- 💬 [GitHub Discussions](https://github.com/barroei1981/ministack_console/discussions) - Ask anything
- 🐛 [Open an Issue](https://github.com/barroei1981/ministack_console/issues/new) - Report bugs
- 📧 Email: [Your contact email]

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to learn and build something useful.

---

**Thank you for contributing!** Every PR, issue, and star helps make this project better. 🎉
