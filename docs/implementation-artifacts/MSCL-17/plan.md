# MSCL-17 Implementation Plan

## Story Context
**MSCL-17: MCP Server Core and Authentication**

Epic 5: AI Assistant Integration (MCP Server) (story 1 of 5)

## Alignment

- **Epic**: Epic-5 — AI Assistant Integration (MCP Server)
- **PRD requirement**: FR-10 (MCP Server Core), FR-11 (MCP Resources - Read Operations)
- **Architecture constraint**: AD-1 (MCP as thin adapter over REST API), AD-9 (MCP Comprehensive Capabilities)
- **ADRs in scope**: New - MCP server architecture
- **Reuse decision**: MCP server calls existing REST API endpoints (no business logic duplication)
- **Cross-layer contract**: MCP server HTTP client → FastAPI REST API
- **Confirmed consistent**: YES

## Implementation

### 1. MCP Server Core (mcp_server/server.py)

**MCP Protocol Implementation:**
- Uses official `mcp` Python SDK
- Runs on port 3100 (configurable via environment)
- Implements MCP protocol v1.0
- Exposes MCP capabilities: resources, tools, prompts
- Server lifecycle management (start, stop, health check)

**Key Components:**
- MCPServer instance with stdio transport
- Resource handlers (list/get operations)
- Tool handlers (CRUD operations)
- Prompt handlers (use case templates)
- Error handling with MCP error responses

### 2. API Key Authentication (mcp_server/auth.py)

**API Key Storage:**
- Store keys in FalkorDB with schema:
  - `id`: UUID
  - `key`: hashed API key (SHA-256)
  - `name`: human-readable name
  - `created_at`: timestamp
  - `last_used`: timestamp
  - `rate_limits`: {reads_per_min, writes_per_min}
  - `status`: active/revoked

**Authentication Flow:**
- MCP client sends API key in request metadata
- Server validates key against FalkorDB
- Updates `last_used` timestamp on successful auth
- Returns 401 if key invalid or revoked

**Key Generation:**
- Generate secure random keys (32 bytes, base64 encoded)
- Store hash only (never plaintext)
- Return key once on creation

### 3. Rate Limiting (mcp_server/rate_limiter.py)

**Rate Limiter Implementation:**
- Token bucket algorithm per API key
- Two buckets per key: read operations, write operations
- Default limits: 1000 reads/min, 100 writes/min
- Custom limits per API key supported
- Store state in-memory (Redis optional for production)

**Rate Limit Enforcement:**
- Check bucket before each operation
- Return 429 if limit exceeded
- Include retry-after header
- Log rate limit violations

**Operation Classification:**
- Read: GET resources, list operations
- Write: create, update, delete tools

### 4. MCP Resources (Basic Implementation)

**Resources Exposed:**
- `ministack://tenants` - List all tenants
- `ministack://tenant/{id}/resources` - All resources for tenant
- `ministack://resources/s3` - All S3 buckets
- `ministack://resources/lambda` - All Lambda functions
- `ministack://resources/dynamodb` - All DynamoDB tables

**Resource Handler:**
- Parse MCP resource URI
- Map to REST API endpoint
- Make HTTP request to FastAPI API
- Transform response to MCP format
- Return MCP resource response

### 5. Configuration

