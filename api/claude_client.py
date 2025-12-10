"""
Claude API client for Sprint Report generation.

This module provides a production-quality client for generating Sprint reports
using Claude AI (Anthropic). Features:
- Async API calls for better performance
- Retry logic with exponential backoff
- Comprehensive error handling
- Report validation
- Structured logging

Example:
    >>> from api.claude_client import ClaudeReportGenerator
    >>> generator = ClaudeReportGenerator()
    >>> report = await generator.generate_sprint_report(
    ...     sprint_guide=guide_content,
    ...     jira_data=jira_data,
    ...     meeting_notes=notes,
    ...     sprint_metadata=metadata
    ... )
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

import anthropic
from anthropic import AsyncAnthropic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)


# Module logger
logger = logging.getLogger(__name__)


class ClaudeAPIError(Exception):
    """Raised when Claude API calls fail."""
    pass


class ReportValidationError(Exception):
    """Raised when generated report fails validation."""
    pass


# Required sections in a complete Sprint report
REQUIRED_REPORT_SECTIONS = [
    "Sprint Overview",
    "Completed Work",
    "In Progress",
    "Blockers and Risks",
    "Metrics",
    "Next Sprint Plan"
]


class ClaudeReportGenerator:
    """
    Claude API client for automated Sprint report generation.

    Uses Claude Opus 4.5 to generate comprehensive Sprint reports by combining:
    - Sprint Report Guide template (DOCX)
    - JIRA Sprint data (issues, progress, metrics)
    - Team meeting notes from Fathom
    - Sprint metadata (ID, dates, goals)

    Features:
    - Async API calls for performance
    - Automatic retry with exponential backoff
    - Report validation
    - Comprehensive logging

    Attributes:
        api_key: Anthropic API key
        model: Claude model name
        max_tokens: Maximum tokens in response
        temperature: Temperature for generation (0.0-1.0)
        client: AsyncAnthropic client instance

    Example:
        >>> generator = ClaudeReportGenerator(
        ...     model="claude-opus-4-5-20251101",
        ...     max_tokens=8192
        ... )
        >>> report = await generator.generate_sprint_report(...)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-5-20251101",
        max_tokens: int = 8192,
        temperature: float = 0.7,
        max_retries: int = 3
    ):
        """
        Initialize Claude API client.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use (default: claude-opus-4-5-20251101)
            max_tokens: Maximum tokens in response (default: 8192)
            temperature: Temperature for generation 0.0-1.0 (default: 0.7)
            max_retries: Maximum retry attempts for failed API calls (default: 3)

        Raises:
            ClaudeAPIError: If API key is not provided or invalid
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ClaudeAPIError(
                "ANTHROPIC_API_KEY not found. Set it in environment or pass to constructor."
            )

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries

        # Initialize async client
        self.client = AsyncAnthropic(api_key=self.api_key)

        logger.info(
            f"ClaudeReportGenerator initialized: "
            f"model={model}, max_tokens={max_tokens}, temp={temperature}"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(anthropic.RateLimitError),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def generate_sprint_report(
        self,
        sprint_guide: str,
        jira_data: Dict[str, Any],
        meeting_notes: List[Dict[str, str]],
        sprint_metadata: Dict[str, str],
        validate: bool = True
    ) -> str:
        """
        Generate Sprint report using Claude API.

        Combines Sprint Report Guide template with JIRA data and meeting notes
        to produce a comprehensive, professional Sprint report.

        Args:
            sprint_guide: Sprint Report Guide template content (from DOCX)
            jira_data: JIRA Sprint data including:
                - completed: List of completed issues
                - in_progress: List of in-progress issues
                - blocked: List of blocked issues
                - metrics: Sprint metrics (velocity, completion rate, etc.)
            meeting_notes: List of meeting notes, each with:
                - date: Meeting date
                - title: Meeting title
                - summary: Meeting summary/transcript
            sprint_metadata: Sprint information:
                - sprint_id: Sprint ID
                - sprint_name: Sprint name
                - start_date: Sprint start date
                - end_date: Sprint end date
                - goal: Sprint goal/objective
            validate: Whether to validate generated report (default: True)

        Returns:
            Markdown-formatted Sprint report

        Raises:
            ClaudeAPIError: If API call fails after retries
            ReportValidationError: If generated report fails validation
            ValueError: If required input data is missing

        Example:
            >>> report = await generator.generate_sprint_report(
            ...     sprint_guide=guide_content,
            ...     jira_data={
            ...         "completed": [...],
            ...         "in_progress": [...],
            ...         "metrics": {"velocity": 42, ...}
            ...     },
            ...     meeting_notes=[
            ...         {"date": "2025-12-01", "title": "Standup", "summary": "..."}
            ...     ],
            ...     sprint_metadata={
            ...         "sprint_id": "SPRINT-45",
            ...         "sprint_name": "Sprint 45",
            ...         "start_date": "2025-11-25",
            ...         "end_date": "2025-12-08",
            ...         "goal": "Complete authentication"
            ...     }
            ... )
        """
        # Validate inputs
        self._validate_inputs(sprint_guide, jira_data, meeting_notes, sprint_metadata)

        # Build prompts
        system_prompt = self._build_system_prompt(sprint_guide)
        user_prompt = self._build_user_prompt(
            sprint_metadata,
            jira_data,
            meeting_notes
        )

        logger.info(
            f"Generating Sprint report for {sprint_metadata.get('sprint_name', 'Unknown')}"
        )
        logger.debug(
            f"Prompt sizes - System: {len(system_prompt)} chars, "
            f"User: {len(user_prompt)} chars"
        )

        try:
            # Call Claude API
            start_time = datetime.now()

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"API call completed in {elapsed:.2f} seconds")

            # Extract report content
            report_content = response.content[0].text

            # Log usage statistics
            if hasattr(response, 'usage'):
                logger.info(
                    f"Token usage - Input: {response.usage.input_tokens}, "
                    f"Output: {response.usage.output_tokens}"
                )

            # Validate report if requested
            if validate:
                validation = self.validate_report(report_content)
                if not validation["valid"]:
                    error_msg = (
                        f"Generated report missing required sections: "
                        f"{validation['missing_sections']}"
                    )
                    logger.error(error_msg)
                    raise ReportValidationError(error_msg)

                logger.info("Report validation passed")

            logger.info(
                f"Successfully generated report ({len(report_content)} chars, "
                f"{validation.get('word_count', 0)} words)"
            )

            return report_content

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}", exc_info=True)
            raise ClaudeAPIError(f"API call failed: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error generating report: {e}", exc_info=True)
            raise ClaudeAPIError(f"Report generation failed: {e}") from e

    def validate_report(self, report_content: str) -> Dict[str, Any]:
        """
        Validate generated Sprint report for completeness.

        Checks that report contains all required sections and meets
        minimum quality standards.

        Args:
            report_content: Generated report markdown content

        Returns:
            Dictionary with validation results:
                - valid: True if report passes all checks
                - missing_sections: List of required sections not found
                - warnings: List of warning messages
                - word_count: Total word count
                - section_count: Number of sections found

        Example:
            >>> validation = generator.validate_report(report_content)
            >>> if not validation["valid"]:
            ...     print(f"Missing: {validation['missing_sections']}")
        """
        missing_sections = []
        found_sections = []
        warnings = []

        # Check for required sections
        content_lower = report_content.lower()

        for section in REQUIRED_REPORT_SECTIONS:
            # Look for section headers (markdown style or plain text)
            section_patterns = [
                f"# {section.lower()}",
                f"## {section.lower()}",
                f"### {section.lower()}",
                section.lower()
            ]

            found = any(pattern in content_lower for pattern in section_patterns)

            if found:
                found_sections.append(section)
            else:
                missing_sections.append(section)

        # Calculate statistics
        word_count = len(report_content.split())
        section_count = len(found_sections)

        # Generate warnings
        if word_count < 500:
            warnings.append(f"Report is very short ({word_count} words)")

        if word_count > 10000:
            warnings.append(f"Report is very long ({word_count} words)")

        # Check for common issues
        if "TODO" in report_content or "TBD" in report_content:
            warnings.append("Report contains TODO/TBD placeholders")

        if report_content.count("\n\n") < 5:
            warnings.append("Report may lack proper formatting (few paragraphs)")

        # Determine validity
        valid = len(missing_sections) == 0

        result = {
            "valid": valid,
            "missing_sections": missing_sections,
            "found_sections": found_sections,
            "warnings": warnings,
            "word_count": word_count,
            "section_count": section_count
        }

        if valid:
            logger.debug("Report validation passed")
        else:
            logger.warning(
                f"Report validation failed: missing {len(missing_sections)} sections"
            )

        return result

    def _validate_inputs(
        self,
        sprint_guide: str,
        jira_data: Dict[str, Any],
        meeting_notes: List[Dict[str, str]],
        sprint_metadata: Dict[str, str]
    ) -> None:
        """
        Validate input data for report generation.

        Args:
            sprint_guide: Sprint guide content
            jira_data: JIRA data
            meeting_notes: Meeting notes
            sprint_metadata: Sprint metadata

        Raises:
            ValueError: If any required data is missing or invalid
        """
        # Validate sprint_guide
        if not sprint_guide or not sprint_guide.strip():
            raise ValueError("sprint_guide is required and cannot be empty")

        if len(sprint_guide) < 100:
            logger.warning("sprint_guide is very short - may be incomplete")

        # Validate jira_data
        if not isinstance(jira_data, dict):
            raise ValueError("jira_data must be a dictionary")

        # Validate meeting_notes
        if not isinstance(meeting_notes, list):
            raise ValueError("meeting_notes must be a list")

        # Validate sprint_metadata
        required_metadata = ["sprint_id", "sprint_name", "start_date", "end_date"]
        for key in required_metadata:
            if key not in sprint_metadata:
                raise ValueError(f"sprint_metadata missing required key: {key}")

        logger.debug("Input validation passed")

    def _build_system_prompt(self, sprint_guide: str) -> str:
        """
        Build system prompt with Sprint Report Guide.

        Args:
            sprint_guide: Sprint Report Guide content

        Returns:
            System prompt string
        """
        return f"""You are an expert Sprint Report Generator for CSG Solutions.

