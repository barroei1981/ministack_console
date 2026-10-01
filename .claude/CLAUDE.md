# ministack_console

## Project Overview
**Control-plane** for MiniStack - a free, open-source AWS emulator (https://github.com/ministackorg/ministack).

**What MiniStack is:**
- Emulates 60+ AWS services on localhost:4566
- Alternative to LocalStack (which went paid)
- Drop-in compatible with boto3, AWS CLI, Terraform, CDK, Pulumi
- Supports multi-tenancy: 12-digit access key = separate account
- MIT licensed, free forever

**The Gap We're Filling:**
1. MiniStack has NO web UI or admin console (users must use CLI/SDK)
2. No resource-to-project-to-tenant tracking
3. AI assistants have NO visibility into local dev environment state

**What We're Building: Dual-Interface Control-Plane**

**Human Interface (Web UI):**
- **Full CRUD operations** for all 60+ MiniStack services (Query, Create, Read, Update, Delete)
- Complete service management equivalent to AWS Console capabilities
- Visual management of S3 buckets, SQS queues, Lambda functions, DynamoDB tables, etc.
- Service dashboards showing resource state
- Log inspection (CloudWatch Logs, SES emails, SNS messages)
- Configuration and policy management (IAM, security groups, etc.)
- Real-time monitoring of emulated services
- Project and tenant management

**Scope:** Every operation available via AWS CLI/SDK should be available via the UI - this is NOT a read-only dashboard.

**AI Assistant Interface (MCP Server):**
- Expose MiniStack state via Model Context Protocol
- Enable AI assistants (Claude, etc.) to query environment state
- Resource queries: "What S3 buckets exist in tenant-1?"
- Relationship queries: "Which projects use this SQS queue?"
- Context-aware development: AI knows what resources actually exist
- Single interaction point for AI-assisted development

**Key Innovation:**
Control-plane maintains resource graph showing tenant → project → resource relationships, making both human AND AI workflows environment-aware.

## Stack
[To be determined during architecture phase - likely:
- Frontend: React/Next.js or Vue.js
- Backend: Node.js or Python FastAPI
- Communication: REST API to MiniStack's Internal API (port 4566)]

## LCH Harness
This project uses the LCH Harness. Key paths:
- PRD: `docs/planning-artifacts/prd.md`
- Architecture: `docs/planning-artifacts/architecture.md`
- Story status: `docs/implementation-artifacts/sprint-status.yaml`
- Story files: `docs/implementation-artifacts/{story-key}.md`
- Memory: `.harness/memory.md`
- Decisions: `.harness/decisions/` (individual files — see `claude/shared/decisions-pattern.md`)

## Conventions
[Fill in: coding standards, naming, branch strategy - TBD after tech stack chosen]

## Infrastructure Constraints
- Target deployment: Runs alongside MiniStack (localhost or container)
- Must connect to MiniStack API at localhost:4566
- Should be lightweight (developers run this locally)
- No external dependencies on real AWS

## Integration Points
- MiniStack Internal API: http://localhost:4566
  - Health check: GET /_ministack/health
  - Reset state: POST /_ministack/reset
  - Runtime config: GET/POST /_ministack/config
  - SES emails: GET /_ministack/ses/emails
  - SQS messages: GET /_ministack/sqs/messages
  - SNS SMS: GET /_ministack/sns/sms
- AWS SDK endpoints: All standard AWS service endpoints via localhost:4566
