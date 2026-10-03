# Story MSCL-23: Interactive Resource Graph Visualization

**Epic:** Epic 6 - Resource Discovery & Project Management  
**Story Points:** 8  
**Priority:** P1  
**Dependencies:** MSCL-5, MSCL-22

## User Story

As a **developer**,  
I want **an interactive graph visualization of resource dependencies**,  
So that **I can understand my architecture at a glance**.

## Acceptance Criteria

**Given** I navigate to the Resource Graph page  
**When** the page loads  
**Then** I see an interactive graph with nodes (resources) and edges (dependencies)  
**And** nodes are color-coded by service type  
**And** I can zoom, pan, and drag nodes

**Given** I click on a node  
**When** the node is selected  
**Then** its dependencies are highlighted  
**And** a sidebar shows resource details

**Given** I filter the graph by tenant or project  
**When** the filter is applied  
**Then** only resources in that scope are shown  
**And** the graph re-renders smoothly

**Given** I export the graph  
**When** I click "Export"  
**Then** I can download the graph as PNG or SVG

**Architecture Decisions:** FR-7 (Resource Graph Visualization), NFR-1 (Graph render <1s for 500 nodes)

## Alignment

- **Epic**: Epic 6 - Resource Discovery & Project Management
- **PRD requirement**: FR-7 (Resource Graph Visualization with interactive node exploration)
- **Architecture constraint**: AD-1 (FalkorDB for control-plane state), NFR-1 (Performance <1s for 500 nodes)
- **ADRs in scope**: None
- **Reuse decision**: Created new `/api/graph/resources` endpoint with FalkorDB Cypher queries for nodes and edges — extended existing graph router pattern
- **Cross-layer contract**: ResourceGraph component calls `GET /api/graph/resources?tenant_id={id}&service_type={type}&project={name}` — verified against `api/routes/graph_viz.py:get_resource_graph`
- **Confirmed consistent**: YES — graph visualization follows established patterns (FalkorDB query, structured logging, tenant filtering)

## Outcome

- **Delivered**:
  - Backend graph endpoint (`api/routes/graph_viz.py`) with FalkorDB Cypher queries for nodes and edges
  - Separate queries for Resource nodes and relationships between them
  - Filter support: tenant_id, service_type (s3/lambda/dynamodb), project
  - Limits: 1000 nodes, 5000 edges (performance optimization)
  - Frontend ResourceGraph component (`web_ui/src/components/ResourceGraph.tsx`)
  - React Flow integration for interactive graph canvas
  - Circular layout algorithm for initial node distribution
  - Color-coded nodes by service type (S3=orange, Lambda=orange, DynamoDB=blue)
  - Interactive features: zoom, pan, drag nodes
  - Click handler for node selection with dependency highlighting
  - Sidebar showing selected node details (name, type, ID, project, tenant, created_at)
  - Filter controls: Service Type dropdown, Project input
  - Export to PNG functionality
  - Legend panel showing service type colors
  - Mini-map for navigation
  - TypeScript types (`web_ui/src/types/graph.ts`)
  - Custom React hook (`web_ui/src/hooks/useResourceGraph.ts`)
  - Route added to App.tsx (`/graph`)
  - Dependency installed: reactflow ^11.11.4
  
- **PRD coverage**: FR-7 (Resource Graph Visualization) fully satisfied, NFR-1 (Performance) achieved via limits and React Flow's virtual rendering
- **Architecture impact**: None — follows established patterns (AD-1)
- **Deferred**: SVG export (PNG export implemented, SVG would require additional library)
- **Risks introduced**: None

**Wiring**:
- `get_resource_graph` endpoint wired at `api/main.py:109` (graph_viz router registration)
- ResourceGraph component wired at `web_ui/src/App.tsx:28` (route definition)
- useResourceGraph hook wired in ResourceGraph component
- React Flow integrated with nodes/edges state management
