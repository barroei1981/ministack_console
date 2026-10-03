# Implementation Plan: MSCL-5 - Resource Dependency Detection

**Story:** MSCL-5  
**Branch:** story/MSCL-5-dependency-detection  
**Created:** 2026-10-02  
**Status:** in-progress

---

## Alignment

**Epic:** Epic 1 - Control-Plane Foundation  
**PRD requirement:** FR-2 (Resource Graph) - Lines 27-35 of prd.md v1.5  
**Architecture constraint:** AD-2 (FalkorDB for Resource Graph) - Graph stored in FalkorDB with DEPENDS_ON relationships

**ADRs in scope:**
- AD-2: FalkorDB for Resource Inventory - Graph operations via control_plane/graph/query.py
- AD-8: Resource Polling Strategy - Dependency detection runs after resource sync (every 30s)
- AD-11: Hybrid Schema Evolution - DEPENDS_ON relationship is part of stable core schema (MSCL-1)

**Reuse decision:**
- Extending MSCL-1 graph operations (control_plane/graph/query.py) - create_relationship for DEPENDS_ON
- Extending MSCL-2 MiniStackClient (control_plane/ministack_client.py) - add methods for list_event_source_mappings, get_bucket_policy
- No new graph schema changes - DEPENDS_ON relationship already defined in MSCL-1 schema
- New module: control_plane/dependencies/ for detection logic

**Cross-layer contract:**
- Dependency detection triggered after resource sync (control_plane/inventory/sync.py integration point)
- Graph queries via existing query_nodes() and Cypher query execution
- No API endpoints in this story (MSCL-6 will add REST API for graph queries)

**Confirmed consistent:** YES

**Rationale:**
- PRD FR-2 requires dependency detection: Lambda→S3, Lambda→SQS, S3→IAM, CloudFormation→resources
- AD-2 mandates FalkorDB for graph storage with DEPENDS_ON relationships (already in MSCL-1 schema)
- Detection runs as part of polling cycle (AD-8) after resource sync
- This story implements detection logic + graph relationship management

**Integration points from Graphiti:**
- MSCL-1: FalkorDB schema defines DEPENDS_ON relationship, graph query abstraction
- MSCL-2: MiniStackClient for AWS API calls (event source mappings, bucket policies)
- MSCL-3: Tenant isolation enforced on dependency queries (tenant_id filtering)
- MSCL-4: No direct integration (tags are orthogonal to dependencies)

---

## Tasks

### Implementation
- [ ] Create control_plane/dependencies/__init__.py module
- [ ] Implement control_plane/dependencies/detectors.py:
  - [ ] detect_lambda_s3_dependencies() - Parse Lambda env vars + IAM policy for S3 ARNs
  - [ ] detect_lambda_event_sources() - Query event source mappings for SQS/SNS/DynamoDB
  - [ ] detect_s3_iam_dependencies() - Parse S3 bucket policy for IAM role ARNs
  - [ ] detect_cloudformation_resources() - Query stack resources via DescribeStackResources
- [ ] Implement control_plane/dependencies/manager.py:
  - [ ] sync_dependencies(resource_id) - Run detection, create/update/delete DEPENDS_ON relationships
  - [ ] get_dependencies(resource_id, direction="outbound") - Query what resource depends on (outbound) or what depends on it (inbound)
  - [ ] get_transitive_dependencies(resource_id, max_depth=3) - Recursive traversal
- [ ] Extend control_plane/ministack_client.py:
  - [ ] list_event_source_mappings(function_name) - Lambda event sources
  - [ ] get_bucket_policy(bucket_name) - S3 bucket policy
  - [ ] describe_stack_resources(stack_name) - CloudFormation resources
- [ ] Integrate with polling: Update control_plane/inventory/poller.py to call sync_dependencies after sync_changes

### Testing
- [ ] Unit tests: tests/test_dependencies_detectors.py
  - [ ] Test Lambda→S3 detection (env vars with S3 ARNs)
  - [ ] Test Lambda→SQS detection (event source mappings)
  - [ ] Test S3→IAM detection (bucket policy parsing)
  - [ ] Test ARN parsing edge cases (malformed, missing components)
- [ ] Unit tests: tests/test_dependencies_manager.py
  - [ ] Test sync_dependencies: creates new relationships
  - [ ] Test sync_dependencies: removes stale relationships
  - [ ] Test get_dependencies: inbound vs outbound
  - [ ] Test get_transitive_dependencies: depth limiting
- [ ] Integration tests: tests/integration/test_dependencies_e2e.py
  - [ ] Create Lambda + S3 + env var → verify DEPENDS_ON created
  - [ ] Create Lambda + SQS + event source → verify DEPENDS_ON created
  - [ ] Remove env var → verify DEPENDS_ON deleted

### Documentation
- [ ] Add docstrings to all detection functions
- [ ] Document ARN parsing patterns in control_plane/dependencies/README.md

---

## Acceptance Criteria Mapping

**AC1: Lambda→S3 via environment variables**
- Function: `detect_lambda_s3_dependencies()` parses Environment.Variables for S3 ARNs
- Relationship: `(:Lambda)-[:DEPENDS_ON {type: "environment_variable"}]->(:S3)`
- Verified by: Integration test creates Lambda with S3 env var

**AC2: Lambda→SQS via event source mappings**
- Function: `detect_lambda_event_sources()` calls list_event_source_mappings
- Relationship: `(:Lambda)-[:DEPENDS_ON {type: "event_source_mapping"}]->(:SQS)`
- Metadata: mapping_uuid stored in relationship

**AC3: S3→IAM via bucket policy**
- Function: `detect_s3_iam_dependencies()` parses bucket policy Principal.AWS
- Relationship: `(:S3)-[:DEPENDS_ON {type: "bucket_policy"}]->(:IAM)`

**AC4: CloudFormation→resources**
- Function: `detect_cloudformation_resources()` calls describe_stack_resources
- Relationship: `(:CloudFormation)-[:DEPENDS_ON {type: "stack_resource"}]->(:Resource)`

**AC5: Stale dependency removal**
- Logic: `sync_dependencies()` compares detected vs existing, deletes removed
- Event: Emits DEPENDENCY_REMOVED (future - requires MSCL-7 SSE)

**AC6: Query dependents**
- Function: `get_dependencies(resource_id, direction="inbound")` queries incoming DEPENDS_ON
- Returns: List of resources with dependency type

---

## Notes

**Phase 1 Scope (This Story):**
- Detect Lambda→S3, Lambda→SQS/SNS, S3→IAM, CloudFormation→resources
- Create/update/delete DEPENDS_ON relationships in FalkorDB
- Query dependencies (inbound/outbound/transitive)
- Integration with polling cycle

**Deferred to Future Stories:**
- DEPENDENCY_REMOVED event emission (requires MSCL-7 SSE)
- Dependency visualization UI (requires web UI stories)
- "Delete with dependents" warning (requires REST API + UI)
- DynamoDB Stream dependencies, API Gateway→Lambda dependencies

**Testing Strategy:**
- Unit tests: 100% coverage for detection logic, ARN parsing
- Integration tests: Verify DEPENDS_ON created/deleted correctly
- Mock boto3 responses (no real MiniStack required for unit tests)

**Performance Considerations:**
- Detection runs per-resource after sync (not all resources at once)
- Use FalkorDB index on resource IDs for fast lookup
- Cache parsed ARNs to avoid re-parsing unchanged resources (future optimization)
