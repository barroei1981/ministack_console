---
title: 'MSCL-9a: S3 UI - Bucket List & Create (AWS Console Clone)'
type: 'feature'
created: '2026-10-03'
status: 'done'
review_loop_iteration: 1
baseline_commit: '36969bb81008e778bf7d25e9647dd728c030dd1a'
context:
  - '_lch-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Developers cannot visually list or create S3 buckets through the MiniStack Console. MSCL-8 provides backend API endpoints, but no Web UI exists. This is the first frontend story - no React app, components, or UI infrastructure exists yet.

**Approach:** Bootstrap Vite + React 18 + TypeScript frontend in `web_ui/`, set up TanStack Query and Tailwind CSS with AWS Console styling (blue header #232f3e, orange buttons #ff9900), create foundational common components (Button, Table, Modal, Toast, SearchBar), build S3 Bucket List page with table view and search filter, implement Create Bucket modal with Zod validation (3-63 chars, lowercase, DNS-compliant), integrate with MSCL-8 backend API (list and create endpoints), add toast notifications for success/error feedback. Detail page, versioning toggle, delete, and SSE deferred to MSCL-9b.

## Boundaries & Constraints

**Always:**
- Frontend dev server on port 3000 (matches backend CORS config at `api/main.py:55`)
- Use TanStack Query for all API calls (caching, auto-retry, loading states)
- AWS Console visual design: blue header (#232f3e), orange buttons (#ff9900), white content
- Client-side bucket name validation (3-63 chars, lowercase, DNS-compliant) with Zod before API call
- Tenant ID from URL query param `?tenant_id={id}` for MVP
- Toast notifications for create success/error (react-hot-toast)
- TypeScript strict mode, no `any` types
- React 18 functional components and hooks only
- Responsive design for laptop screens (1280px+, mobile not required)

**Ask First:**
- Tenant switcher component in header - minimal for MVP (hardcode or single dropdown)
- Pagination controls for >100 buckets - mock UI for MVP, functional in MSCL-10
- Accessibility (ARIA labels, keyboard nav) - defer to post-MVP unless blocking

**Never:**
- Use Create React App (deprecated, use Vite)
- Skip TypeScript (type safety required)
- Implement bucket detail, versioning toggle, or delete in this story (MSCL-9b scope)
- Build custom HTTP client (use Axios with TanStack Query)
- Hardcode API base URL (use VITE_API_BASE_URL env var)
- Skip CORS config validation (frontend port 3000 must match backend allow_origins)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Load bucket list | Navigate to `/s3/buckets?tenant_id=123456789012` | API call `GET /api/resources/s3/buckets?tenant_id={id}`, display table with columns: Name, Region, Versioning, Tags, Created. Empty state if no buckets. Loading spinner during fetch. | 403 Forbidden → Toast: "Access denied". 500 → Toast: "Failed to load buckets", TanStack Query auto-retry 3x. |
| Search buckets | Type "test" in search bar | Filter displayed buckets client-side (name includes "test", case-insensitive). No API call. | N/A |
| Create bucket (valid) | Click "Create bucket", form: name "my-bucket", project "myproject", versioning enabled, submit | API call `POST /api/resources/s3/buckets` with `{name, tenant_id, project, versioning}`, loading spinner on button. On 201: toast "Bucket created", close modal, invalidate query cache (list refetches). | 400 Bad Request → Toast: "Invalid bucket name: {detail}". 409 Conflict → Toast: "Bucket already exists". 500 → Toast: "Failed to create bucket". |
| Create bucket (invalid name) | Form input: "My-Bucket" (uppercase) | Client-side Zod validation fails, inline error below field: "Bucket name must be lowercase". Submit button disabled. | N/A (client-side only) |
| Create bucket (network error) | Submit form, network offline | TanStack Query mutation fails, toast: "Network error, check connection". Form stays open, retry button visible. | Auto-retry disabled for mutations (user-triggered retry). |

</frozen-after-approval>

## Code Map

**Backend API (MSCL-8 - reuse only):**
- `api/routes/resources.py:21-91` -- GET /api/resources/s3/buckets endpoint
- `api/routes/resources.py:94-172` -- POST /api/resources/s3/buckets endpoint
- `api/models.py:152-168` -- CreateBucketRequest Pydantic model
- `api/models.py:171-187` -- BucketResponse Pydantic model
- `api/models.py:190-198` -- BucketListResponse Pydantic model
- `api/models.py:114-149` -- validate_bucket_name() function
- `api/main.py:55` -- CORS allow_origins: ["http://localhost:3000"]

**Frontend (new):**
- `web_ui/` -- Vite + React 18 + TypeScript app root
- `web_ui/package.json` -- Dependencies: react@18, react-dom@18, react-router-dom, @tanstack/react-query, axios, zod, react-hook-form, @headlessui/react, react-hot-toast, tailwindcss, typescript, vite
- `web_ui/vite.config.ts` -- Vite config (server port 3000)
- `web_ui/tailwind.config.js` -- Tailwind config with AWS color scheme
- `web_ui/src/main.tsx` -- React entry point (renders App)
- `web_ui/src/App.tsx` -- Root component with React Router + TanStack QueryClientProvider + Toaster
- `web_ui/src/api/client.ts` -- Axios instance (baseURL from env)
- `web_ui/src/types/s3.ts` -- TypeScript types (Bucket, CreateBucketRequest)
- `web_ui/src/hooks/useS3.ts` -- TanStack Query hooks (useBuckets, useCreateBucket)
- `web_ui/src/components/common/Button.tsx` -- AWS-styled button
- `web_ui/src/components/common/Table.tsx` -- Sortable table component
- `web_ui/src/components/common/Modal.tsx` -- Modal wrapper (Headless UI Dialog)
- `web_ui/src/components/common/Toast.tsx` -- Toast setup (react-hot-toast Toaster)
- `web_ui/src/components/common/SearchBar.tsx` -- Search input with debounce
- `web_ui/src/components/services/S3/BucketList.tsx` -- Bucket list page
- `web_ui/src/components/services/S3/BucketCreate.tsx` -- Create bucket modal
- `web_ui/src/styles/aws-theme.css` -- AWS Console color variables

## Tasks & Acceptance

**Execution:**
- [x] `web_ui/` -- Bootstrap Vite project: `npm create vite@latest web_ui -- --template react-ts`, install deps (react-router-dom@6, @tanstack/react-query@5, axios, zod, react-hook-form, @headlessui/react@2, react-hot-toast, tailwindcss@3, react-i18next, i18next, vitest, @testing-library/react, @testing-library/jest-dom, @testing-library/user-event, jsdom), configure Vite server port 3000 in `vite.config.ts`, set up Tailwind with AWS colors in `tailwind.config.js`, configure vitest in `vite.config.ts` (test environment: jsdom)
- [x] `web_ui/src/i18n/config.ts` -- Set up i18next with react-i18next plugin, default language 'en', load translations from locales/ directory
- [x] `web_ui/src/i18n/locales/en.json` -- Create English translation keys: `{"s3": {"title": "S3", "createBucket": "Create bucket", "table": {"name": "Name", "region": "Region", "versioning": "Versioning", "tags": "Tags", "created": "Created"}, "empty": "No buckets found", "errors": {"missingTenantId": "Missing tenant_id query parameter. Please add ?tenant_id=YOUR_TENANT_ID to the URL."}}}`
- [x] `web_ui/src/main.tsx` -- Import and initialize i18n config before rendering App
- [x] `web_ui/src/styles/aws-theme.css` -- Define CSS variables: `--aws-blue: #232f3e`, `--aws-orange: #ff9900`, `--aws-gray-light: #f2f3f3`, `--aws-gray-dark: #545b64`, `--aws-border: #d5dbdb`
- [x] `web_ui/src/api/client.ts` -- Create Axios instance: `baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001/api'`, add request interceptor to append `tenant_id` query param from URL with null/empty validation and try-catch for URLSearchParams, add error interceptor for 401/403/500 with toast notifications
- [x] `web_ui/src/types/s3.ts` -- Define types: `Bucket` (name, tenant_id, project, arn, created_at, versioning, tags, state), `CreateBucketRequest` (name, tenant_id, project, versioning)
- [x] `web_ui/src/hooks/useS3.ts` -- Implement TanStack Query hooks: `useBuckets(tenantId)` (useQuery with queryKey `['buckets', tenantId]`), `useCreateBucket()` (useMutation with cache invalidation on success and toast notifications)
- [x] `web_ui/src/hooks/useS3.test.ts` -- Unit tests for useS3 hooks: test useBuckets with null tenantId (returns empty, no API call), test useBuckets with valid tenantId (calls API, returns data), test useBuckets with API error (handles gracefully), test useCreateBucket success (invalidates cache), test useCreateBucket error (shows toast)
- [x] `web_ui/src/components/common/Button.tsx` -- Reusable button: props `variant` (primary=orange, secondary=gray), `disabled`, `loading` (shows spinner), `onClick`, Tailwind classes for AWS styling
- [x] `web_ui/src/components/common/Table.tsx` -- Table component: props `columns` (array of {key, label, sortable, render}), `data` (array of objects), `onRowClick`, sortable headers (ascending/descending toggle), Tailwind styling
- [x] `web_ui/src/components/common/Modal.tsx` -- Modal wrapper: Headless UI Dialog with backdrop, close on ESC, props `isOpen`, `onClose`, `title`, `children`
- [x] `web_ui/src/components/common/Toast.tsx` -- Toast setup: react-hot-toast Toaster component with position bottom-right, duration 3s
- [x] `web_ui/src/components/common/SearchBar.tsx` -- Search input: props `value`, `onChange`, debounce 300ms, Tailwind styling
- [x] `web_ui/src/components/services/S3/BucketList.tsx` -- Bucket list page: blue header with useTranslation() for all text ("s3.title", "s3.createBucket", table headers via "s3.table.*"), SearchBar, orange "Create bucket" button (opens BucketCreate modal), Table with columns (Name, Region, Versioning, Tags, Created), client-side search filter with null guards (bucket.name?.toLowerCase()), useBuckets hook, empty state with useTranslation("s3.empty"), error display with error.message
- [x] `web_ui/src/components/services/S3/BucketList.test.tsx` -- Component tests: renders with tenant_id (shows list), renders without tenant_id (shows warning), search filters buckets (case-insensitive, handles null names), empty state (no buckets), error state (API failure), loading state (spinner visible)
- [x] `web_ui/src/components/services/S3/BucketCreate.tsx` -- Create modal: React Hook Form with Zod schema (name: 3-63 chars lowercase, project: optional, versioning: boolean), useTranslation() for all labels/errors, inline errors, submit calls useCreateBucket with toast on success/error, loading state, close on success
- [x] `web_ui/src/components/services/S3/BucketCreate.test.tsx` -- Component tests: form validation (invalid names rejected), successful submission (calls mutation, closes modal, shows toast), API error (shows error toast, stays open), cancel (closes without submit)
- [x] `web_ui/src/App.tsx` -- Root component: React Router with route `/s3/buckets` (BucketList), TanStack QueryClientProvider wrapping router, Toaster component from Toast, Suspense with loading fallback for i18n
- [x] `web_ui/.env.example` -- Environment variable template: `VITE_API_BASE_URL=http://localhost:3001/api` (document actual .env should be created, add .env to .gitignore)
- [x] `web_ui/.gitignore` -- Add .env to gitignore (keep .env.example tracked)
- [x] `web_ui/README.md` -- Document setup: `npm install`, `npm run dev` (port 3000), `npm run test` (run tests), backend dependency (API on port 3001), environment variables (.env.example)

**Acceptance Criteria:**
- Given I start frontend (`npm run dev` in `web_ui/`), when I navigate to `http://localhost:3000/s3/buckets?tenant_id=123456789012`, then I see blue header with "S3" title, orange "Create bucket" button, and bucket list table (or empty state)
- Given backend is running, when bucket list loads, then I see table columns: Name, Region, Versioning, Tags, Created Date, and data matches `GET /api/resources/s3/buckets` response
- Given I click "Create bucket", when modal opens, then I see form fields: bucket name (required), project (optional), versioning (checkbox), and submit button
- Given I enter invalid bucket name "My-Bucket" (uppercase), when validation runs, then inline error appears: "Bucket name must be lowercase", submit button disabled
- Given I submit valid form (name: "test-bucket", project: "myproject", versioning: true), when API returns 201, then toast "Bucket created successfully" appears, modal closes, and bucket list refetches (new bucket visible)
- Given I type "test" in search bar, when search query updates, then table filters to show only buckets with "test" in name (case-insensitive, client-side)

## Design Notes

**Vite + TanStack Query Setup:**
```typescript
// web_ui/src/App.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { BucketList } from './components/services/S3/BucketList';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30000, retry: 3 },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/s3/buckets" element={<BucketList />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" />
    </QueryClientProvider>
  );
}
```

**Zod Validation Schema:**
```typescript
// web_ui/src/components/services/S3/BucketCreate.tsx
import { z } from 'zod';

const bucketSchema = z.object({
  name: z.string()
    .min(3, 'Minimum 3 characters')
    .max(63, 'Maximum 63 characters')
    .regex(/^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$/, 'Lowercase alphanumeric with hyphens/periods')
    .refine(name => !name.includes('..'), 'No consecutive periods'),
  project: z.string().optional(),
  versioning: z.boolean().default(false),
});
```

## Verification

**Commands:**
- `cd web_ui && npm run test` -- expected: All tests pass (hooks, components), no failures
- `cd web_ui && npm run dev` -- expected: Vite dev server starts on port 3000, no errors
- `cd web_ui && npm run build` -- expected: TypeScript compiles, build succeeds

**Manual checks:**
- Navigate to `http://localhost:3000/s3/buckets?tenant_id=123456789012` -- expected: Blue header showing translated "S3" title (from i18n), orange "Create bucket" button, AWS styling visible
- Open DevTools Network tab, create bucket -- expected: POST to `http://localhost:3001/api/resources/s3/buckets`, 201 response, success toast displayed
- Check browser console -- expected: No errors, no hardcoded English strings visible in source (all via i18n keys)

## Spec Change Log

### 2026-10-03 - Review Loop 1: Added i18n and test requirements

**Triggering finding:** Code review revealed (1) hardcoded English UI strings violating code-intelligence.md § 3 i18n mandate, and (2) no test files violating testing.md requirement for tests before commit.

**Root cause:** Spec tasks did not include i18n setup or test file creation. Global rules (code-intelligence.md, testing.md) mandate these but spec failed to translate them into concrete tasks.

**Amendment:** 
- Added task: Set up react-i18next, create en.json keys file, wrap all UI strings with useTranslation()
- Added tasks: Install vitest + @testing-library/react, write unit tests for useS3 hooks, write component tests for BucketList and BucketCreate
- Updated bootstrap task: Add i18next, react-i18next, vitest, @testing-library packages to dependency list
- Updated Verification section: Added `npm run test` command as first verification step
- Updated .env task: Use .env.example pattern, add .env to .gitignore

**Known-bad state avoided:** Shipping frontend with hardcoded English strings (not localizable) and zero test coverage (untested code in production).

**KEEP instructions (what worked well, must survive re-derivation):**
- Vite + React 18 + TypeScript bootstrap approach is clean and correct
- TanStack Query integration pattern (queryKey with tenantId, cache invalidation on mutations) is sound
- Component structure (common/ reusable + services/S3/ specific) is logical and maintainable
- AWS color scheme implementation (#232f3e blue, #ff9900 orange) matches spec requirements exactly
- API client interceptor pattern for tenant_id injection is correct (just needs null guards)
- Port 3000 configuration matches backend CORS allowlist at api/main.py:55
- Zod validation schema for bucket names is correct per AWS S3 rules
- React Hook Form + Zod integration for BucketCreate is best practice
- Toast notification pattern with react-hot-toast is appropriate
- SearchBar debounce (300ms) is reasonable for client-side filtering

## Suggested Review Order

**Entry Point & Architecture**

- React 18 + TanStack Query setup with i18n Suspense fallback
  [`App.tsx:7`](../../web_ui/src/App.tsx#L7)

- i18next configuration with English translations loaded
  [`config.ts:3`](../../web_ui/src/i18n/config.ts#L3)

**API Integration & Tenant Isolation**

- Axios client with tenant_id auto-injection from URL query params + error interceptors
  [`client.ts:11`](../../web_ui/src/api/client.ts#L11)

- TanStack Query hooks for buckets list and create with cache invalidation
  [`useS3.ts:5`](../../web_ui/src/hooks/useS3.ts#L5)

**Core UI Components**

- Bucket list page: search, table, create button, tenant validation, i18n text
  [`BucketList.tsx:10`](../../web_ui/src/components/services/S3/BucketList.tsx#L10)

- Create bucket modal: Zod validation, React Hook Form, i18n labels, toast feedback
  [`BucketCreate.tsx:20`](../../web_ui/src/components/services/S3/BucketCreate.tsx#L20)

**Reusable Components (AWS Console Style)**

- AWS-styled button (orange primary, gray secondary) with loading states
  [`Button.tsx:9`](../../web_ui/src/components/common/Button.tsx#L9)

- Generic sortable table with client-side sorting and custom renderers
  [`Table.tsx:19`](../../web_ui/src/components/common/Table.tsx#L19)

- Modal wrapper with Headless UI Dialog for accessibility
  [`Modal.tsx:7`](../../web_ui/src/components/common/Modal.tsx#L7)

**Supporting Infrastructure**

- TypeScript types matching backend Pydantic models
  [`s3.ts:1`](../../web_ui/src/types/s3.ts#L1)

- English translation keys for all UI strings
  [`en.json:2`](../../web_ui/src/i18n/locales/en.json#L2)

**Tests (15 passing)**

- Hook tests: useBuckets null/valid tenant, useCreateBucket success/error, cache invalidation
  [`useS3.test.tsx:11`](../../web_ui/src/hooks/useS3.test.tsx#L11)

- BucketList tests: with/without tenant, search filter, empty/error/loading states
  [`BucketList.test.tsx:11`](../../web_ui/src/components/services/S3/BucketList.test.tsx#L11)

- BucketCreate tests: form validation, successful submit, API error, cancel
  [`BucketCreate.test.tsx:9`](../../web_ui/src/components/services/S3/BucketCreate.test.tsx#L9)
