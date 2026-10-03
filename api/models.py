"""
Pydantic models for REST API request/response validation.
"""

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class HealthServiceStatus(BaseModel):
    """Health status for a single service."""

    connected: bool = Field(..., description="Whether service is connected and healthy")
    instance_id: str | None = Field(None, description="Service instance ID")
    error: str | None = Field(None, description="Error message if not healthy")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall status: 'healthy' or 'unhealthy'")
    ministack: HealthServiceStatus = Field(..., description="MiniStack connection status")
    falkordb: HealthServiceStatus = Field(..., description="FalkorDB connection status")


class TenantResponse(BaseModel):
    """Tenant summary response."""

    id: str = Field(..., description="12-digit tenant ID (MiniStack access key)")
    name: str = Field(..., description="Tenant display name")
    resource_count: int = Field(..., description="Total resources owned by tenant")
    created_at: str = Field(..., description="Tenant creation timestamp (ISO 8601)")


class ResourceSummary(BaseModel):
    """Resource summary for list endpoints."""

    id: str = Field(..., description="Resource ID (typically ARN)")
    type: str = Field(..., description="Resource type (e.g., 's3:bucket')")
    name: str = Field(..., description="Resource name")
    tenant_id: str = Field(..., description="Owning tenant ID")
    project: str | None = Field(None, description="Project tag value")
    tags: dict[str, str] = Field(default_factory=dict, description="Control-plane tags")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    state_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Key state fields (service-specific subset)",
    )


