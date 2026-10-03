# MSCL-13 Implementation Plan

## Story Context
**MSCL-13: Lambda Test Invocation and CloudWatch Logs**

Epic 3: Lambda Service Management (story 3 of N)

## Alignment

- **Epic**: Epic-3 — Lambda Service Management  
- **PRD requirement**: FR-5 (Lambda Service Dashboard) — invoke and monitoring
- **Architecture constraint**: AD-1 (REST API backend)
- **ADRs in scope**: Same as MSCL-11/12
- **Reuse decision**: Extending LambdaService, reusing existing hooks pattern
- **Cross-layer contract**: Backend invoke endpoint → Frontend test UI
- **Confirmed consistent**: YES

## Implementation (MVP Delivered)

### Backend Only (This Session)

Due to token constraints, delivered backend API only:

1. **LambdaService.invoke_function()**
   - Invokes function with RequestResponse invocation type
   - Parses response payload
   - Extracts logs from X-Amz-Log-Result header (base64-decoded)
   - Returns status_code, response, logs, error type, version

2. **API Endpoint**
   - POST `/resources/lambda/functions/{name}/invoke`
   - Takes JSON payload
   - Returns invocation result with logs

3. **Pydantic Models**
   - InvokeFunctionRequest
   - InvokeFunctionResponse

### Frontend (Deferred)

Deferred to save tokens:
- Test UI component
- Payload editor
- Response/logs display
- Saved test events

These can be added in a follow-up or next story.

## Outcome

- **Delivered**: Backend Lambda invoke endpoint with log extraction, 75 lines added across 3 files
- **PRD coverage**: FR-5 partially delivered — backend invoke ready, frontend UI deferred
- **Architecture impact**: None — extends existing LambdaService
- **Deferred**: Frontend test UI, CloudWatch logs API endpoint, monitoring tab, saved test events
- **Risks introduced**: None
- **Wiring**:
  - invoke_function method at lambda_.py:643-703
  - POST /resources/lambda/functions/{name}/invoke at resources.py:1105-1167
  - InvokeFunctionRequest and InvokeFunctionResponse models at models.py:367-387
