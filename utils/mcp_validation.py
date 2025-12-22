"""
MCP response validation utilities.

Provides validation functions for MCP JSON-RPC 2.0 responses and JIRA data.
Uses Pydantic models for type-safe validation with clear error messages.

Usage:
    from utils.mcp_validation import validate_mcp_response

    try:
        data = validate_mcp_response(mcp_response_dict)
    except JiraMCPError as e:
        # Handle validation error
        logger.error(f"MCP validation failed: {e}")
"""
import json
import logging
from typing import Any, Dict
from pydantic import ValidationError

from utils.exceptions import JiraMCPError
from utils.mcp_models import MCPResponse, SprintData, IssueData


logger = logging.getLogger(__name__)


def validate_mcp_response(response: Dict[str, Any]) -> Any:
    """Validate MCP JSON-RPC 2.0 response and extract data.

    Args:
        response: Parsed JSON response from MCP Docker container

    Returns:
        Parsed JSON data from response.result.content[0].text

    Raises:
        JiraMCPError: If response is invalid or contains an error

    Examples:
        >>> response = {
        ...     "jsonrpc": "2.0",
        ...     "id": 2,
        ...     "result": {"content": [{"text": '{"sprints": []}', "type": "text"}]}
        ... }
        >>> validate_mcp_response(response)
        {'sprints': []}

        >>> error_response = {
        ...     "jsonrpc": "2.0",
        ...     "id": 2,
        ...     "error": {"code": -32700, "message": "Parse error"}
        ... }
        >>> validate_mcp_response(error_response)
        Traceback (most recent call last):
        ...
        JiraMCPError: MCP tool error: Parse error
    """
    # Validate MCP response structure with Pydantic
    try:
        mcp_response = MCPResponse.model_validate(response)
    except ValidationError as e:
        # Format Pydantic error for user-friendly message
        error_details = "; ".join([
            f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
        ])
        raise JiraMCPError(f"Invalid MCP response structure: {error_details}")

    # Check for MCP error (tool failure)
    if mcp_response.error:
        raise JiraMCPError(
            f"MCP tool error [{mcp_response.error.code}]: {mcp_response.error.message}"
        )

    # Validate result exists (should always be present if no error)
    if not mcp_response.result:
        raise JiraMCPError("MCP response missing result field")

    # Validate content exists and is non-empty
    if not mcp_response.result.content:
        raise JiraMCPError("MCP response has empty content")

    # Parse JSON from text content
    text_content = mcp_response.result.content[0].text
    try:
        data = json.loads(text_content)
    except json.JSONDecodeError as e:
        # Log first 200 chars of invalid JSON for debugging
        logger.error(f"Invalid JSON in MCP response: {text_content[:200]}")
        raise JiraMCPError(f"Invalid JSON in MCP response text: {e}")

    return data


def validate_sprint_data(sprint_data: Dict[str, Any], strict: bool = False) -> bool:
    """Validate sprint data against SprintData schema.

    Args:
        sprint_data: Raw sprint data from MCP
        strict: If True, raise exception on validation failure.
                If False, log warning and return False (default)

    Returns:
        True if valid, False if invalid (when strict=False)

    Raises:
        ValidationError: If strict=True and data is invalid

    Examples:
        >>> valid_sprint = {
        ...     "id": 123,
        ...     "name": "Sprint 11",
        ...     "state": "active",
        ...     "start_date": "2024-12-01",
        ...     "end_date": "2024-12-14"
        ... }
        >>> validate_sprint_data(valid_sprint)
        True

        >>> invalid_sprint = {"id": 123}  # Missing required fields
        >>> validate_sprint_data(invalid_sprint)
        False
    """
    try:
        SprintData.model_validate(sprint_data)
        return True
    except ValidationError as e:
        if strict:
            raise
        else:
            # Log warning with field-level details
            error_details = "; ".join([
                f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
            ])
            logger.warning(f"Invalid sprint data: {error_details}")
            logger.debug(f"Sprint data: {sprint_data}")
            return False


def validate_issue_data(issue_data: Dict[str, Any], strict: bool = False) -> bool:
    """Validate issue data against IssueData schema.

    Args:
        issue_data: Raw issue data from MCP
        strict: If True, raise exception on validation failure.
                If False, log warning and return False (default)

    Returns:
        True if valid, False if invalid (when strict=False)

    Raises:
        ValidationError: If strict=True and data is invalid

    Examples:
        >>> valid_issue = {
        ...     "key": "PROJ-123",
        ...     "summary": "Fix login bug",
        ...     "status": {"name": "In Progress"},
        ...     "assignee": {"display_name": "John Doe"},
        ...     "issue_type": {"name": "Bug"},
        ...     "story_points": 3
        ... }
        >>> validate_issue_data(valid_issue)
        True

        >>> invalid_issue = {"key": "invalid-key"}  # Invalid key format
        >>> validate_issue_data(invalid_issue)
        False
    """
    try:
        IssueData.model_validate(issue_data)
        return True
    except ValidationError as e:
        if strict:
            raise
        else:
            # Log warning with field-level details
            error_details = "; ".join([
                f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
            ])
            logger.warning(f"Invalid issue data: {error_details}")
            logger.debug(f"Issue data: {issue_data}")
            return False
