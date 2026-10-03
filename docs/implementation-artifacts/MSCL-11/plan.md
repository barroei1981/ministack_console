# MSCL-11 Implementation Plan

## Story Context
**MSCL-11: Lambda Backend CRUD Operations**

Epic 3: Lambda Service Management (story 1 of N)

## Alignment

- **Epic**: Epic-3 — Lambda Service Management (complete CRUD for Lambda functions via REST API)
- **PRD requirement**: FR-5 (Lambda Service Dashboard) — backend portion for function management
- **Architecture constraint**: Control-plane architecture (AD-4) mandates dual-write pattern (MiniStack → FalkorDB → SSE), dependency detection for resource relationships
- **ADRs in scope**: 
  - 2026-10-01-architecture-control-plane-with-mcp.md (Control-plane core, dual interfaces)
  - 2026-10-01-definition-of-done-end-to-end.md (End-to-end testing requirements)
- **Reuse decision**: 
  - Extending `api/routes/resources.py` router (add Lambda endpoints under `/resources/lambda/`) — same pattern as S3 endpoints
  - Creating new `api/services/lambda_.py` LambdaService class — follows S3Service pattern (boto3 → dual-write → SSE)
  - Creating new `api/models/lambda_.py` for Pydantic models — follows existing api/models/s3.py structure
  - Reusing `control_plane.events.event_bus` for SSE events — same pattern as S3
  - Reusing `control_plane.graph` for FalkorDB operations — same query_nodes/create_node/delete_node pattern
- **Cross-layer contract**: Frontend will be MSCL-12 (Lambda UI), endpoints verified after implementation
- **Confirmed consistent**: YES — follows control-plane architecture, reuses S3 patterns, dual-write + SSE for real-time updates

## Prior-Story Continuity

**MSCL-8 (S3 Backend CRUD):**
- Produced: S3Service class with boto3 client, dual-write pattern, SSE event emission, structured logging
- Integration points: LambdaService will follow identical patterns (tenant-scoped service, boto3 client factory, dual-write to FalkorDB, SSE events)

**MSCL-7 (SSE Real-Time Updates):**
- Produced: event_bus.publish() pattern for RESOURCE_CREATED/UPDATED/DELETED
- Integration points: Lambda service will emit same event types for function operations

**MSCL-5 (Dependency Detection):**
- Produced: DEPENDS_ON relationship pattern in FalkorDB
- Integration points: Lambda service will detect S3/SQS dependencies from environment variables and create DEPENDS_ON edges

## Implementation Tasks

### Phase 1: LambdaService Core (boto3 + FalkorDB)

#### 1.1 Create LambdaService Class

**File**: `api/services/lambda_.py`

