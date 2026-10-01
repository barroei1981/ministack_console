# ministack_console

## Project Overview
Admin console for MiniStack - a free, open-source AWS emulator (https://github.com/ministackorg/ministack).

**What MiniStack is:**
- Emulates 60+ AWS services on localhost:4566
- Alternative to LocalStack (which went paid)
- Drop-in compatible with boto3, AWS CLI, Terraform, CDK, Pulumi
- MIT licensed, free forever

**The Gap We're Filling:**
MiniStack has NO web UI or admin console. Users must use CLI/SDK for everything.

**What We're Building:**
Web-based admin panel providing AWS Console experience for local development:
- Visual management of S3 buckets, SQS queues, Lambda functions, DynamoDB tables, etc.
- Service dashboards showing resource state
- Log inspection (CloudWatch Logs, SES emails, SNS messages)
- Resource creation/deletion without CLI commands
- Real-time monitoring of emulated services

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
