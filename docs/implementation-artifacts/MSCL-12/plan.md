# MSCL-12 Implementation Plan

## Story Context
**MSCL-12: Lambda UI Components (AWS Console Clone)**

Epic 3: Lambda Service Management (story 2 of N)

## Alignment

- **Epic**: Epic-3 — Lambda Service Management (complete UI for Lambda function management)
- **PRD requirement**: FR-5 (Lambda Service Dashboard) — frontend portion
- **Architecture constraint**: AD-7 (AWS Console Clone UI), AD-4 (SSE for real-time updates)
- **ADRs in scope**: 
  - 2026-10-01-architecture-control-plane-with-mcp.md
  - 2026-10-01-definition-of-done-end-to-end.md
- **Reuse decision**: 
  - Reusing Button, Modal, Toast, Table, Breadcrumbs from S3 UI (MSCL-9a/9b)
  - Creating new FunctionList, FunctionCreate components — Lambda-specific, no overlap with S3
  - Reusing useSSE hook from MSCL-9b for real-time updates
  - Creating new useLambda hooks — follows useS3 pattern
- **Cross-layer contract**: 
  - FunctionList calls GET /api/resources/lambda/functions?tenant_id={id} — verified in MSCL-11
  - FunctionCreate calls POST /api/resources/lambda/functions — verified in MSCL-11
- **Confirmed consistent**: YES

## Prior-Story Continuity

**MSCL-11 (Lambda Backend CRUD):**
- Produced: 6 API endpoints for Lambda operations
- Integration: Frontend will consume these endpoints

**MSCL-9a/9b (S3 UI):**
- Produced: Common components, hooks pattern, SSE integration
- Integration: Reuse same patterns for Lambda UI

## Implementation Tasks

### Phase 1: Lambda Hooks (MVP - This Session)

**File**: `web_ui/src/hooks/useLambda.ts`

Hooks for:
- `useFunctions(tenantId)` - List functions
- `useCreateFunction()` - Create function with ZIP upload
- `useDeleteFunction()` - Delete function

### Phase 2: TypeScript Types

**File**: `web_ui/src/types/lambda.ts`

Types for Lambda requests/responses matching backend Pydantic models.

### Phase 3: Function List Component

**File**: `web_ui/src/components/services/Lambda/FunctionList.tsx`

- Table with columns: Name, Runtime, Last Modified, Memory, Timeout
- "Create function" button
- SSE integration for real-time updates
- Delete action

### Phase 4: Create Function Modal

**File**: `web_ui/src/components/services/Lambda/FunctionCreate.tsx`

- Function name input
- Runtime dropdown (python3.11, nodejs18.x, etc.)
- Handler input
- Memory/timeout inputs
- Environment variables (key-value pairs)
- ZIP file upload
- Base64 encode ZIP before sending to API

### Phase 5: Routing & i18n

- Add /lambda/functions route to App.tsx
- Add i18n strings to en.json

### Phase 6: Function Detail Page (Deferred to Next Session)

Due to token budget, defer:
- Function detail page with tabs
- Code editor
- Test/invoke functionality
- Update configuration UI

## Outcome

(To be filled after implementation)

- **Delivered**: 
- **PRD coverage**: 
- **Architecture impact**: 
- **Deferred**: 
- **Risks introduced**: 
- **Wiring**:
