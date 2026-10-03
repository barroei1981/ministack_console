# MSCL-14 Implementation Plan

## Story Context
**MSCL-14: DynamoDB Backend CRUD Operations**

Epic 4: DynamoDB Service Management (story 1 of N)

## Alignment

- **Epic**: Epic-4 — DynamoDB Service Management
- **PRD requirement**: FR-6 (DynamoDB Service Dashboard)
- **Architecture constraint**: AD-1 (REST API backend), AD-5 (Python + FastAPI)
- **ADRs in scope**: Same as MSCL-8 (S3 Backend), MSCL-11 (Lambda Backend)
- **Reuse decision**: Following S3Service and LambdaService patterns - dual-write pattern, structured logging, SSE events
- **Cross-layer contract**: Backend endpoints ready for future frontend UI
- **Confirmed consistent**: YES

## Implementation

### 1. DynamoDBService (api/services/dynamodb.py)

New service class following S3Service/LambdaService patterns:

**Methods:**
- `__init__(tenant_id)` - Initialize with tenant ID validation
- `_create_client()` - Create boto3 DynamoDB client for MiniStack
- `list_tables()` - Query FalkorDB for table metadata
- `get_table(name)` - Get single table from FalkorDB
- `create_table(...)` - Dual-write pattern (MiniStack → FalkorDB → SSE)
- `delete_table(name)` - Dual-delete pattern (MiniStack → FalkorDB → SSE)
- `scan_items(table_name, limit, ...)` - Scan table items with pagination
- `put_item(table_name, item)` - Put item to table

**Key Features:**
- Tenant isolation via 12-digit access key
- Structured logging (OPERATIONAL, AUDIT, SECURITY)
- OpenTelemetry tracing
- Rollback on FalkorDB failure
- SSE event emission

### 2. Pydantic Models (api/models.py)

Added models:
- `CreateTableRequest` - Create table request with validation
- `TableResponse` - Table details response
- `TableListResponse` - List tables response
- `ScanItemsRequest` - Scan items request
- `ScanItemsResponse` - Scan items response with pagination
- `PutItemRequest` - Put item request
- `PutItemResponse` - Put item success response
- `DeleteTableResponse` - Delete table response

**Validation:**
- Table name: 3-255 chars, alphanumeric + underscore/hyphen/period
- Tenant ID: exactly 12 digits
- Billing mode: PAY_PER_REQUEST or PROVISIONED
- Key schema: HASH and optionally RANGE keys

### 3. API Endpoints (api/routes/resources.py)

Added 4 endpoints:

#### GET `/resources/dynamodb/tables`
- List all tables for tenant
- Returns: table name, ARN, key schema, billing mode, item count

#### POST `/resources/dynamodb/tables`
- Create new table
- Body: table name, key schema, attribute definitions, billing mode
- Returns: 201 with created table metadata

#### GET `/resources/dynamodb/tables/{table_name}/items`
- Scan table items with pagination
- Query params: tenant_id, limit (1-1000)
- Returns: items list, count, last_evaluated_key

#### PUT `/resources/dynamodb/tables/{table_name}/items`
- Put item to table (create or update)
- Body: item data in DynamoDB JSON format
- Returns: success status

**All endpoints:**
- Tenant ID validation via middleware
- 403 if tenant mismatch
- Structured logging for all operations
- Error handling with appropriate status codes

## Alignment with Patterns

- **Dual-write**: MiniStack first, then FalkorDB, then SSE
- **Rollback**: Delete from MiniStack if FalkorDB write fails
- **Logging**: OPERATIONAL for actions, AUDIT for data changes
- **Tracing**: OpenTelemetry spans for all operations
- **SSE**: RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_DELETED events

## Testing Notes

Manual testing plan:
1. Create table with HASH key
2. List tables - verify appears
3. Put items to table
4. Scan items - verify returned
5. Delete table - verify removed

Integration with MiniStack at localhost:4566.

## Outcome

- **Delivered**: Complete DynamoDB backend API with 4 endpoints, ~600 lines added
- **PRD coverage**: FR-6 backend foundation ready
- **Architecture impact**: None - follows existing patterns
- **Deferred**: Frontend UI (next story)
- **Risks introduced**: None
- **Wiring**:
  - DynamoDBService at api/services/dynamodb.py:1-505
  - Pydantic models at api/models.py:377-505
  - API endpoints at api/routes/resources.py:1175-1427
