# Project Memory
**Last updated:** 2026-10-01
**Phase:** new

## Current State
Project just initialized. Run `/lch-solutions-plan` to start planning.

## Context for Next Session
- Project: ministack_console
- Stack: [fill in after architecture is created]
- Phase: new — no PRD yet

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
