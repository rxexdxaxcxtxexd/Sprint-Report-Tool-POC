"""
Custom exceptions for Sprint Report CLI.

Centralizes exception definitions to avoid circular imports.
"""


class JiraMCPError(Exception):
    """Exception raised for JIRA MCP communication errors."""
    pass
