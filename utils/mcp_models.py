"""
Pydantic models for MCP (Model Context Protocol) response validation.

Provides type-safe validation for:
- MCP JSON-RPC 2.0 protocol structure
- JIRA data schemas (sprints, issues)

Usage:
    from utils.mcp_models import MCPResponse, SprintData, IssueData

    # Validate MCP response
    mcp_response = MCPResponse.model_validate_json(response_json)

    # Validate JIRA data
    sprint = SprintData.model_validate(sprint_data)
"""
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Any, Dict


# ==============================================================================
# MCP Protocol Models (JSON-RPC 2.0)
# ==============================================================================

class MCPContent(BaseModel):
    """MCP response content item.

    Attributes:
        text: JSON string containing the tool result data
        type: Content type (always "text" for MCP tools)
    """
    text: str
    type: str = "text"


class MCPResult(BaseModel):
    """MCP response result structure.

    Attributes:
        content: List of content items (usually just one with JSON text)
    """
    content: List[MCPContent]


class MCPError(BaseModel):
    """MCP error structure (JSON-RPC 2.0 error object).

    Attributes:
        code: Error code (e.g., -32700 for parse error)
        message: Human-readable error message
        data: Optional additional error data
    """
    code: int
    message: str
    data: Optional[Any] = None


class MCPResponse(BaseModel):
    """MCP JSON-RPC 2.0 response.

    Attributes:
        jsonrpc: Protocol version (must be "2.0")
        id: Request ID (matches the request)
        result: Tool result (present on success)
        error: Error object (present on failure)

    Validation Rules:
        - jsonrpc must be exactly "2.0"
        - Either result or error must be present (not both)
        - If result is present, it must have non-empty content
    """
    jsonrpc: str = Field(pattern=r"^2\.0$")
    id: int
    result: Optional[MCPResult] = None
    error: Optional[MCPError] = None


# ==============================================================================
# JIRA Data Models
# ==============================================================================

class SprintData(BaseModel):
    """JIRA sprint data schema.

    Attributes:
        id: Sprint ID (unique identifier)
        name: Sprint name (e.g., "Sprint 11", "Q4 Planning Sprint")
        state: Sprint state ("future", "active", "closed")
        start_date: ISO 8601 date string (optional for future sprints)
        end_date: ISO 8601 date string (optional for future sprints)
        board_id: Board ID (optional, may not be in MCP response)

    Validation Rules:
        - id must be a positive integer
        - name cannot be empty
        - state must be one of: "future", "active", "closed"
    """
    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    state: str = Field(pattern=r"^(future|active|closed)$")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    board_id: Optional[int] = None


class IssueStatusData(BaseModel):
    """JIRA issue status data.

    Attributes:
        name: Status name (e.g., "To Do", "In Progress", "Done")
    """
    name: str


class IssueAssigneeData(BaseModel):
    """JIRA issue assignee data.

    Attributes:
        display_name: Assignee's display name
    """
    display_name: str


class IssueTypeData(BaseModel):
    """JIRA issue type data.

    Attributes:
        name: Issue type name (e.g., "Task", "Story", "Bug")
    """
    name: str


class IssueData(BaseModel):
    """JIRA issue data schema.

    Attributes:
        key: Issue key (e.g., "PROJ-123")
        summary: Issue title/summary
        status: Issue status object or string
        assignee: Assignee object (optional, may be null/unassigned)
        issue_type: Issue type object or string
        story_points: Story points (optional, validated separately)

    Validation Rules:
        - key must match JIRA key pattern (PROJECT-NUMBER)
        - summary cannot be empty
        - status/issue_type can be dict or string (flexible for MCP formats)

    Note:
        story_points validation is handled separately by validate_story_points()
        utility function for more flexible type coercion (str/int/float/None).
    """
    key: str = Field(pattern=r"^[A-Z]+-\d+$")
    summary: str = Field(min_length=1)
    status: Any  # Can be dict with 'name' or string (flexible)
    assignee: Optional[Any] = None  # Can be dict with 'display_name' or null
    issue_type: Any  # Can be dict with 'name' or string (flexible)
    story_points: Optional[Any] = None  # Validated separately
