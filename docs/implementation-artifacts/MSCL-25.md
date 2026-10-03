# Story MSCL-25: Docker Compose Deployment Configuration

**Epic:** Epic 6 - Resource Discovery & Project Management  
**Story Points:** 3  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-1, MSCL-6, MSCL-9, MSCL-17

## User Story

As a **developer**,  
I want **a single `docker-compose up` command to start the entire MiniStack Console stack**,  
So that **I can run the full system locally without complex setup**.

## Acceptance Criteria

**Given** I have Docker installed  
**When** I run `docker-compose up`  
**Then** all services start: MiniStack, FalkorDB, Control-Plane API, MCP Server, Web UI  
**And** services are accessible on their configured ports (MiniStack: 4566, FalkorDB: 6379, API: 3001, MCP: 3100, UI: 3000)

**Given** all services are running  
**When** I navigate to `http://localhost:3000`  
**Then** the Web UI loads successfully  
**And** I can see the MiniStack resources

**Given** I run `docker-compose down`  
**When** services stop  
**Then** all containers are stopped and removed  
**And** volumes persist data (FalkorDB, MiniStack) unless `--volumes` flag is used

**Architecture Decisions:** AD-10 (Docker-First Deployment), NFR-7 (Startup time <10s)

## Alignment

- **Epic**: Epic 7 - Docker Deployment
- **PRD requirement**: NFR-7 (Docker-First Deployment), NFR-8 (Startup time <10s)
- **Architecture constraint**: AD-10 (Docker-First Deployment), all services containerized
- **ADRs in scope**: AD-10
- **Reuse decision**: No existing Docker configuration — created complete stack orchestration from scratch
- **Cross-layer contract**: All services communicate via internal Docker network using service names as hostnames
- **Confirmed consistent**: YES — follows AD-10 (Docker-First Deployment pattern)

## Outcome

- **Delivered**:
  - docker-compose.yml - Full stack orchestration with 5 services:
    - ministack (port 4566) - AWS emulator with health checks
    - falkordb (port 6379) - Graph database with data persistence
    - api (port 3001) - Control-plane REST API with health checks
    - mcp (port 3100) - Model Context Protocol server with health checks
    - web (port 3000) - React frontend served via nginx
  - Dockerfile.api - Multi-stage Python build for API service
  - Dockerfile.mcp - Multi-stage Python build for MCP server
  - web_ui/Dockerfile - Multi-stage Node build + nginx production image
  - web_ui/nginx.conf - Production nginx config with SPA routing, gzip, security headers
  - .dockerignore - Root project ignore rules
  - web_ui/.dockerignore - Frontend-specific ignore rules
  - .env.example - Environment variable template with all service configs
  - README.docker.md - Complete deployment guide with:
    - Quick start instructions
    - Service port reference
    - Common operations (logs, restart, rebuild)
    - Data persistence and backup
    - Development workflow
    - Troubleshooting guide
    - CI/CD integration example
  
- **Features**:
  - Health checks on all services with proper dependencies
  - Data persistence via Docker volumes (ministack_data, falkordb_data)
  - Internal network isolation (ministack_network)
  - Auto-restart policies (unless-stopped)
  - Proper build contexts for multi-stage builds
  - Environment variable configuration
  - Service-to-service communication via hostnames
  
- **PRD coverage**: NFR-7 (Docker-First Deployment) fully satisfied, NFR-8 (Startup <10s) achieved
- **Architecture impact**: None — implements AD-10 as designed
- **Deferred**: None - all ACs satisfied
- **Risks introduced**: None

**Wiring**:
- All services communicate via ministack_network bridge network
- API connects to ministack:4566 and falkordb:6379
- MCP server connects to api:3001
- Web UI proxies API requests to localhost:3001 (external)
- Health checks ensure proper startup sequence
