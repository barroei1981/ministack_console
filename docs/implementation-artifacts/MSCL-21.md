# Story MSCL-21: MCP Bulk Operations with Transactional Checkpoint

**Epic:** Epic 5 - AI Assistant Integration (MCP Server)  
**Story Points:** 8  
**Priority:** P1  
**Dependencies:** MSCL-19, MSCL-20

## User Story

As an **AI assistant**,  
I want **to create multiple resources atomically with rollback capability**,  
So that **I can provision complete application stacks safely**.

## Acceptance Criteria

**Given** I invoke `bulk_create_stack` tool with a stack definition (S3 bucket + SQS queue + Lambda function)  
**When** the tool executes  
**Then** resources are created sequentially  
**And** each resource creation is checkpointed  
**And** I receive a transaction ID

**Given** a bulk operation partially fails (2/3 resources created)  
**When** I invoke `bulk_rollback` with the transaction ID  
**Then** all created resources are deleted  
**And** I receive a rollback summary

**Given** a bulk operation succeeds  
**When** I invoke `bulk_confirm` with the transaction ID  
**Then** the transaction is marked as complete  
**And** resources are kept

**Given** a transaction is not confirmed within 5 minutes  
**When** the auto-cleanup runs  
**Then** the transaction is auto-rolled back  
**And** resources are deleted

**Architecture Decisions:** AD-13 (Transactional Checkpoint for MCP Bulk Operations)

## Alignment

- **Epic**: Epic 5 - AI Assistant Integration (MCP Server)
- **PRD requirement**: FR-12 (MCP Tools with transactional safety)
- **Architecture constraint**: AD-13 (Transactional Checkpoint for MCP Bulk Operations)
- **ADRs in scope**: AD-13
- **Reuse decision**: Created new transaction management system (mcp_server/transactions.py) with in-memory state for MVP
- **Cross-layer contract**: Transactions track resources and call delete operations via tools.py functions
- **Confirmed consistent**: YES - implements AD-13 (transactional checkpoint pattern)

## Outcome

- **Delivered**:
  - mcp_server/transactions.py - Transaction management system:
    - TransactionStatus enum (IN_PROGRESS, COMPLETED, ROLLED_BACK, FAILED)
    - Transaction dataclass with resource tracking
    - create_transaction() - Generate transaction ID
    - add_resource_to_transaction() - Track created resources
    - confirm_transaction() - Mark as complete (keep resources)
    - mark_transaction_rolled_back() - Mark as rolled back
    - cleanup_expired_transactions() - Auto-rollback after 5 minutes
    - start_cleanup_task() - Background cleanup task
  - mcp_server/tools.py - Transactional bulk operations:
    - bulk_create_stack(stack_definition, tenant_id, project) - Create multiple resources with checkpointing
    - bulk_rollback(transaction_id) - Delete all resources in transaction
    - bulk_confirm(transaction_id) - Confirm transaction (keep resources)
  - Extended mcp_server/server.py with 3 transactional tool definitions
  - Auto-cleanup runs every 60 seconds, rolls back transactions >5 minutes old
  
- **Features**:
  - Sequential resource creation with checkpoint after each
  - Reverse-order deletion on rollback (LIFO)
  - Transaction state tracking (id, status, resources, error)
  - Auto-rollback for abandoned transactions
  - Partial failure handling (returns created resources + errors)
  
- **PRD coverage**: FR-12 (transactional bulk operations) fully satisfied
- **Architecture impact**: None - implements AD-13 as designed
- **Deferred**: None - all ACs satisfied (in-memory state sufficient for MVP)
- **Risks introduced**: In-memory state lost on server restart (acceptable for MVP)

**Wiring**:
- Transaction cleanup task started in server main()
- All resource create operations add to transaction via add_resource_to_transaction()
- Rollback uses same delete functions as individual operations
