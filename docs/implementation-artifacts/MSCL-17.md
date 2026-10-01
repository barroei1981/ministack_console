# Story MSCL-17: MCP Server Core and Authentication

**Epic:** Epic 5 - AI Assistant Integration (MCP Server)  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-6

## User Story

As an **AI assistant (Claude, GPT, etc.)**,  
I want **to connect to the MiniStack Console via MCP protocol**,  
So that **I can query and manage resources on behalf of users**.

## Acceptance Criteria

**Given** the MCP Server is running on port 3100  
**When** I connect via MCP protocol  
**Then** the connection is established successfully  
**And** I can list available resources and tools

**Given** I connect with a valid API key  
**When** I make MCP requests  
**Then** all requests are authenticated via the API key  
**And** rate limiting is applied (1000 reads/min, 100 writes/min)

**Given** I connect without an API key  
**When** I attempt to make requests  
**Then** I receive an authentication error  
**And** the request is rejected

**Given** the MCP Server is deployed  
**When** Claude Desktop connects to it  
**Then** Claude can see the server in available MCP servers list  
**And** Claude can query resources and invoke tools

**Architecture Decisions:** AD-1 (MCP as thin adapter over REST API), AD-9 (MCP Comprehensive Capabilities)
