# Project Memory
**Last updated:** 2026-10-02
**Phase:** in-development

## Current State
MSCL-3 (Multi-Tenant Isolation) complete and in review. PR #3 created.
Next: MSCL-4 (Control-Plane Tagging) after PR #3 approval

## Context for Next Session
- Project: ministack_console
- Stack: Python 3.11+, FastAPI (planned), FalkorDB, Docker Compose
- Phase: Epic 1 (Control-Plane Foundation) - stories 1-3/7 complete
- Branch: story/MSCL-3-multi-tenant → awaiting PR approval
- PR: https://github.com/barroei1981/ministack_console/pull/3
- Completed: MSCL-1 (FalkorDB Setup - PR #1 merged), MSCL-2 (MiniStack Polling - PR #2 merged), MSCL-3 (Multi-Tenant Isolation - PR #3 in review)

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
