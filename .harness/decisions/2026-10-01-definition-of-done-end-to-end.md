# Definition of Done: DONE MEANS DONE

**Date:** 2026-10-01  
**Status:** MANDATORY - NO EXCEPTIONS  
**Deciders:** roeibar  
**Type:** Process

## Decision

**DONE = DONE. Not "mostly done", not "coded but not wired", not "works in isolation". DONE.**

Working end-to-end, frontend to backend to database. All wired. All checked. Period.

No story is "done" if:
- ❌ Frontend isn't wired to backend API
- ❌ Backend API isn't wired to database
- ❌ CORS isn't configured
- ❌ Middleware is missing
- ❌ Authentication/authorization isn't working
- ❌ Any other integration piece is missing

## Context

Too many times in development, work is marked "done" when only individual pieces work in isolation:
- "The UI component renders" (but doesn't call the API)
- "The API endpoint exists" (but isn't wired to the database)
- "The database schema is created" (but queries fail)

This is NOT done. This is partially complete at best.

## Required Before Marking "Done"

1. **Golden Path Works:**
   - User can perform the action in the UI
   - UI calls the backend API successfully
   - Backend processes the request
   - Data is saved to/retrieved from database
   - Response flows back to UI
   - UI displays the result

2. **All Wiring Verified:**
   - CORS configured and tested
   - Middleware applied (auth, rate limiting, logging, etc.)
   - Error handling works end-to-end
   - No 404s, no CORS errors, no "middleware not found"

3. **Integration Test Proves It:**
   - Not just unit tests passing
   - Run the actual feature in the UI
   - Verify data appears in database
   - Verify backend logs show the operation

## What "Working End-to-End" Means

**Example: Create S3 Bucket Story**

❌ **NOT Done:**
- UI has a "Create Bucket" form that renders
- Backend has `POST /api/s3/buckets` endpoint defined
- But clicking "Create" in UI gives CORS error
- Or API call returns 500 because boto3 isn't configured
- Or bucket is created in MiniStack but doesn't appear in UI list

✅ **Actually Done:**
1. User opens UI, navigates to S3 page
2. User clicks "Create Bucket", fills in name
3. User clicks "Submit"
4. Frontend calls `POST /api/s3/buckets` successfully (no CORS errors)
5. Backend receives request, validates, calls MiniStack boto3 API
6. Bucket is created in MiniStack
7. Backend saves bucket metadata to FalkorDB
8. Backend returns success to frontend
9. Frontend shows success message
10. UI list refreshes and new bucket appears
11. Real-time update (SSE) notifies other tabs/users
12. Developer can verify bucket exists in MiniStack via AWS CLI

**All 12 steps must work before marking done.**

## Testing Standard

Before marking story "done", developer must:

1. **Run the golden path manually:**
   - Start frontend dev server
   - Start backend API
   - Start FalkorDB
   - Start MiniStack (or point to running instance)
   - Open browser, perform the action
   - Verify it works end-to-end

2. **Check backend logs:**
   - API received request
   - API called MiniStack successfully
   - API updated FalkorDB successfully
   - No errors in logs

3. **Check database:**
   - Query FalkorDB directly
   - Verify resource node exists
   - Verify relationships are correct

4. **Check MiniStack:**
   - Use AWS CLI to verify resource exists in MiniStack
   - Confirm state matches what UI shows

## Consequences

### Positive
- ✅ No "looks done but doesn't work" stories
- ✅ No rework cycles to add missing wiring
- ✅ Higher quality, fewer integration bugs
- ✅ Faster overall delivery (no back-and-forth)

### Negative
- ⚠️ Stories take slightly longer to complete (but are actually complete)
- ⚠️ Developers can't rush through stories

### What Happens If Violated

If a story is marked "done" but isn't working end-to-end:
1. Story is moved back to "in-progress"
2. Developer must fix ALL wiring issues
3. Story isn't "done" again until end-to-end works

**No exceptions.** "Mostly working" is not done.

## Implementation Notes

**For Dev Agent (`lch-agent-dev`):**
- Before marking story `done` in `sprint-status.yaml`, verify end-to-end
- Run manual test of golden path
- Check logs, database, MiniStack
- If ANY piece doesn't work, keep status `in-progress`

**For Code Review:**
- Reviewer must verify end-to-end integration
- "Unit tests pass" is not sufficient
- Reviewer runs the feature in UI before approving

**For QA Gates (`/lch-qa-gates`):**
- Automated check: does UI successfully call API?
- Automated check: does API successfully update database?
- Automated check: does data appear in UI?

## Related Rules

See also:
- `~/.claude/rules/testing.md` - Definition of Done section
- `~/.claude/rules/alignment.md` - Cross-layer contract verification (§ 4)
- `~/.claude/rules/code-intelligence.md` - Wiring proof (§ 2b)

This decision amplifies those rules with explicit emphasis on end-to-end integration.
