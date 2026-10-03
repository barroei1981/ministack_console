# MCP Server - AI Assistant Integration

**Status**: Foundation / MVP in progress  
**Epic**: Epic 5 - AI Assistant Integration  
**Story**: MSCL-17

## Overview

This module implements a Model Context Protocol (MCP) server that enables AI assistants (Claude, GPT, etc.) to query and manage MiniStack resources programmatically.

## Architecture

```
AI Assistant (Claude Desktop)
    ↓ MCP Protocol
MCP Server (port 3100)
    ↓ HTTP/REST
FastAPI REST API (port 8000)
    ↓
MiniStack + FalkorDB
```

**Key Principle**: MCP server is a **thin protocol adapter** with no business logic. All operations delegate to the existing REST API.

## Current Implementation Status

### ✅ Completed (MSCL-17 MVP)
- [x] Module structure created
- [x] Configuration system (environment variables)
- [x] Dependency added (mcp>=1.0.0 in pyproject.toml)
- [x] Architecture documented

### 🚧 In Progress / TODO
- [ ] MCP server core implementation (server.py)
- [ ] API key authentication (auth.py)
- [ ] Rate limiting (rate_limiter.py)
- [ ] Resource handlers for read operations
- [ ] API key management endpoints
- [ ] Integration tests with Claude Desktop

## Configuration

Environment variables:

```bash
MCP_SERVER_PORT=3100              # Server port
MCP_API_BASE_URL=http://localhost:8000  # REST API base URL
MCP_LOG_LEVEL=INFO                # Logging level
MCP_RATE_LIMIT_READS=1000         # Read operations per minute
MCP_RATE_LIMIT_WRITES=100         # Write operations per minute
MCP_REQUIRE_API_KEY=true          # Enforce authentication
MCP_DEV_MODE=false                # Disable auth for development
```

## Planned Capabilities

### Resources (Read Operations) - MSCL-18
```
ministack://tenants
ministack://tenant/{id}/resources
ministack://tenant/{id}/projects
ministack://project/{name}/resources
ministack://resources/{service_type}
ministack://resource/{id}/details
ministack://resource/{id}/dependencies
```

### Tools (Write Operations) - MSCL-19-21
```
create_s3_bucket
delete_s3_bucket
create_lambda_function
update_lambda_function
delete_lambda_function
create_dynamodb_table
delete_dynamodb_table
tag_resource
bulk_create_stack
```

### Prompts (Use Case Templates) - Future
```
list_environment_state
generate_terraform_for_project
explain_resource_dependencies
suggest_cleanup
```

## Authentication & Security

**API Key Management:**
- Keys stored in FalkorDB (hashed with SHA-256)
- Never store plaintext keys
- Each key has rate limits and metadata
- Keys can be revoked (soft delete)

**Rate Limiting:**
- Token bucket algorithm
- Per-API-key limits
- Separate buckets for reads vs. writes
- 429 response when limit exceeded

## Usage Example (Planned)

**Claude Desktop config** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "ministack-console": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "MCP_API_KEY": "your-api-key-here",
        "MCP_API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Natural language query in Claude:**
```
User: "What S3 buckets exist in my MiniStack environment?"
Claude: [Uses ministack://resources/s3 to query]
Claude: "You have 3 S3 buckets: dev-data, staging-assets, prod-backups"
```

## Development Roadmap

**Phase 1 (MSCL-17):** Foundation
- ✅ Module structure
- 🚧 MCP server core
- 🚧 Authentication
- 🚧 Rate limiting

**Phase 2 (MSCL-18):** Read Operations
- MCP Resources for all service types
- Resource detail queries
- Dependency graph queries

**Phase 3 (MSCL-19-21):** Write Operations
- MCP Tools for CRUD operations
- Bulk operations with transaction support
- Rollback and confirmation patterns

**Phase 4 (Future):** Advanced Features
- MCP Prompts for common use cases
- Audit logging UI
- Usage analytics
- Multi-user API key management UI

## References

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Claude Desktop MCP Integration](https://docs.anthropic.com/claude/docs/mcp)
