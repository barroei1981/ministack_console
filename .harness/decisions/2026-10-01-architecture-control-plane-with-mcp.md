# Architecture Decision: Control-Plane with MCP Interface

**Date:** 2026-10-01  
**Status:** Proposed  
**Deciders:** roeibar  
**Type:** Architecture

## Context

MiniStack is a local AWS emulator with 60+ services but no management UI or programmatic visibility layer. Initial concept was a simple admin console (web UI only).

**Key insight:** Developers increasingly use AI assistants (Claude, etc.) for development. These assistants are blind to local dev environment state - they can't query "what S3 buckets exist?" or "which resources does project A use?"

**Multi-tenancy context:** MiniStack supports multiple isolated accounts (12-digit access key = tenant). Need to track resources across tenants and projects.

## Decision

Build as a **Control-Plane with Dual Interfaces**, not just an admin UI:

### 1. Control-Plane Core
- Central resource inventory system
- Track relationships: tenant → project → resources
- Maintain resource graph (which Lambda uses which SQS queue, etc.)
- Single source of truth for all MiniStack resource state

### 2. Human Interface (Web UI)
- Visual admin console (AWS Console-like experience)
- **Full service management** - complete CRUD operations for all 60+ services
- Query, create, read, update, delete resources across all service types
- Service dashboards, resource management, log inspection
- Project and tenant management views
- Real-time monitoring

### 3. AI Assistant Interface (MCP Server)
- Expose control-plane state via Model Context Protocol
- Enable AI assistants to query environment state
- Resource queries: "List S3 buckets in tenant-1"
- Relationship queries: "Which projects use queue xyz?"
- Context injection: AI knows actual environment, generates code that fits

## Scope: Full Service Management

**IMPORTANT:** The control-plane must provide **complete management capabilities** for all 60+ MiniStack services, based on available AWS APIs:

- **Query:** List resources, describe configuration, inspect state
- **Create:** Provision new resources (buckets, queues, functions, tables, etc.)
- **Read:** View resource details, configuration, metadata, logs
- **Update/Alter:** Modify resource configuration, update policies, change settings
- **Delete:** Remove resources, clean up state
- **Manage:** Full CRUD operations on all supported service types

**NOT just a read-only dashboard** - this is a full-capability management console equivalent to AWS Console, but for the local emulated environment. Every operation available via AWS CLI/SDK should be available via the UI.

## Consequences

### Positive
- ✅ **Environment-aware AI development** - AI assistants know what exists, reduce "does X exist?" questions
- ✅ **Single source of truth** - Both humans and AI query same control-plane
- ✅ **Resource graph visibility** - Understand dependencies (this Lambda uses that bucket)
- ✅ **Multi-tenant support** - Track resources per tenant/project
- ✅ **Future-proof** - MCP is industry standard for AI-tool integration
- ✅ **Developer productivity** - Visual UI for exploration, MCP for automation/AI

### Negative
- ⚠️ **Increased scope** - More complex than simple UI
- ⚠️ **Resource graph maintenance** - Must track relationships accurately
- ⚠️ **MCP server development** - Additional component to build/maintain

### Neutral
- Architecture must support both synchronous (UI) and asynchronous (MCP) access patterns
- Need caching layer to avoid hitting MiniStack API repeatedly
- Resource graph likely needs its own storage (not just MiniStack state)

## Alternatives Considered

### 1. Simple Admin UI Only
**Rejected:** Misses opportunity to make AI-assisted development environment-aware. Developers would still context-switch between UI (to see state) and AI (to write code).

### 2. MCP Server Only (No UI)
**Rejected:** Not all developers use AI assistants. Many want visual exploration of resources.

### 3. GraphQL API Instead of MCP
**Rejected:** MCP is specifically designed for AI assistant integration. GraphQL better for human-facing APIs but doesn't integrate with Claude/other AI tools.

## Implementation Notes

**Architecture layers:**
```
┌─────────────────────┐
│   Web UI (React)    │
├─────────────────────┤
│  MCP Server (MCP)   │
├─────────────────────┤
│  Control-Plane Core │ ← Resource graph, inventory, relationships
├─────────────────────┤
│   MiniStack API     │ ← localhost:4566
└─────────────────────┘
```

**MCP Resources to expose:**
- `ministack://tenants` - List all tenants/accounts
- `ministack://tenant/{id}/projects` - Projects in a tenant
- `ministack://project/{id}/resources` - Resources in a project
- `ministack://resources/s3/buckets` - All S3 buckets
- `ministack://resources/{type}` - Resources by service type
- `ministack://resource/{id}/relationships` - What depends on this resource

**Control-plane must:**
1. Poll/subscribe to MiniStack state changes
2. Build and maintain resource graph
3. Support tagging resources with project/metadata
4. Provide both REST (for UI) and MCP (for AI) interfaces

## References
- MiniStack: https://github.com/ministackorg/ministack
- Model Context Protocol (MCP): https://spec.modelcontextprotocol.io/
- MiniStack Internal API: http://localhost:4566/_ministack/*

## Next Steps
1. PRD should define both UI and MCP use cases
2. Architecture doc must detail control-plane core design
3. Resource graph schema design (ADR needed)
4. MCP server resource/tool definitions
