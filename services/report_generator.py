"""
Report Generator - Simplified version for CLI tool.

Generates executive-level sprint reports using Claude AI, combining JIRA data
and Fathom transcripts according to the sprint report guide.
"""
from anthropic import Anthropic
from typing import List, Dict, Any
from pathlib import Path

from cli.jira_mcp import Sprint, Issue
from cli.transcript_filter import FilteredTranscript
from utils.config import Config


def generate_sprint_report(
    sprint: Sprint,
    issues: List[Issue],
    transcripts: List[FilteredTranscript],
    config: Config
) -> str:
    """Generate sprint report using Claude AI.

    Args:
        sprint: Sprint object with metadata
        issues: List of JIRA issues in sprint
        transcripts: List of selected Fathom transcripts
        config: Configuration object

    Returns:
        Report content in Markdown format

    Raises:
        Exception: If Claude API fails or guide file missing
    """
    # Load sprint report guide
    if not config.report.guide_path.exists():
        raise FileNotFoundError(f"Sprint guide not found: {config.report.guide_path}")

    with open(config.report.guide_path, 'r') as f:
        sprint_guide = f.read()

    # Build sprint data summary
    sprint_data = _build_sprint_data_summary(sprint, issues)

    # Build transcript context
    transcript_context = _build_transcript_context(transcripts)

    # Build Claude prompt
    prompt = _build_claude_prompt(
        sprint_guide=sprint_guide,
        sprint_data=sprint_data,
        transcript_context=transcript_context,
        team_name=config.report.team_name
    )

    # Call Claude API
    client = Anthropic(api_key=config.claude.api_key)

    response = client.messages.create(
        model=config.claude.model,
        max_tokens=config.claude.max_tokens,
        temperature=config.claude.temperature,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # Extract markdown report from response
    report_markdown = response.content[0].text

    return report_markdown


def _build_sprint_data_summary(sprint: Sprint, issues: List[Issue]) -> str:
    """Build summary of sprint data from JIRA.

    Args:
        sprint: Sprint object
        issues: List of issues

    Returns:
        Formatted string with sprint data
    """
    # Calculate metrics
    total_issues = len(issues)
    completed_issues = len([i for i in issues if i.status in ['Done', 'Closed', 'Resolved']])
    completion_rate = (completed_issues / total_issues * 100) if total_issues > 0 else 0

    # Story points (if available)
    total_points = sum(i.story_points for i in issues if i.story_points)
    completed_points = sum(
        i.story_points for i in issues
        if i.story_points and i.status in ['Done', 'Closed', 'Resolved']
    )

    # Group by type
    issues_by_type = {}
    for issue in issues:
        issue_type = issue.issue_type
        if issue_type not in issues_by_type:
            issues_by_type[issue_type] = []
        issues_by_type[issue_type].append(issue)

    # Build summary
    summary = f"""# Sprint Data Summary

**Sprint:** {sprint.name}
**State:** {sprint.state}
**Dates:** {sprint.start_date[:10] if sprint.start_date else 'N/A'} → {sprint.end_date[:10] if sprint.end_date else 'N/A'}

## Metrics
- **Total Issues:** {total_issues}
- **Completed Issues:** {completed_issues} ({completion_rate:.1f}%)
- **Total Story Points:** {total_points:.0f}
- **Completed Story Points:** {completed_points:.0f}

## Issues by Type
"""

    for issue_type, type_issues in issues_by_type.items():
        summary += f"\n### {issue_type} ({len(type_issues)})\n"
        for issue in type_issues:
            status_emoji = "✓" if issue.status in ['Done', 'Closed', 'Resolved'] else "○"
            points = f" ({issue.story_points:.0f}pts)" if issue.story_points else ""
            summary += f"- {status_emoji} **{issue.key}**: {issue.summary}{points}\n"

    return summary


def _build_transcript_context(transcripts: List[FilteredTranscript]) -> str:
    """Build context from selected Fathom transcripts.

    Args:
        transcripts: List of selected transcripts

    Returns:
        Formatted string with transcript summaries
    """
    if not transcripts:
        return "# Fathom Transcripts\n\nNo transcripts selected for this sprint."

    context = "# Fathom Transcripts\n\n"
    context += f"Selected {len(transcripts)} meeting(s) related to this sprint:\n\n"

    for idx, transcript in enumerate(transcripts, 1):
        context += f"## Meeting {idx}: {transcript.title}\n"
        context += f"**Date:** {transcript.date}\n"
        context += f"**Confidence:** {transcript.confidence}\n\n"

        # Note: Full transcript content would be included here if available
        # For MVP, we're just including meeting metadata
        # In production, you'd call fathom_client.get_meeting_transcript()

        context += f"_[Transcript content would be included in full implementation]_\n\n"

    context += "\n**Note:** Use these meetings as context for the sprint report, "
    context += "but focus on high-level executive summary rather than technical details.\n"

    return context


def _build_claude_prompt(
    sprint_guide: str,
    sprint_data: str,
    transcript_context: str,
    team_name: str
) -> str:
    """Build Claude prompt combining guide, data, and context.

    Args:
        sprint_guide: Sprint report format guide
        sprint_data: JIRA sprint data summary
        transcript_context: Fathom transcript context
        team_name: Team name for report

    Returns:
        Complete prompt for Claude
    """
    prompt = f"""You are an expert technical writer creating an executive-level sprint report for {team_name}.

# Your Task

Generate a comprehensive sprint report following the format guide below. The report should be:
- Written for executive/business stakeholders (not developers)
- High-level and focused on outcomes and business value
- Clear, concise, and well-structured
- Following the exact format specified in the guide

# Sprint Report Format Guide

{sprint_guide}

# JIRA Sprint Data

{sprint_data}

# Fathom Meeting Context

{transcript_context}

# Instructions

1. Read the sprint report format guide carefully
2. Analyze the JIRA data to understand what was accomplished
3. Use the Fathom meetings as additional context (but prioritize JIRA data)
4. Write a polished, executive-level report following the guide's structure
5. Use active voice, present tense, and business-focused language
6. Include specific JIRA issue references where appropriate (e.g., "→ BOPS-123")
7. Focus on business value and outcomes, not technical implementation details

Output the report in Markdown format, ready for PDF generation.
"""

    return prompt


if __name__ == "__main__":
    """Test report generation."""
    print("Report Generator - Test Mode")
    print("This module is meant to be imported, not run directly.")
    print("\nTo test, run: python cli/main.py")
