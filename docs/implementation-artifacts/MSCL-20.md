# Story MSCL-20: MCP Tools - Lambda and DynamoDB CRUD Operations

**Epic:** Epic 5 - AI Assistant Integration (MCP Server)  
**Story Points:** 5  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-17, MSCL-11, MSCL-14

## User Story

As an **AI assistant**,  
I want **to create, update, and delete Lambda functions and DynamoDB tables via MCP Tools**,  
So that **I can provision complete application stacks via natural language**.

## Acceptance Criteria

**Given** I invoke `create_lambda_function` tool with parameters: name, runtime, handler, code (base64), environment variables  
**When** the tool executes  
**Then** a new Lambda function is created in MiniStack  
**And** I receive the function ARN and details

**Given** I invoke `create_dynamodb_table` tool with parameters: name, partition_key, sort_key (optional), billing_mode  
**When** the tool executes  
**Then** a new DynamoDB table is created  
**And** I receive the table ARN and status

**Given** I invoke `delete_lambda_function` or `delete_dynamodb_table` tools  
**When** the tools execute  
**Then** the resources are deleted from MiniStack  
**And** I receive confirmation responses

**Architecture Decisions:** AD-9 (MCP Comprehensive Capabilities - Full CRUD from Phase 1)
