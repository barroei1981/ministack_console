# MSCL-15 Implementation Plan

## Story Context
**MSCL-15: DynamoDB UI Components (AWS Console Clone)**

Epic 4: DynamoDB Service Management (story 2 of N)

## Alignment

- **Epic**: Epic-4 — DynamoDB Service Management
- **PRD requirement**: FR-6 (DynamoDB Service Dashboard)
- **Architecture constraint**: AD-7 (AWS Console Clone UI)
- **ADRs in scope**: Same as MSCL-9a/9b (S3 UI), MSCL-12 (Lambda UI)
- **Reuse decision**: Following S3/Lambda UI patterns - TanStack Query hooks, SSE integration, AWS Console styling
- **Cross-layer contract**: Frontend consumes MSCL-14 backend APIs (list, create tables)
- **Confirmed consistent**: YES

## Implementation

### 1. TypeScript Types (web_ui/src/types/dynamodb.ts)

New types file following s3.ts and lambda.ts patterns:

**Types:**
- `KeySchemaElement` - Partition/sort key definition (HASH/RANGE)
- `AttributeDefinition` - Attribute name and type (S/N/B)
- `ProvisionedThroughput` - Read/write capacity units
- `DynamoDBTable` - Complete table metadata
- `CreateTableRequest` - Create table payload
- `TableListResponse` - List tables response
- `ScanItemsResponse` - Scan items response with pagination

**Constants:**
- `ATTRIBUTE_TYPES` - String, Number, Binary
- `BILLING_MODES` - On-demand, Provisioned

### 2. React Hooks (web_ui/src/hooks/useDynamoDB.ts)

TanStack Query hooks following useS3.ts and useLambda.ts patterns:

**Hooks:**
- `useTables(tenantId)` - Query all tables for tenant
- `useCreateTable()` - Mutation to create table
- `useDeleteTable()` - Mutation to delete table
- `useTableItems(tableName, tenantId)` - Query table items (scan)
- `usePutItem()` - Mutation to put item

All hooks invalidate relevant query keys on success for cache updates.

### 3. Table List Component (web_ui/src/components/services/DynamoDB/TableList.tsx)

AWS Console-style table list following BucketList and FunctionList patterns:

**Features:**
- Table with columns: name (link), partition key, sort key, item count, created date, actions
- Search/filter by table name
- Create table button (orange, top right)
- Delete confirmation modal
- Empty state with "Create your first table" CTA
- SSE real-time updates via useSSE hook
- Key type display: "attribute_name (String/Number/Binary)"

**Key Implementation:**
- Extract partition key (HASH) from key_schema
- Extract sort key (RANGE) from key_schema
- Map AttributeType to human-readable labels
- Navigate to table detail on name click (route pending)

### 4. Create Table Component (web_ui/src/components/services/DynamoDB/TableCreate.tsx)

Full create table form following BucketCreate and FunctionCreate patterns:

**Sections:**

**Table Details:**
- Table name input (3-255 chars, alphanumeric + _-.)
- Project input (optional)

**Partition Key:**
- Attribute name input (required)
- Type selector (String/Number/Binary)

**Sort Key (optional):**
- Checkbox to enable
- Attribute name input
- Type selector
- Validation: sort key must differ from partition key

**Table Settings:**
- Billing mode selector (On-demand/Provisioned)
- Provisioned throughput inputs (if Provisioned mode):
  - Read capacity units (min 1)
  - Write capacity units (min 1)

**Validation:**
- Table name: 3-255 chars, alphanumeric + underscore/hyphen/period
- Partition key name required
- Sort key name required if enabled
- Sort key must differ from partition key
- Capacity units: integers >= 1

**Form Behavior:**
- Client-side validation with error messages
- Submit creates table via useCreateTable hook
- Navigate to table list on success
- Display error on failure

### 5. Routes (web_ui/src/App.tsx)

Added 2 routes:
- `/dynamodb/tables` - TableList component
- `/dynamodb/create` - TableCreate component

### 6. SSE Integration (web_ui/src/hooks/useSSE.ts)

Extended SSE handler to support DynamoDB events:
- `dynamodb:table` resource type
- Invalidates `['dynamodb', 'tables', tenantId]` on create/delete
- Invalidates table items on update
- Toast notifications for table creation

## Alignment with Patterns

- **URL params for tenant**: Uses `?tenant_id={id}` in URL (same as S3/Lambda)
- **TanStack Query**: All data fetching via hooks with cache invalidation
- **SSE real-time**: Automatic refetch on backend events
- **AWS Console styling**: Orange primary buttons, table layout, form sections
- **TypeScript validation**: Full type safety across components
- **Navigation**: Preserves tenant_id in URLs across navigation

## Testing Notes

Manual testing plan:
1. Navigate to `/dynamodb/tables?tenant_id=123456789012`
2. List should load (empty state if no tables)
3. Click "Create table"
4. Fill form: name, partition key (String), optional sort key
5. Select billing mode (On-demand/Provisioned)
6. Submit - should create and navigate back
7. Table should appear in list
8. Delete table - confirmation modal
9. SSE: table list updates in real-time

## Outcome

- **Delivered**: Complete DynamoDB frontend UI with list and create, ~450 lines added
- **PRD coverage**: FR-6 frontend foundation ready (AC1-AC2 complete)
- **Architecture impact**: None - follows existing patterns
- **Deferred**: Table detail page with tabs (Overview, Items, Indexes, Monitoring)
- **Risks introduced**: None
- **Wiring**:
  - DynamoDB types at web_ui/src/types/dynamodb.ts:1-63
  - React hooks at web_ui/src/hooks/useDynamoDB.ts:1-152
  - TableList at web_ui/src/components/services/DynamoDB/TableList.tsx:1-180
  - TableCreate at web_ui/src/components/services/DynamoDB/TableCreate.tsx:1-338
  - Routes at web_ui/src/App.tsx:10-11,29-30
  - SSE handler at web_ui/src/hooks/useSSE.ts:63-73
