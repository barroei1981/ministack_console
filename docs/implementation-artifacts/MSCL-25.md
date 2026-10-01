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