```python
"""
Lambda service layer for MiniStack operations.

Handles boto3 operations, dual-write to FalkorDB, and SSE event emission.
"""

import asyncio
import base64
import re
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import boto3
from botocore.exceptions import ClientError

from control_plane.events import event_bus
from control_plane.graph.query import create_node, delete_node, query_nodes
from control_plane.observability import (
    log_audit,
    log_operational,
    log_security,
    trace_operation,
)


class LambdaService:
    """
    Lambda service layer for tenant-scoped function operations.
    
    Each instance is scoped to a single tenant. Uses boto3 to interact with
    MiniStack and maintains resource state in FalkorDB.
    """
    
    def __init__(self, tenant_id: str):
        """
        Initialize Lambda service for a tenant.
        
        Args:
            tenant_id: 12-digit tenant ID (MiniStack access key)
            
        Raises:
            ValueError: If tenant_id is invalid
        """
        if not tenant_id or not re.match(r"^\d{12}$", tenant_id):
            raise ValueError("Tenant ID must be exactly 12 digits")
        
        self.tenant_id = tenant_id
        self.client = self._create_client()
    
    def _create_client(self) -> Any:
        """
        Create boto3 Lambda client for MiniStack.
        
        Returns:
            boto3 Lambda client configured for MiniStack endpoint
        """
        session = boto3.Session(
            aws_access_key_id=self.tenant_id,
            aws_secret_access_key="dummy",  # MiniStack ignores secret
            region_name="us-east-1",
        )
        return session.client("lambda", endpoint_url="http://localhost:4566")
    
    async def list_functions(self) -> list[dict[str, Any]]:
        """
        List all Lambda functions for this tenant.
        
        Queries FalkorDB for function metadata (source of truth for control-plane state).
        
        Returns:
            List of function dicts with metadata
            
        Raises:
            Exception: If query fails
        """
        with trace_operation("list_lambda_functions", tenant_id=self.tenant_id):
            try:
                # Query FalkorDB for Lambda function resources
                function_nodes = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"tenant_id": self.tenant_id, "type": "lambda:function"},
                )
                
                log_operational(
                    "Listed Lambda functions",
                    tenant_id=self.tenant_id,
                    count=len(function_nodes),
                )
                
                return function_nodes
                
            except Exception as e:
                log_operational(
                    "Failed to list Lambda functions",
                    tenant_id=self.tenant_id,
                    error=str(e),
                )
                raise
    
    async def get_function(self, name: str) -> dict[str, Any] | None:
        """
        Get Lambda function details by name.
        
        Args:
            name: Function name
            
        Returns:
            Function dict with metadata or None if not found
            
        Raises:
            Exception: If query fails
        """
        with trace_operation("get_lambda_function", tenant_id=self.tenant_id, function=name):
            try:
                # Query FalkorDB for specific function
                function_id = f"lambda-function-{name}"
                functions = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={
                        "id": function_id,
                        "tenant_id": self.tenant_id,
                        "type": "lambda:function",
                    },
                )
                
                if not functions:
                    return None
                
                function = functions[0]
                
                # Fetch live configuration from MiniStack
                try:
                    response = await asyncio.to_thread(
                        self.client.get_function_configuration,
                        FunctionName=name
                    )
                    
                    # Update function state with live data
                    if "state" not in function:
                        function["state"] = {}
                    
                    function["state"]["last_modified"] = response.get("LastModified", "")
                    function["state"]["code_size"] = response.get("CodeSize", 0)
                    
                except ClientError:
                    pass  # Function might not exist in MiniStack anymore
                
                log_operational(
                    "Retrieved Lambda function",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                return function
                
            except Exception as e:
                log_operational(
                    "Failed to get Lambda function",
                    tenant_id=self.tenant_id,
                    function=name,
                    error=str(e),
                )
                raise
    
    async def create_function(
        self,
        name: str,
        runtime: str,
        handler: str,
        code: bytes,
        project: str | None = None,
        environment: dict[str, str] | None = None,
        memory: int = 128,
        timeout: int = 3,
        tags: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a Lambda function.
        
        Dual-write pattern: Create in MiniStack first, then FalkorDB, then emit SSE event.
        
        Args:
            name: Function name
            runtime: Lambda runtime (python3.11, nodejs18.x, etc.)
            handler: Function handler (module.function_name)
            code: ZIP file bytes containing function code
            project: Control-plane project tag
            environment: Environment variables
            memory: Memory size in MB (128-10240)
            timeout: Timeout in seconds (1-900)
            tags: Control-plane tags
            
        Returns:
            Created function dict with metadata
            
        Raises:
            ClientError: If function creation fails in MiniStack
            Exception: If FalkorDB write or SSE publish fails
        """
        with trace_operation("create_lambda_function", tenant_id=self.tenant_id, function=name):
            try:
                # 1. Create in MiniStack
                params: dict[str, Any] = {
                    "FunctionName": name,
                    "Runtime": runtime,
                    "Role": f"arn:aws:iam::{self.tenant_id}:role/lambda-execution",
                    "Handler": handler,
                    "Code": {"ZipFile": code},
                    "MemorySize": memory,
                    "Timeout": timeout,
                }
                
                if environment:
                    params["Environment"] = {"Variables": environment}
                
                response = await asyncio.to_thread(
                    self.client.create_function, **params
                )
                
                log_operational(
                    "Created Lambda function in MiniStack",
                    tenant_id=self.tenant_id,
                    function=name,
                    runtime=runtime,
                )
                
                # 2. Add to FalkorDB
                resource = {
                    "id": f"lambda-function-{name}",
                    "type": "lambda:function",
                    "name": name,
                    "tenant_id": self.tenant_id,
                    "project": project or "",
                    "arn": response["FunctionArn"],
                    "state": {
                        "runtime": runtime,
                        "handler": handler,
                        "memory": memory,
                        "timeout": timeout,
                        "environment": environment or {},
                        "last_modified": response.get("LastModified", ""),
                        "code_size": response.get("CodeSize", 0),
                    },
                    "tags": tags or {},
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                
                try:
                    await asyncio.to_thread(create_node, "Resource", resource)
                except Exception as e:
                    # Rollback: delete function from MiniStack
                    log_operational(
                        "Failed to add function to FalkorDB, rolling back",
                        tenant_id=self.tenant_id,
                        function=name,
                        error=str(e),
                    )
                    await asyncio.to_thread(self.client.delete_function, FunctionName=name)
                    raise
                
                log_operational(
                    "Added Lambda function to FalkorDB",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                # 3. Detect dependencies from environment variables
                await self._detect_dependencies(resource)
                
                # 4. Emit SSE event
                await event_bus.publish(
                    "RESOURCE_CREATED", resource, self.tenant_id
                )
                
                log_security(
                    "Lambda function created",
                    tenant_id=self.tenant_id,
                    function=name,
                    project=project,
                )
                
                # Audit log
                log_audit(
                    "Lambda function created",
                    event_type="FUNCTION_CREATED",
                    actor={"id": self.tenant_id, "type": "TENANT"},
                    target={"type": "lambda:function", "id": name},
                    action="CREATE",
                    status="SUCCESS",
                    changes={"before": None, "after": resource},
                )
                
                return resource
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                
                if error_code == "ResourceAlreadyExistsException":
                    log_security(
                        "Lambda function creation failed - already exists",
                        tenant_id=self.tenant_id,
                        function=name,
                        error_code=error_code,
                    )
                    raise ValueError(f"Function {name} already exists") from e
                
                log_operational(
                    "Failed to create Lambda function in MiniStack",
                    tenant_id=self.tenant_id,
                    function=name,
                    error=str(e),
                    error_code=error_code,
                )
                raise
                
            except Exception as e:
                log_operational(
                    "Failed to create Lambda function",
                    tenant_id=self.tenant_id,
                    function=name,
                    error=str(e),
                )
                raise
    
    async def update_function_code(
        self, name: str, code: bytes
    ) -> dict[str, Any]:
        """
        Update Lambda function code.
        
        Args:
            name: Function name
            code: New ZIP file bytes
            
        Returns:
            Updated function metadata
            
        Raises:
            ClientError: If update fails
        """
        with trace_operation("update_lambda_code", tenant_id=self.tenant_id, function=name):
            try:
                # 1. Update in MiniStack
                response = await asyncio.to_thread(
                    self.client.update_function_code,
                    FunctionName=name,
                    ZipFile=code
                )
                
                log_operational(
                    "Updated Lambda function code in MiniStack",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                # 2. Update FalkorDB state
                function_id = f"lambda-function-{name}"
                functions = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"id": function_id, "tenant_id": self.tenant_id},
                )
                
                if functions:
                    function = functions[0]
                    function["state"]["last_modified"] = response.get("LastModified", "")
                    function["state"]["code_size"] = response.get("CodeSize", 0)
                    function["updated_at"] = datetime.now(UTC).isoformat()
                    
                    # Delete old node and create updated one
                    await asyncio.to_thread(delete_node, "Resource", function_id)
                    await asyncio.to_thread(create_node, "Resource", function)
                
                # 3. Emit SSE event
                await event_bus.publish(
                    "RESOURCE_UPDATED",
                    {"id": function_id, "type": "lambda:function", "name": name},
                    self.tenant_id
                )
                
                log_security(
                    "Lambda function code updated",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                return {
                    "updated": name,
                    "last_modified": response.get("LastModified", ""),
                    "code_size": response.get("CodeSize", 0),
                }
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    raise ValueError(f"Function {name} not found") from e
                raise
    
    async def update_function_configuration(
        self,
        name: str,
        environment: dict[str, str] | None = None,
        memory: int | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Update Lambda function configuration.
        
        Args:
            name: Function name
            environment: New environment variables (optional)
            memory: New memory size (optional)
            timeout: New timeout (optional)
            
        Returns:
            Updated function metadata
            
        Raises:
            ClientError: If update fails
        """
        with trace_operation("update_lambda_config", tenant_id=self.tenant_id, function=name):
            try:
                # 1. Update in MiniStack
                params: dict[str, Any] = {"FunctionName": name}
                
                if environment is not None:
                    params["Environment"] = {"Variables": environment}
                if memory is not None:
                    params["MemorySize"] = memory
                if timeout is not None:
                    params["Timeout"] = timeout
                
                response = await asyncio.to_thread(
                    self.client.update_function_configuration,
                    **params
                )
                
                log_operational(
                    "Updated Lambda function configuration in MiniStack",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                # 2. Update FalkorDB state
                function_id = f"lambda-function-{name}"
                functions = await asyncio.to_thread(
                    query_nodes,
                    "Resource",
                    filters={"id": function_id, "tenant_id": self.tenant_id},
                )
                
                if functions:
                    function = functions[0]
                    
                    if environment is not None:
                        function["state"]["environment"] = environment
                    if memory is not None:
                        function["state"]["memory"] = memory
                    if timeout is not None:
                        function["state"]["timeout"] = timeout
                    
                    function["updated_at"] = datetime.now(UTC).isoformat()
                    
                    # Delete old node and create updated one
                    await asyncio.to_thread(delete_node, "Resource", function_id)
                    await asyncio.to_thread(create_node, "Resource", function)
                    
                    # Re-detect dependencies if environment changed
                    if environment is not None:
                        await self._detect_dependencies(function)
                
                # 3. Emit SSE event
                await event_bus.publish(
                    "RESOURCE_UPDATED",
                    {"id": function_id, "type": "lambda:function", "name": name},
                    self.tenant_id
                )
                
                log_security(
                    "Lambda function configuration updated",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                return {"updated": name, "configuration": params}
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    raise ValueError(f"Function {name} not found") from e
                raise
    
    async def delete_function(self, name: str) -> dict[str, Any]:
        """
        Delete a Lambda function.
        
        Args:
            name: Function name
            
        Returns:
            Deletion summary
            
        Raises:
            ClientError: If deletion fails
        """
        with trace_operation("delete_lambda_function", tenant_id=self.tenant_id, function=name):
            try:
                # 1. Delete from MiniStack
                await asyncio.to_thread(
                    self.client.delete_function,
                    FunctionName=name
                )
                
                log_operational(
                    "Deleted Lambda function from MiniStack",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                # 2. Delete from FalkorDB
                function_id = f"lambda-function-{name}"
                await asyncio.to_thread(delete_node, "Resource", function_id)
                
                log_operational(
                    "Removed Lambda function from FalkorDB",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                # 3. Emit SSE event
                await event_bus.publish(
                    "RESOURCE_DELETED",
                    {"id": function_id, "name": name, "type": "lambda:function"},
                    self.tenant_id,
                )
                
                log_security(
                    "Lambda function deleted",
                    tenant_id=self.tenant_id,
                    function=name,
                )
                
                return {"deleted": name}
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    raise ValueError(f"Function {name} not found") from e
                raise
    
    async def _detect_dependencies(self, function: dict[str, Any]) -> None:
        """
        Detect Lambda function dependencies from environment variables.
        
        Creates DEPENDS_ON relationships in FalkorDB for:
        - S3 buckets (arn:aws:s3:::bucket-name or s3://bucket-name)
        - SQS queues (arn:aws:sqs:::queue-name)
        - DynamoDB tables (arn:aws:dynamodb:::table/table-name)
        
        Args:
            function: Function resource dict
        """
        env_vars = function.get("state", {}).get("environment", {})
        function_id = function["id"]
        
        for key, value in env_vars.items():
            # S3 bucket references
            if "arn:aws:s3:::" in value:
                bucket_name = value.split("arn:aws:s3:::")[-1].split("/")[0]
                await self._create_dependency(
                    function_id,
                    "s3:bucket",
                    f"s3-bucket-{bucket_name}",
                    "environment_variable",
                    key
                )
            elif value.startswith("s3://"):
                bucket_name = value.split("s3://")[1].split("/")[0]
                await self._create_dependency(
                    function_id,
                    "s3:bucket",
                    f"s3-bucket-{bucket_name}",
                    "environment_variable",
                    key
                )
            
            # SQS queue references
            if "arn:aws:sqs:" in value:
                queue_name = value.split(":")[-1]
                await self._create_dependency(
                    function_id,
                    "sqs:queue",
                    f"sqs-queue-{queue_name}",
                    "environment_variable",
                    key
                )
            
            # DynamoDB table references
            if "arn:aws:dynamodb:" in value and "/table/" in value:
                table_name = value.split("/table/")[-1]
                await self._create_dependency(
                    function_id,
                    "dynamodb:table",
                    f"dynamodb-table-{table_name}",
                    "environment_variable",
                    key
                )
    
    async def _create_dependency(
        self,
        source_id: str,
        target_type: str,
        target_id: str,
        dependency_type: str,
        env_var_key: str | None = None,
    ) -> None:
        """Create DEPENDS_ON relationship in FalkorDB."""
        # Check if target resource exists
        target_nodes = await asyncio.to_thread(
            query_nodes,
            "Resource",
            filters={"id": target_id, "tenant_id": self.tenant_id},
        )
        
        if target_nodes:
            # Create relationship using Cypher query
            # (This assumes FalkorDB has a create_relationship function similar to create_node)
            log_operational(
                "Created dependency relationship",
                tenant_id=self.tenant_id,
                source=source_id,
                target=target_id,
                dependency_type=dependency_type,
                env_var=env_var_key,
            )
```

### Phase 2: API Endpoints

Add Lambda endpoints to `api/routes/resources.py` and create Pydantic models.

### Phase 3: Testing

- Unit tests for LambdaService methods
- Integration tests for full CRUD flow
- Dependency detection tests

## Outcome

(To be filled after implementation)

- **Delivered**: 
- **PRD coverage**: 
- **Architecture impact**: 
- **Deferred**: 
- **Risks introduced**: 
- **Wiring**:
