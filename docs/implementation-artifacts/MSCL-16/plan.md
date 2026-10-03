# MSCL-16 Implementation Plan

## Story Context
**MSCL-16: DynamoDB Item Browser and JSON Editor**

Epic 4: DynamoDB Service Management (story 3 of 3)

## Alignment

- **Epic**: Epic-4 — DynamoDB Service Management
- **PRD requirement**: FR-5 (DynamoDB Service Dashboard) - item management
- **Architecture constraint**: AD-1 (REST API backend), AD-7 (AWS Console Clone UI)
- **ADRs in scope**: Same as MSCL-14, MSCL-15
- **Reuse decision**: Following S3 BucketDetail pattern - tabs for Overview and Items
- **Cross-layer contract**: Backend delete_item endpoint → Frontend ItemBrowser
- **Confirmed consistent**: YES

## Implementation

### 1. Backend: Delete Item Endpoint

**Extended DynamoDBService (api/services/dynamodb.py):**
- `delete_item(table_name, key)` - Delete item by primary key
  - Uses boto3 `delete_item` operation
  - Logs AUDIT event with BEFORE state
  - Emits SSE RESOURCE_UPDATED event
  - OpenTelemetry tracing

**Added Pydantic Models (api/models.py):**
- `DeleteItemRequest` - tenant_id, key (primary key dict)
- `DeleteItemResponse` - success boolean

**Added API Endpoint (api/routes/resources.py):**
- `DELETE /resources/dynamodb/tables/{table_name}/items`
  - Accepts item key in request body
  - Validates tenant match
  - Returns success status
  - 404 if table not found, 403 if forbidden

### 2. Frontend: Table Detail Page

**TableDetail Component (web_ui/src/components/services/DynamoDB/TableDetail.tsx):**
- Two tabs: Overview, Items
- Overview tab shows:
  - Table status, created date, billing mode, item count
  - Primary key details (partition key, sort key with types)
  - Project tag if exists
- Items tab renders ItemBrowser component
- Back button to table list
- Follows BucketDetail UI pattern

**Key Features:**
- Tab navigation with active state highlighting
- Extracts key schema from table metadata
- Maps AttributeType to human-readable labels (String/Number/Binary)
- URL params for tenant ID preservation

### 3. Frontend: Item Browser

**ItemBrowser Component (web_ui/src/components/services/DynamoDB/ItemBrowser.tsx):**
- Table view of all items (scan operation)
- Displays key columns:
  - Key (partition + sort key)
  - Attributes (JSON preview, truncated)
  - Actions (Edit, Delete buttons)
- Empty state with "Create your first item" CTA
- Real-time updates via TanStack Query invalidation

**Item Actions:**
- **Create**: Opens modal with JSON editor, empty template
- **Edit**: Opens modal with current item JSON
- **Delete**: Confirmation prompt, calls delete API
- **Validation**: JSON syntax checking before submit

**JSON Editor Modal:**
- Textarea with monospace font (15 rows)
- Syntax validation on input
- Error display for invalid JSON or API errors
- Example hint showing DynamoDB JSON format
- Save/Cancel buttons

**DynamoDB JSON Format:**
```json
{
  "id": {"S": "123"},
  "name": {"S": "Example"},
  "age": {"N": "25"}
}
```

### 4. React Hooks Extension

**Extended useDynamoDB.ts:**
- `useDeleteItem()` - Mutation hook
  - DELETE request to items endpoint
  - Invalidates table items query on success
  - Error handling

### 5. Routing

**Updated App.tsx:**
- Added route: `/dynamodb/tables/:tableName` → TableDetail
- Imports TableDetail component

## Alignment with Patterns

- **Dual-write backend**: DynamoDB delete → audit log → SSE event
- **TanStack Query**: Automatic cache invalidation on mutations
- **AWS Console styling**: Tab navigation, table layout, orange buttons
- **TypeScript validation**: Full type safety
- **JSON editor**: Inline validation before submission

## Testing Notes

Manual testing plan:
1. Navigate to table detail from table list
2. Overview tab shows correct metadata
3. Switch to Items tab
4. Click "Create item" - JSON editor opens
5. Enter valid DynamoDB JSON - item created
6. Item appears in list
7. Click "Edit" on item - JSON editor shows current data
8. Modify and save - item updated
9. Click "Delete" - confirmation prompt
10. Confirm - item deleted and list updates

DynamoDB JSON format notes:
- Attribute values wrapped in type descriptors: `{"S": "string"}`, `{"N": "123"}`, `{"B": "binary"}`
- Primary key must match table schema
- Sort key required if table has one

## Outcome

- **Delivered**: Complete DynamoDB item management UI with CRUD operations, ~400 lines added
- **PRD coverage**: FR-5 (DynamoDB portion) complete - full CRUD for tables and items
- **Architecture impact**: None - follows existing patterns
- **Deferred**: Batch operations (multiple deletes), query operation (vs scan), item filtering
- **Risks introduced**: None
- **Wiring**:
  - delete_item method at api/services/dynamodb.py:520-588
  - DeleteItemRequest/Response at api/models.py:514-522
  - DELETE /items endpoint at api/routes/resources.py:1463-1518
  - TableDetail at web_ui/src/components/services/DynamoDB/TableDetail.tsx:1-180
  - ItemBrowser at web_ui/src/components/services/DynamoDB/ItemBrowser.tsx:1-225
  - useDeleteItem at web_ui/src/hooks/useDynamoDB.ts:155-189
  - Route at web_ui/src/App.tsx:12,30
