"""
Pydantic models for REST API request/response validation.
"""

from typing import Any

from pydantic import BaseModel, Field


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
