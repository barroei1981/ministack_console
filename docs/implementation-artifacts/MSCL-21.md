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
