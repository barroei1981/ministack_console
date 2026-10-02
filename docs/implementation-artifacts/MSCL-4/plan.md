# Implementation Plan: MSCL-4 - Dual Tagging System

**Story:** MSCL-4  
**Branch:** story/MSCL-4-dual-tagging  
**Created:** 2026-10-02  
**Status:** in-progress

---

## Alignment

**Epic:** Epic 1 - Control-Plane Foundation  
**PRD requirement:** FR-4 (Project Tagging) - Section 203-212 of prd.md v1.5  
**Architecture constraint:** AD-3 (Dual Tagging System) - Lines 83-89 of architecture.md v1.5

**ADRs in scope:**
- AD-3: Dual Tagging System - Two parallel tagging systems (control-plane + native) serve different purposes
- AD-2: FalkorDB for Resource Inventory - Graph storage for control-plane tags via (:Resource)-[:TAGGED_WITH]->(:Tag) relationships
- AD-6: Multi-Tenant Isolation - Tags must respect tenant_id boundaries
- AD-11: Hybrid Schema Evolution - TAGGED_WITH relationship is part of stable core schema

**Reuse decision:** 
- Extending existing FalkorDB graph operations from MSCL-1 (control_plane/graph/query.py)
- No new abstractions needed for tag storage - using existing relationship patterns
- New modules: control_plane/tagging/control_plane.py and control_plane/tagging/native.py to encapsulate tag operations

**Cross-layer contract:**
- Control-plane tags: FalkorDB only via relationship `(:Resource)-[:TAGGED_WITH {key, value, namespace: 'control_plane'}]->(:Tag)`
- Native tags: Write-through to both FalkorDB (namespace: 'native') and MiniStack via boto3
- No API endpoints in this story (MSCL-6 will add REST API)
- Focus: Core tagging logic + FalkorDB operations + boto3 integration

**Confirmed consistent:** YES

**Rationale:**
- PRD FR-4 requires project tagging for logical resource grouping
- AD-3 mandates dual tagging: control-plane tags (all resources) + native tags (taggable services only)
- Control-plane tags stored in FalkorDB relationship (MSCL-1 schema already defines TAGGED_WITH)
- Native tags written to MiniStack via boto3 (MSCL-2 already has boto3 client infrastructure)
- This story implements the core tagging operations layer - API endpoints deferred to MSCL-6

**Integration points from Graphiti:**
- MSCL-1: FalkorDB schema defines TAGGED_WITH relationship, graph query abstraction layer
- MSCL-2: MiniStack boto3 client infrastructure (control_plane/ministack_client.py) for native tag write-through
- MSCL-3: Tenant isolation enforces tenant_id on all queries including tag queries

---

## Tasks

### Implementation
- [ ] Create control_plane/tagging/__init__.py module
- [ ] Implement control_plane/tagging/control_plane.py:
  - [ ] add_control_plane_tag(resource_id, key, value) - Create TAGGED_WITH relationship
  - [ ] remove_control_plane_tag(resource_id, key) - Delete TAGGED_WITH relationship
  - [ ] get_control_plane_tags(resource_id) - Query all control-plane tags for resource
  - [ ] query_resources_by_tag(key, value, tenant_id=None) - Find resources by tag
- [ ] Implement control_plane/tagging/native.py:
  - [ ] TAGGABLE_SERVICES constant (s3:bucket, lambda:function, dynamodb:table)
  - [ ] add_native_tag(resource_id, key, value) - Write-through to FalkorDB + MiniStack
  - [ ] remove_native_tag(resource_id, key) - Remove from FalkorDB + MiniStack
  - [ ] get_native_tags(resource_id) - Query native tags
  - [ ] sync_native_tags_from_ministack(resource_id) - Poll MiniStack for current native tags
- [ ] Implement tag propagation (CloudFormation stack → resources inherit control-plane tags)
- [ ] Add tag namespace validation (control_plane vs native)

### Testing
- [ ] Unit tests: tests/test_tagging_control_plane.py
  - [ ] Test add/remove/get control-plane tags
  - [ ] Test query_resources_by_tag with and without tenant_id filter
  - [ ] Test tag key/value validation
  - [ ] Test multiple tags on single resource
- [ ] Unit tests: tests/test_tagging_native.py
  - [ ] Test add/remove native tags for taggable services (S3, Lambda, DynamoDB)
  - [ ] Test non-taggable services (should only write to FalkorDB, log warning)
  - [ ] Test namespace isolation (control_plane vs native tags don't collide)
- [ ] Integration tests: tests/integration/test_tagging_e2e.py
  - [ ] Test native tag write-through: add tag → verify in both FalkorDB and MiniStack
  - [ ] Test query across multiple service types by project tag
  - [ ] Test tenant isolation for tag queries
  - [ ] Test tag propagation (future: CloudFormation stack tags)

### Documentation
- [ ] Add docstrings to all public functions
- [ ] Update control_plane/tagging/README.md with usage examples

---

## Acceptance Criteria Mapping

**AC1: Control-plane tags stored in FalkorDB**
- File: `control_plane/tagging/control_plane.py`
- Functions: `add_control_plane_tag()`, `get_control_plane_tags()`
- Relationship: `(:Resource)-[:TAGGED_WITH {key, value, namespace: 'control_plane'}]->(:Tag)`

**AC2: Native tags written to both FalkorDB and MiniStack**
- File: `control_plane/tagging/native.py`
- Functions: `add_native_tag()` calls FalkorDB + boto3 client
- Services: S3, Lambda, DynamoDB (TAGGABLE_SERVICES)

**AC3: Control-plane tags apply to all resources**
- Implementation: No service-type check in `add_control_plane_tag()`
- Verified by: Unit test with multiple service types

**AC4: Query resources by tag**
- Function: `query_resources_by_tag(key, value, tenant_id=None)`
- Uses FalkorDB index on Resource.tenant_id for performance
- Verified by: Integration test querying across S3, Lambda, DynamoDB

**AC5: Tag propagation (CloudFormation → resources)**
- Deferred to future story (requires CloudFormation stack tracking)
- Placeholder: Document in control_plane/tagging/propagation.py

**AC6: Non-taggable services handled gracefully**
- Logic: Check `if resource.type in TAGGABLE_SERVICES` before boto3 call
- Fallback: Store in FalkorDB only, log warning
- Verified by: Unit test attempting to tag non-taggable service

---

## Notes

**Phase 1 Scope (This Story):**
- Core tagging operations (add, remove, query)
- FalkorDB storage for both tag types
- boto3 write-through for native tags (Phase 1: S3, Lambda, DynamoDB)
- Namespace isolation (control_plane vs native)

**Deferred to Future Stories:**
- REST API endpoints for tagging (MSCL-6: REST API Foundation)
- Tag propagation for CloudFormation stacks (requires stack tracking)
- Tag validation rules (reserved keys, character limits)
- Bulk tagging operations
- Tag history/audit trail

**Testing Strategy:**
- Unit tests: 100% coverage for tagging logic
- Integration tests: Verify write-through to MiniStack
- E2E tests: Query by tag across multiple tenants and service types

**Performance Considerations:**
- Use FalkorDB index on Resource.tenant_id for fast tag queries
- Batch tag operations where possible (future optimization)
- Cache tag results for frequently accessed resources (future optimization)
