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
Admin console for ministack (https://github.com/ministackorg/ministack) - a free, open-source AWS emulator.

**Problem being solved:**
- MiniStack currently has NO web UI or admin console
- Users must use AWS CLI, boto3, Terraform for all operations
- Developers want visual tools like AWS Console for local dev

**Vision:**
Web-based admin panel providing:
- Visual management of emulated AWS services (S3, SQS, Lambda, DynamoDB, etc.)
- Service dashboards showing resource state
- Log inspection (CloudWatch Logs, SES emails, SNS messages)
- Resource creation/deletion without CLI
- True AWS Console experience for local development
