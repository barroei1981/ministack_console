"""
Tenant ID extraction from MiniStack access keys.

Per AD-6: MiniStack uses 12-digit access keys as tenant identifiers.
"""

import logging

logger = logging.getLogger(__name__)


def extract_tenant_id(access_key: str) -> str:
    """
    Extract tenant ID from MiniStack 12-digit access key.

    Per AD-6, the access key IS the tenant ID for MiniStack.

    Args:
        access_key: MiniStack access key (must be 12 digits)

    Returns:
        str: Validated tenant ID (same as access key)

    Raises:
        ValueError: If access key is not exactly 12 numeric digits

    Example:
        >>> extract_tenant_id("123456789012")
        '123456789012'

        >>> extract_tenant_id("abc")
        ValueError: Invalid MiniStack access key: abc. Must be 12 digits.
    """
    if not access_key:
        raise ValueError("Access key cannot be empty")

    if len(access_key) != 12:
        raise ValueError(
            f"Invalid MiniStack access key: {access_key}. "
            f"Must be 12 digits (got {len(access_key)})"
        )

    if not access_key.isdigit():
        raise ValueError(
            f"Invalid MiniStack access key: {access_key}. Must be numeric"
        )

    logger.debug(f"Extracted tenant ID: {access_key}")
    return access_key
