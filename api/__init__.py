"""
API client modules for Sprint Report Service.

This package provides production-ready clients for external APIs:
- ClaudeReportGenerator: Generate Sprint reports using Claude AI
- JiraClient: Interact with JIRA Agile REST API (if available)
- FathomClient: Interact with Fathom Video API (if available)

Example usage:
    from api import ClaudeReportGenerator

    # Initialize Claude client
    generator = ClaudeReportGenerator()

    # Generate Sprint report
    report = await generator.generate_sprint_report(
        sprint_guide=guide_content,
        jira_data=jira_data,
        meeting_notes=notes,
        sprint_metadata=metadata
    )
"""

from .claude_client import (
    ClaudeReportGenerator,
    ClaudeAPIError,
    ReportValidationError,
    generate_report
)

# Try to import JIRA and Fathom clients if they exist
try:
    from .jira_client import (
        JiraClient,
        JiraAPIError,
        JiraAuthenticationError,
        JiraPermissionError,
        JiraNotFoundError
    )
    _has_jira = True
except ImportError:
    _has_jira = False

try:
    from .fathom_client import (
        FathomClient,
        FathomAPIError,
        FathomAuthenticationError,
        FathomNotFoundError,
        FathomRateLimitError
    )
    _has_fathom = True
except ImportError:
    _has_fathom = False

# Build __all__ dynamically
__all__ = [
    # Claude API (always available)
    'ClaudeReportGenerator',
    'ClaudeAPIError',
    'ReportValidationError',
    'generate_report',
]

# Add JIRA exports if available
if _has_jira:
    __all__.extend([
        'JiraClient',
        'JiraAPIError',
        'JiraAuthenticationError',
        'JiraPermissionError',
        'JiraNotFoundError',
    ])

# Add Fathom exports if available
if _has_fathom:
    __all__.extend([
        'FathomClient',
        'FathomAPIError',
        'FathomAuthenticationError',
        'FathomNotFoundError',
        'FathomRateLimitError',
    ])

__version__ = '1.0.0'