Your task is to create a comprehensive, professional Sprint report following the exact structure and format specified in the Sprint Report Guide below.

# Sprint Report Guide (Your Template)

{sprint_guide}

# Your Mission

Generate a polished Sprint report that:

1. **Follows the EXACT structure** from the Sprint Report Guide above
2. **Incorporates JIRA Sprint data** - Use actual issue keys, status, metrics
3. **References team meeting notes** - Include key decisions and action items
4. **Maintains professional tone** - Executive-friendly, clear, concise
5. **Highlights achievements** - Celebrate completed work
6. **Identifies risks clearly** - Call out blockers and impediments
7. **Provides actionable next steps** - Clear plan for upcoming sprint
8. **Uses specific data** - Include actual numbers, percentages, issue counts
9. **Formats beautifully** - Clean Markdown with proper headings and lists

# Critical Guidelines

- **DO NOT invent information** - Use only data provided in JIRA and meeting notes
- **DO NOT skip sections** - Include all sections from the guide
- **DO format consistently** - Use Markdown headings (##), bullets, tables
- **DO be specific** - Use actual issue keys (e.g., BOPS-123), dates, names
- **DO be concise** - Executives value clarity over length

# Output Format

Return a complete Sprint report in Markdown format, ready to share with stakeholders."""

    def _build_user_prompt(
        self,
        sprint_metadata: Dict[str, str],
        jira_data: Dict[str, Any],
        meeting_notes: List[Dict[str, str]]
    ) -> str:
        """
        Build user prompt with Sprint data.

        Args:
            sprint_metadata: Sprint information
            jira_data: JIRA Sprint data
            meeting_notes: Team meeting notes

        Returns:
            User prompt string
        """
        # Format meeting notes
        formatted_notes = self._format_meeting_notes(meeting_notes)

        # Format JIRA data
        formatted_jira = self._format_jira_data(jira_data)

        return f"""Generate a Sprint Report for the following Sprint:

# Sprint Information

- **Sprint ID**: {sprint_metadata.get('sprint_id', 'N/A')}
- **Sprint Name**: {sprint_metadata.get('sprint_name', 'N/A')}
- **Date Range**: {sprint_metadata.get('start_date', 'N/A')} to {sprint_metadata.get('end_date', 'N/A')}
- **Sprint Goal**: {sprint_metadata.get('goal', 'N/A')}

# JIRA Sprint Data

{formatted_jira}

# Team Meeting Notes (from Fathom)

{formatted_notes}

---

Please generate the complete Sprint Report following the Sprint Report Guide structure provided in the system prompt. Include all sections and use the actual data provided above."""

    def _format_meeting_notes(
        self,
        meeting_notes: List[Dict[str, str]]
    ) -> str:
        """
        Format meeting notes for inclusion in prompt.

        Args:
            meeting_notes: List of meeting note dictionaries

        Returns:
            Formatted meeting notes string
        """
        if not meeting_notes:
            return "No meeting notes available for this Sprint."

        formatted = []

        for i, note in enumerate(meeting_notes, 1):
            date = note.get('date', 'Unknown date')
            title = note.get('title', 'Untitled meeting')
            summary = note.get('summary', 'No summary available')

            formatted.append(f"""## Meeting {i}: {title}
**Date**: {date}

{summary}
""")

        return "\n".join(formatted)

    def _format_jira_data(self, jira_data: Dict[str, Any]) -> str:
        """
        Format JIRA data for inclusion in prompt.

        Args:
            jira_data: JIRA Sprint data dictionary

        Returns:
            Formatted JIRA data string
        """
        if not jira_data:
            return "No JIRA data available."

        # Format as JSON for clarity
        try:
            formatted = json.dumps(jira_data, indent=2, default=str)
            return f"```json\n{formatted}\n```"
        except Exception as e:
            logger.warning(f"Error formatting JIRA data as JSON: {e}")
            return str(jira_data)

    async def generate_multiple_reports(
        self,
        report_configs: List[Dict[str, Any]],
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple Sprint reports concurrently.

        Useful for batch report generation across multiple sprints or boards.

        Args:
            report_configs: List of report configuration dictionaries, each with:
                - sprint_guide: str
                - jira_data: dict
                - meeting_notes: list
                - sprint_metadata: dict
            max_concurrent: Maximum concurrent API calls (default: 3)

        Returns:
            List of result dictionaries with:
                - success: bool
                - report: str (if successful)
                - error: str (if failed)
                - sprint_id: str

        Example:
            >>> configs = [
            ...     {"sprint_guide": guide, "jira_data": data1, ...},
            ...     {"sprint_guide": guide, "jira_data": data2, ...}
            ... ]
            >>> results = await generator.generate_multiple_reports(configs)
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_semaphore(config: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    report = await self.generate_sprint_report(**config)
                    return {
                        "success": True,
                        "report": report,
                        "sprint_id": config["sprint_metadata"]["sprint_id"]
                    }
                except Exception as e:
                    logger.error(
                        f"Failed to generate report for "
                        f"{config['sprint_metadata']['sprint_id']}: {e}"
                    )
                    return {
                        "success": False,
                        "error": str(e),
                        "sprint_id": config["sprint_metadata"]["sprint_id"]
                    }

        logger.info(f"Generating {len(report_configs)} reports (max {max_concurrent} concurrent)")

        results = await asyncio.gather(
            *[generate_with_semaphore(config) for config in report_configs],
            return_exceptions=True
        )

        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        logger.info(f"Batch generation complete: {successful}/{len(results)} successful")

        return results


# Convenience function for simple usage
async def generate_report(
    sprint_guide_path: str,
    jira_data: Dict[str, Any],
    meeting_notes: List[Dict[str, str]],
    sprint_metadata: Dict[str, str],
    api_key: Optional[str] = None,
    model: str = "claude-opus-4-5-20251101"
) -> str:
    """
    Convenience function to generate a Sprint report.

    Args:
        sprint_guide_path: Path to Sprint Report Guide DOCX file
        jira_data: JIRA Sprint data
        meeting_notes: Team meeting notes
        sprint_metadata: Sprint information
        api_key: Anthropic API key (optional)
        model: Claude model to use

    Returns:
        Generated Sprint report (Markdown)

    Example:
        >>> report = await generate_report(
        ...     sprint_guide_path="guide.docx",
        ...     jira_data={...},
        ...     meeting_notes=[...],
        ...     sprint_metadata={...}
        ... )
    """
    # Import here to avoid circular dependency
    from utils.docx_parser import parse_sprint_guide

    # Parse guide
    sprint_guide = parse_sprint_guide(sprint_guide_path)

    # Generate report
    generator = ClaudeReportGenerator(api_key=api_key, model=model)
    report = await generator.generate_sprint_report(
        sprint_guide=sprint_guide,
        jira_data=jira_data,
        meeting_notes=meeting_notes,
        sprint_metadata=sprint_metadata
    )

    return report


if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    async def test_client():
        """Test the Claude client with sample data."""
        # Sample data
        sample_guide = """
# Sprint Report Guide

## Sprint Overview
Provide a high-level summary of the Sprint.

## Completed Work
List all completed issues and their impact.

## In Progress
List ongoing work items.

## Blockers and Risks
Identify any blockers or risks.

## Metrics
Include Sprint metrics and KPIs.

## Next Sprint Plan
Outline plans for the next Sprint.
"""

        sample_jira = {
            "completed": [
                {"key": "BOPS-123", "summary": "Implement user authentication"},
                {"key": "BOPS-124", "summary": "Fix payment gateway bug"}
            ],
            "in_progress": [
                {"key": "BOPS-125", "summary": "Add admin dashboard"}
            ],
            "blocked": [],
            "metrics": {
                "velocity": 42,
                "completion_rate": 85,
                "total_issues": 10,
                "completed_issues": 8
            }
        }

        sample_notes = [
            {
                "date": "2025-12-01",
                "title": "Daily Standup",
                "summary": "Team discussed authentication implementation. No blockers."
            }
        ]

        sample_metadata = {
            "sprint_id": "SPRINT-45",
            "sprint_name": "Sprint 45 - Authentication",
            "start_date": "2025-11-25",
            "end_date": "2025-12-08",
            "goal": "Complete user authentication and authorization"
        }

        try:
            generator = ClaudeReportGenerator()
            print("Generating Sprint report...")

            report = await generator.generate_sprint_report(
                sprint_guide=sample_guide,
                jira_data=sample_jira,
                meeting_notes=sample_notes,
                sprint_metadata=sample_metadata
            )

            print("\n=== Generated Report ===\n")
            print(report)

            print("\n=== Validation ===\n")
            validation = generator.validate_report(report)
            print(f"Valid: {validation['valid']}")
            print(f"Word count: {validation['word_count']}")
            if validation['warnings']:
                print(f"Warnings: {validation['warnings']}")

        except Exception as e:
            print(f"Error: {e}")

    # Run test
    # asyncio.run(test_client())
    print("Claude API client loaded. Import and use in your application.")
    print("\nExample usage:")
    print("  from api.claude_client import ClaudeReportGenerator")
    print("  generator = ClaudeReportGenerator()")
    print("  report = await generator.generate_sprint_report(...)")
