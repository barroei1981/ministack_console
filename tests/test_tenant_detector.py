"""
Unit tests for tenant ID extraction.

Tests extract_tenant_id() from control_plane.tenants.detector.
"""

import pytest

from control_plane.tenants.detector import extract_tenant_id


class TestExtractTenantId:
    """Test tenant ID extraction from MiniStack access keys."""

    def test_valid_12_digit_access_key(self):
        """Valid 12-digit numeric access key should be returned as-is."""
        access_key = "123456789012"
        result = extract_tenant_id(access_key)
        assert result == "123456789012"

    def test_different_valid_tenant_id(self):
        """Different valid tenant ID should work."""
        access_key = "999888777666"
        result = extract_tenant_id(access_key)
        assert result == "999888777666"

    def test_empty_access_key(self):
        """Empty access key should raise ValueError."""
        with pytest.raises(ValueError, match="Access key cannot be empty"):
            extract_tenant_id("")

    def test_none_access_key(self):
        """None access key should raise ValueError."""
        with pytest.raises(ValueError):
            extract_tenant_id(None)

    def test_too_short_access_key(self):
        """Access key with fewer than 12 digits should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            extract_tenant_id("123")

    def test_too_long_access_key(self):
        """Access key with more than 12 digits should raise ValueError."""
        with pytest.raises(ValueError, match="Must be 12 digits"):
            extract_tenant_id("1234567890123")

    def test_non_numeric_access_key(self):
        """Access key with non-numeric characters should raise ValueError."""
        with pytest.raises(ValueError, match="Must be numeric"):
            extract_tenant_id("12345678901a")

    def test_alphabetic_access_key(self):
        """Alphabetic access key should raise ValueError."""
        with pytest.raises(ValueError, match="Must be numeric"):
            extract_tenant_id("abcdefghijkl")

    def test_mixed_alphanumeric(self):
        """Mixed alphanumeric access key should raise ValueError."""
        with pytest.raises(ValueError, match="Must be numeric"):
            extract_tenant_id("123abc789012")

    def test_special_characters(self):
        """Access key with special characters should raise ValueError."""
        with pytest.raises(ValueError, match="Must be numeric"):
            extract_tenant_id("123456-78901")

    def test_whitespace(self):
        """Access key with whitespace should raise ValueError."""
        with pytest.raises(ValueError, match="Must be numeric"):
            extract_tenant_id("123456 78901")

    def test_leading_zeros(self):
        """Access key with leading zeros should be valid."""
        access_key = "000000000001"
        result = extract_tenant_id(access_key)
        assert result == "000000000001"

    def test_all_zeros(self):
        """Access key with all zeros should be valid."""
        access_key = "000000000000"
        result = extract_tenant_id(access_key)
        assert result == "000000000000"

    def test_all_nines(self):
        """Access key with all nines should be valid."""
        access_key = "999999999999"
        result = extract_tenant_id(access_key)
        assert result == "999999999999"
