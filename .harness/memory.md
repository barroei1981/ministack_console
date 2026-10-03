# Project Memory
**Last updated:** 2026-10-03
**Phase:** in-development

## Current State
MSCL-8 (S3 Backend CRUD Operations) complete and in review. PR #8 created.
Epic 1 (Control-Plane Foundation) - all 7 stories complete.
Epic 2 (S3 Service Management) - 1 of 3 stories complete.

## Context for Next Session
- Project: ministack_console
- Stack: Python 3.11+, FastAPI, FalkorDB, Docker Compose, SSE, boto3
- Phase: Epic 2 (S3 Service Management) - story 1 of 3 complete
- Branch: story/MSCL-8-s3-backend-crud → awaiting PR approval
- PR: https://github.com/barroei1981/ministack_console/pull/8
- Completed: 
  - MSCL-1 (FalkorDB Setup - PR #1 merged)
  - MSCL-2 (MiniStack Polling - PR #2 merged)
  - MSCL-3 (Multi-Tenant Isolation - PR #3 merged)
  - MSCL-4 (Dual Tagging System - PR #4 merged)
  - MSCL-5 (Dependency Detection - PR #5 merged)
  - MSCL-6 (FastAPI REST API Foundation - PR #6 merged)
  - MSCL-7 (Server-Sent Events System - PR #7 merged)
  - MSCL-8 (S3 Backend CRUD Operations - PR #8 in review)

## What This Project Is
Control-plane for ministack (https://github.com/ministackorg/ministack) - a free, open-source AWS emulator.

**Problem being solved:**
- MiniStack currently has NO web UI or admin console
- Users must use AWS CLI, boto3, Terraform for all operations
- Developers want visual tools like AWS Console for local dev
- AI assistants (Claude, etc.) have NO visibility into local dev environment state
- No tracking of resource-to-project relationships or multi-tenant resource inventory

**Vision: Control-Plane Architecture**
Dual-interface management layer:

**1. Web UI (Human Interface):**
- Visual management of emulated AWS services (S3, SQS, Lambda, DynamoDB, etc.)
- Service dashboards showing resource state
- Log inspection (CloudWatch Logs, SES emails, SNS messages)
- Resource creation/deletion without CLI
- True AWS Console experience for local development

**2. MCP Server (AI Assistant Interface):**
- Expose MiniStack state via Model Context Protocol
- AI assistants can query: "What resources exist in tenant-1?"
- Context-aware: "Project A uses these S3 buckets and Lambda functions"
- Resource relationships: "Which projects use this SQS queue?"
- Single interaction point for AI-assisted development
- AI generates code that fits actual environment, not assumptions

**Key Differentiator:**
Control-plane tracks resource-to-project-to-tenant relationships, making both human AND AI workflows environment-aware.
