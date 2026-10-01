# Story MSCL-13: Lambda Test Invocation and CloudWatch Logs

**Epic:** Epic 3 - Lambda Service Management  
**Story Points:** 5  
**Priority:** P1  
**Dependencies:** MSCL-11, MSCL-12

## User Story

As a **developer**,  
I want **to test Lambda functions and view their CloudWatch logs**,  
So that **I can debug function execution without external tools**.

## Acceptance Criteria

**Given** I am on a Lambda function's detail page  
**When** I click "Test"  
**Then** I can enter a JSON payload in a text editor  
**And** I can save test events for reuse  
**And** I click "Invoke" to execute the function

**Given** I invoke a Lambda function with a test payload  
**When** the invocation completes  
**Then** I see the response body, status code, and execution duration  
**And** I see the function logs streamed from CloudWatch  
**And** errors are highlighted in red

**Given** I am on the Monitoring tab  
**When** the page loads  
**Then** I see recent invocations with timestamps  
**And** I can click on an invocation to view its logs  
**And** I can filter logs by time range

**Architecture Decisions:** AD-1 (REST API backend for CloudWatch log fetching)
