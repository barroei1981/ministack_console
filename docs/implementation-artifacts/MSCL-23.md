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
