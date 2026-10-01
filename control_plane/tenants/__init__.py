"""
Tenant management module.

Provides multi-tenant isolation and tenant-aware operations.
"""

from .detector import extract_tenant_id
from .isolation import (
    ensure_tenant_exists,
    validate_tenant_id,
    get_tenant_resources,
    create_project_with_ownership,
    list_tenants,
)

__all__ = [
    "extract_tenant_id",
    "ensure_tenant_exists",
    "validate_tenant_id",
    "get_tenant_resources",
    "create_project_with_ownership",
    "list_tenants",
]
