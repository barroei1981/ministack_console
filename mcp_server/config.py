"""
MCP Server configuration.
"""

import os
from dataclasses import dataclass


@dataclass
class MCPConfig:
    """MCP Server configuration."""

    # Server settings
    port: int = int(os.getenv("MCP_SERVER_PORT", "3100"))
    api_base_url: str = os.getenv("MCP_API_BASE_URL", "http://localhost:8000")
    log_level: str = os.getenv("MCP_LOG_LEVEL", "INFO")

    # Rate limiting
    rate_limit_reads: int = int(os.getenv("MCP_RATE_LIMIT_READS", "1000"))
    rate_limit_writes: int = int(os.getenv("MCP_RATE_LIMIT_WRITES", "100"))

    # Authentication
    require_api_key: bool = os.getenv("MCP_REQUIRE_API_KEY", "true").lower() == "true"

    # Development mode (disable auth for testing)
    dev_mode: bool = os.getenv("MCP_DEV_MODE", "false").lower() == "true"


# Global config instance
config = MCPConfig()
