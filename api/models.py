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


class ProjectListResponse(BaseModel):
    """Project list response."""

    projects: list[ProjectSummary] = Field(..., description="Project list")
    tenant_id: str = Field(..., description="Tenant ID context")


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