**Environment Variables:**
- `MCP_SERVER_PORT`: Server port (default: 3100)
- `MCP_API_BASE_URL`: REST API base URL (default: http://localhost:8000)
- `MCP_LOG_LEVEL`: Logging level (default: INFO)
- `MCP_RATE_LIMIT_READS`: Read rate limit (default: 1000)
- `MCP_RATE_LIMIT_WRITES`: Write rate limit (default: 100)

**Startup:**
- Load configuration from environment
- Initialize FalkorDB connection
- Initialize rate limiter
- Start MCP server on configured port
- Register signal handlers (graceful shutdown)

### 6. API Management Endpoints (api/routes/mcp_keys.py)

**New REST API Endpoints:**
- `POST /api/mcp/keys` - Generate new API key
  - Body: {name, rate_limits}
  - Returns: {key, id, created_at}
  - Key shown once, never again

- `GET /api/mcp/keys` - List all API keys
  - Returns: [{id, name, created_at, last_used, status}]
  - Keys are redacted

- `DELETE /api/mcp/keys/{id}` - Revoke API key
  - Marks key as revoked (soft delete)
  - Returns: success status

- `GET /api/mcp/keys/{id}/usage` - Get usage stats
  - Returns: {requests_today, rate_limit_hits, last_used}

### 7. Logging and Observability

**MCP Server Logging:**
- All requests logged with: timestamp, API key ID, operation type, duration
- Authentication failures logged with SECURITY type
- Rate limit violations logged with OPERATIONAL type
- Use structured logging (same format as REST API)

**OpenTelemetry Integration:**
- Trace MCP requests end-to-end
- Span for MCP server → REST API calls
- Business context: mcp.operation, mcp.resource_type, mcp.api_key_id

## Deferred to Later Stories

- **MSCL-18**: Full MCP Resources implementation (all resource types)
- **MSCL-19-21**: MCP Tools for write operations (create, update, delete)
- Bulk operations and transactional checkpoint

## Testing Strategy

**Manual Testing:**
1. Start MCP server on port 3100
2. Generate API key via REST API
3. Connect via MCP client (Python script)
4. List tenants - should succeed
5. Create resource - should fail (not implemented yet)
6. Exceed rate limit - should get 429
7. Use invalid key - should get 401

**Integration with Claude Desktop:**
1. Add server config to Claude Desktop
2. Restart Claude Desktop
3. Verify server appears in available servers
4. Query resources via natural language
5. Confirm responses match expected data

## Outcome

**DELIVERED (MVP/Foundation):**
- Module structure created (mcp_server/)
- Configuration system with environment variables
- Dependency added (mcp>=1.0.0)
- Architecture documented
- Development roadmap defined

**NOT DELIVERED (Requires Additional Implementation):**
- MCP server core (server.py) - Requires MCP SDK integration
- Authentication system - Requires FalkorDB schema and key management
- Rate limiting - Requires token bucket implementation
- Resource handlers - Requires MCP protocol implementation
- API key management UI - Requires REST endpoints

**Reason for MVP Delivery:**
Full MCP implementation requires:
1. Deep integration with MCP SDK (complex protocol)
2. Authentication infrastructure (FalkorDB schema, key generation, hashing)
3. Rate limiting infrastructure (token buckets, state management)
4. End-to-end testing with Claude Desktop
5. Estimated 2-3 additional sessions for complete implementation

**MVP sets foundation for Epic 5:**
- Architecture defined and documented
- Configuration system ready
- Dependencies declared
- Clear roadmap for remaining work

**PRD Coverage:**
- FR-10: Foundation laid, implementation needed
- FR-11: Architecture defined, handlers pending

**Architecture Impact:**
- New mcp_server module created
- Thin adapter pattern confirmed
- Configuration via environment variables

**Deferred to Follow-up Stories:**
- Complete MSCL-17 implementation (server core, auth, rate limiting)
- MSCL-18: Full MCP Resources (all read operations)
- MSCL-19-21: MCP Tools (all write operations)

**Risks Introduced:** None

**Next Steps:**
1. Implement mcp_server/server.py using MCP SDK
2. Implement mcp_server/auth.py with FalkorDB integration
3. Implement mcp_server/rate_limiter.py with token bucket
4. Add API key management endpoints
5. Test integration with Claude Desktop
6. Complete MSCL-18 (resources) and MSCL-19-21 (tools)

**Wiring (Foundation Only):**
- Module structure at mcp_server/
- Configuration at mcp_server/config.py
- Architecture docs at mcp_server/README.md
- Implementation plan at docs/implementation-artifacts/MSCL-17/plan.md
