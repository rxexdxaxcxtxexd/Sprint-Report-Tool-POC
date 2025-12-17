"""
Data validation utilities for JIRA MCP responses.

Provides type-safe validation and coercion for JIRA data fields.
"""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def validate_story_points(value: Any) -> Optional[float]:
    """Validate and convert story points to float.

    Args:
        value: Raw story points value from JIRA (any type)

    Returns:
        Float value or None if invalid/missing

    Examples:
        >>> validate_story_points("5")
        5.0
        >>> validate_story_points(3)
        3.0
        >>> validate_story_points(None)
        None
        >>> validate_story_points("N/A")
        None
    """
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        # Log warning but don't fail - graceful degradation
        logger.warning(f"Invalid story points value: {value!r}, treating as None")
        return None