class PaginationMetadata(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(..., description="Current page number (1-indexed)")
    limit: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total items across all pages")
    next: str | None = Field(None, description="Next page URL")
    prev: str | None = Field(None, description="Previous page URL")


class PaginatedResourceResponse(BaseModel):
    """Paginated resource list response."""

    resources: list[ResourceSummary] = Field(..., description="Resource list for current page")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


class ProjectSummary(BaseModel):
    """Project summary with resource counts."""

    name: str = Field(..., description="Project name (from control-plane tags)")
    resource_count: int = Field(..., description="Total resources in project")
    tenant_id: str = Field(..., description="Owning tenant ID")
    description: str | None = Field(None, description="Project description")
    created_at: str | None = Field(None, description="Project creation timestamp")


class ProjectListResponse(BaseModel):
    """Project list response."""

    projects: list[ProjectSummary] = Field(..., description="Project list")
    tenant_id: str = Field(..., description="Tenant ID context")


class CreateProjectRequest(BaseModel):
    """Create project request."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str | None = Field(None, max_length=1000, description="Project description")
    tenant_id: str = Field(..., min_length=12, max_length=12, description="Owning tenant ID")


class ProjectDetailResponse(BaseModel):
    """Project detail response with resource breakdown."""

    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Project description")
    tenant_id: str = Field(..., description="Owning tenant ID")
    created_at: str | None = Field(None, description="Project creation timestamp")
    resource_count: int = Field(..., description="Total resources in project")
    resource_counts_by_service: dict[str, int] = Field(
        ..., description="Resource counts grouped by service type"
    )


class BulkDeleteResponse(BaseModel):
    """Bulk delete operation response."""

    deleted_count: int = Field(..., description="Number of resources deleted")
    project_name: str = Field(..., description="Project name")
    tenant_id: str = Field(..., description="Tenant ID")


class DependencyResponse(BaseModel):
    """Resource dependency relationship."""

    from_node_id: str = Field(..., description="Source resource ID")
    to_node_id: str = Field(..., description="Target resource ID")
    rel_type: str = Field(..., description="Relationship type (e.g., 'DEPENDS_ON')")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Relationship metadata (e.g., dependency_type)",
    )


class DependencyListResponse(BaseModel):
    """Dependency list response."""

    dependencies: list[DependencyResponse] = Field(..., description="Dependency relationships")
    resource_id: str = Field(..., description="Queried resource ID")


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Additional error details")


# S3 Bucket naming validation pattern
BUCKET_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$")


def validate_bucket_name(name: str) -> None:
    """
    Validate S3 bucket name according to AWS rules.

    Args:
        name: Bucket name to validate

    Raises:
        ValueError: If bucket name violates S3 naming rules
    """
    if not (3 <= len(name) <= 63):
        raise ValueError("Bucket name must be 3-63 characters")

    if not name.islower():
        raise ValueError("Bucket name must be lowercase")

    if not all(c.isalnum() or c in ["-", "."] for c in name):
        raise ValueError(
            "Bucket name must contain only lowercase alphanumeric, hyphens, and periods"
        )

    if name.startswith("-") or name.endswith("-"):
        raise ValueError("Bucket name cannot start or end with hyphen")

    if ".." in name:
        raise ValueError("Bucket name cannot contain consecutive periods")

    # Check if IP address format
    if name.replace(".", "").isdigit() and name.count(".") == 3:
        raise ValueError("Bucket name cannot be formatted as IP address")

    if not BUCKET_NAME_PATTERN.match(name):
        raise ValueError(
            "Bucket name must start and end with alphanumeric character"
        )


class CreateBucketRequest(BaseModel):
    """Request model for creating an S3 bucket."""

    name: str = Field(..., description="Bucket name (3-63 chars, lowercase)")
    tenant_id: str = Field(
        ..., description="Tenant ID (12-digit MiniStack access key)"
    )
    project: str | None = Field(
        None, description="Control-plane project tag"
    )
    versioning: bool = Field(
        False, description="Enable versioning on bucket"
    )
    tags: dict[str, str] = Field(
        default_factory=dict, description="Control-plane tags"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate bucket name."""
        validate_bucket_name(v)
        return v

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """Validate tenant ID format."""
        if not re.match(r"^\d{12}$", v):
            raise ValueError("Tenant ID must be exactly 12 digits")
        return v


class BucketResponse(BaseModel):
    """Response model for S3 bucket details."""

    name: str = Field(..., description="Bucket name")
    tenant_id: str = Field(..., description="Owning tenant ID")
    project: str | None = Field(None, description="Control-plane project tag")
    arn: str = Field(..., description="Bucket ARN")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    versioning: str = Field(
        ..., description="Versioning status (Enabled, Suspended, or empty)"
    )
    tags: dict[str, str] = Field(
        default_factory=dict, description="Control-plane tags"
    )
    state: dict[str, Any] = Field(
        default_factory=dict,
        description="Bucket state (region, object_count, size_bytes)",
    )


class BucketListResponse(BaseModel):
    """Response model for listing S3 buckets."""

    buckets: list[BucketResponse] = Field(
        ..., description="List of buckets for tenant"
    )
    tenant_id: str = Field(..., description="Tenant ID context")
    total: int = Field(..., description="Total bucket count")


class UpdateVersioningRequest(BaseModel):
    """Request model for updating bucket versioning."""

    enabled: bool = Field(
        ..., description="Enable or disable versioning"
    )
    tenant_id: str = Field(..., description="Tenant ID (for validation)")


class DeleteBucketResponse(BaseModel):
    """Response model for deleting a bucket."""

    deleted: str = Field(..., description="Name of deleted bucket")
    objects_deleted: int = Field(
        0, description="Number of objects deleted (if force=true)"
    )


# Lambda Function naming validation
LAMBDA_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9-_]+$")


def validate_lambda_name(name: str) -> None:
    """
    Validate Lambda function name according to AWS rules.

    Args:
        name: Function name to validate

    Raises:
        ValueError: If function name violates Lambda naming rules
    """
    if not (1 <= len(name) <= 64):
        raise ValueError("Function name must be 1-64 characters")

    if not LAMBDA_NAME_PATTERN.match(name):
        raise ValueError(
            "Function name must contain only alphanumeric, hyphens, and underscores"
        )


class CreateFunctionRequest(BaseModel):
    """Request model for creating a Lambda function."""

    name: str = Field(..., description="Function name (1-64 chars)")
    runtime: str = Field(
        ..., description="Lambda runtime (e.g., python3.11, nodejs18.x)"
    )
    handler: str = Field(..., description="Function handler (e.g., index.handler)")
    code: str = Field(..., description="Base64-encoded ZIP file containing function code")
    tenant_id: str = Field(
        ..., description="Tenant ID (12-digit MiniStack access key)"
    )
    project: str | None = Field(None, description="Control-plane project tag")
    environment: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    memory: int = Field(128, description="Memory size in MB (128-10240)", ge=128, le=10240)
    timeout: int = Field(3, description="Timeout in seconds (1-900)", ge=1, le=900)
    tags: dict[str, str] = Field(
        default_factory=dict, description="Control-plane tags"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate function name."""
        validate_lambda_name(v)
        return v

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """Validate tenant ID format."""
        if not re.match(r"^\d{12}$", v):
            raise ValueError("Tenant ID must be exactly 12 digits")
        return v


class FunctionResponse(BaseModel):
    """Response model for Lambda function details."""

    name: str = Field(..., description="Function name")
    tenant_id: str = Field(..., description="Owning tenant ID")
    project: str | None = Field(None, description="Control-plane project tag")
    arn: str = Field(..., description="Function ARN")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    runtime: str = Field(..., description="Lambda runtime")
    handler: str = Field(..., description="Function handler")
    memory: int = Field(..., description="Memory size in MB")
    timeout: int = Field(..., description="Timeout in seconds")
    environment: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    last_modified: str = Field(..., description="Last modified timestamp")
    code_size: int = Field(..., description="Code size in bytes")
    tags: dict[str, str] = Field(
        default_factory=dict, description="Control-plane tags"
    )
    state: dict[str, Any] = Field(
        default_factory=dict,
        description="Function state (runtime, handler, memory, timeout, environment)",
    )


class FunctionListResponse(BaseModel):
    """Response model for listing Lambda functions."""

    functions: list[FunctionResponse] = Field(
        ..., description="List of functions for tenant"
    )
    tenant_id: str = Field(..., description="Tenant ID context")
    total: int = Field(..., description="Total function count")


class UpdateFunctionCodeRequest(BaseModel):
    """Request model for updating function code."""

    code: str = Field(..., description="Base64-encoded ZIP file containing new function code")
    tenant_id: str = Field(..., description="Tenant ID (for validation)")


class UpdateFunctionConfigurationRequest(BaseModel):
    """Request model for updating function configuration."""

    environment: dict[str, str] | None = Field(
        None, description="New environment variables"
    )
    memory: int | None = Field(
        None, description="New memory size in MB (128-10240)", ge=128, le=10240
    )
    timeout: int | None = Field(
        None, description="New timeout in seconds (1-900)", ge=1, le=900
    )
    tenant_id: str = Field(..., description="Tenant ID (for validation)")


class DeleteFunctionResponse(BaseModel):
    """Response model for deleting a function."""

    deleted: str = Field(..., description="Name of deleted function")


class InvokeFunctionRequest(BaseModel):
    """Request model for invoking a function."""

    payload: dict[str, Any] = Field(
        default_factory=dict, description="Test payload (JSON object)"
    )
    tenant_id: str = Field(..., description="Tenant ID (for validation)")


class InvokeFunctionResponse(BaseModel):
    """Response model for function invocation."""

    status_code: int = Field(..., description="HTTP status code")
    response: str = Field(..., description="Function response body")
    logs: str = Field(..., description="Execution logs")
    function_error: str | None = Field(None, description="Error type if failed")
    executed_version: str = Field(..., description="Executed function version")


# DynamoDB Table naming validation
DYNAMODB_TABLE_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")


def validate_dynamodb_table_name(name: str) -> None:
    """
    Validate DynamoDB table name according to AWS rules.

    Args:
        name: Table name to validate

    Raises:
        ValueError: If table name violates DynamoDB naming rules
    """
    if not (3 <= len(name) <= 255):
        raise ValueError("Table name must be 3-255 characters")

    if not DYNAMODB_TABLE_PATTERN.match(name):
        raise ValueError(
            "Table name must contain only alphanumeric, underscores, hyphens, and periods"
        )


class CreateTableRequest(BaseModel):
    """Request model for creating a DynamoDB table."""

    name: str = Field(..., description="Table name (3-255 chars)")
    key_schema: list[dict[str, str]] = Field(
        ..., description="Key schema (HASH and optionally RANGE keys)"
    )
    attribute_definitions: list[dict[str, str]] = Field(
        ..., description="Attribute definitions for key attributes"
    )
    billing_mode: str = Field(
        "PAY_PER_REQUEST", description="Billing mode (PAY_PER_REQUEST or PROVISIONED)"
    )
    provisioned_throughput: dict[str, int] | None = Field(
        None, description="Provisioned throughput (if PROVISIONED billing mode)"
    )
    tenant_id: str = Field(
        ..., description="Tenant ID (12-digit MiniStack access key)"
    )
    project: str | None = Field(None, description="Control-plane project tag")
    tags: dict[str, str] = Field(
        default_factory=dict, description="Control-plane tags"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate table name."""
        validate_dynamodb_table_name(v)
        return v

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """Validate tenant ID format."""
        if not re.match(r"^\d{12}$", v):
            raise ValueError("Tenant ID must be exactly 12 digits")
        return v


class TableResponse(BaseModel):
    """Response model for DynamoDB table details."""

    name: str = Field(..., description="Table name")
    tenant_id: str = Field(..., description="Owning tenant ID")
    project: str | None = Field(None, description="Control-plane project tag")
    arn: str = Field(..., description="Table ARN")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    key_schema: list[dict[str, str]] = Field(..., description="Key schema")
    attribute_definitions: list[dict[str, str]] = Field(
        ..., description="Attribute definitions"
    )
    billing_mode: str = Field(..., description="Billing mode")
    table_status: str = Field(..., description="Table status (ACTIVE, CREATING, etc.)")
    item_count: int = Field(0, description="Approximate item count")
    tags: dict[str, str] = Field(
        default_factory=dict, description="Control-plane tags"
    )
    state: dict[str, Any] = Field(
        default_factory=dict,
        description="Table state (key_schema, billing_mode, item_count)",
    )


class TableListResponse(BaseModel):
    """Response model for listing DynamoDB tables."""

    tables: list[TableResponse] = Field(..., description="List of tables for tenant")
    tenant_id: str = Field(..., description="Tenant ID context")
    total: int = Field(..., description="Total table count")


class ScanItemsRequest(BaseModel):
    """Request model for scanning table items."""

    tenant_id: str = Field(..., description="Tenant ID (for validation)")
    limit: int = Field(100, description="Max items to return", ge=1, le=1000)
    exclusive_start_key: dict[str, Any] | None = Field(
        None, description="Pagination token"
    )
    filter_expression: str | None = Field(None, description="Filter expression")
    projection_expression: str | None = Field(
        None, description="Projection expression"
    )


class ScanItemsResponse(BaseModel):
    """Response model for scanned items."""

    items: list[dict[str, Any]] = Field(..., description="Scanned items")
    count: int = Field(..., description="Number of items returned")
    last_evaluated_key: dict[str, Any] | None = Field(
        None, description="Pagination token for next page"
    )


class PutItemRequest(BaseModel):
    """Request model for putting an item."""

    tenant_id: str = Field(..., description="Tenant ID (for validation)")
    item: dict[str, Any] = Field(..., description="Item data (DynamoDB JSON format)")


class PutItemResponse(BaseModel):
    """Response model for put item operation."""

    success: bool = Field(..., description="Whether operation succeeded")


class DeleteTableResponse(BaseModel):
    """Response model for deleting a table."""

    deleted: str = Field(..., description="Name of deleted table")


class DeleteItemRequest(BaseModel):
    """Request model for deleting an item."""

    tenant_id: str = Field(..., description="Tenant ID (for validation)")
    key: dict[str, Any] = Field(..., description="Primary key of item to delete")


class DeleteItemResponse(BaseModel):
    """Response model for delete item operation."""

    success: bool = Field(..., description="Whether operation succeeded")
