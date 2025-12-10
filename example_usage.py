"""
Example usage of Sprint Report Service utilities.

This script demonstrates how to use the three core modules:
1. config_loader - Configuration management
2. docx_parser - DOCX file parsing
3. claude_client - Claude API for report generation

Run this script to test the utilities with your configuration.
"""

import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def main():
    """Main example demonstrating all three utilities."""

    print("\n" + "=" * 70)
    print("Sprint Report Service - Example Usage")
    print("=" * 70 + "\n")

    # ========================================================================
    # 1. Configuration Management
    # ========================================================================
    print("1. Testing Configuration Loader\n" + "-" * 70)

    try:
        from utils import ConfigLoader

        # Load configuration
        config = ConfigLoader("config.yaml")
        print("✓ Configuration loaded successfully")

        # Get configuration values
        board_id = config.get("jira.default_board_id")
        print(f"  Default JIRA board: {board_id}")

        guide_path = config.get("sprint_report.guide_path")
        print(f"  Sprint guide path: {guide_path}")

        # Validate configuration
        validation = config.validate()
        if validation["errors"]:
            print(f"\n  ⚠ Configuration Errors:")
            for error in validation["errors"]:
                print(f"    - {error}")
        else:
            print("  ✓ No configuration errors")

        if validation["warnings"]:
            print(f"\n  ⚠ Configuration Warnings:")
            for warning in validation["warnings"]:
                print(f"    - {warning}")

    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return

    print("\n")

    # ========================================================================
    # 2. DOCX Parsing
    # ========================================================================
    print("2. Testing DOCX Parser\n" + "-" * 70)

    try:
        from utils import parse_sprint_guide, extract_sections, validate_guide, get_document_stats

        guide_path = config.get("sprint_report.guide_path")

        if not guide_path or not Path(guide_path).exists():
            print(f"⚠ Sprint Report Guide not found at: {guide_path}")
            print("  Skipping DOCX parsing tests")
        else:
            # Get document statistics
            stats = get_document_stats(guide_path)
            print(f"✓ Document loaded: {Path(guide_path).name}")
            print(f"  Paragraphs: {stats['paragraph_count']}")
            print(f"  Tables: {stats['table_count']}")
            print(f"  Headings: {stats['heading_count']}")
            print(f"  Words: {stats['word_count']:,}")
            print(f"  Characters: {stats['character_count']:,}")

            # Extract sections
            sections = extract_sections(guide_path)
            print(f"\n  Sections found ({len(sections)}):")
            for section_name in sections.keys():
                print(f"    - {section_name}")

            # Validate guide
            validation = validate_guide(guide_path)
            print(f"\n  Validation:")
            print(f"    Valid: {validation['valid']}")
            if validation['missing_sections']:
                print(f"    Missing sections: {validation['missing_sections']}")
            if validation['warnings']:
                print(f"    Warnings: {len(validation['warnings'])}")

            # Parse full guide
            guide_content = parse_sprint_guide(guide_path)
            print(f"\n  ✓ Full guide parsed ({len(guide_content)} characters)")

    except Exception as e:
        print(f"✗ DOCX parsing error: {e}")
        logger.exception("DOCX parsing failed")

    print("\n")

    # ========================================================================
    # 3. Claude API Client
    # ========================================================================
    print("3. Testing Claude API Client\n" + "-" * 70)

    try:
        from api import ClaudeReportGenerator

        # Check if API key is configured
        api_key = config.get_env_var("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠ ANTHROPIC_API_KEY not configured")
            print("  Set it in your .env file to test report generation")
            print("  Skipping Claude API tests")
        else:
            print("✓ Claude API key found")

            # Initialize generator
            generator = ClaudeReportGenerator()
            print(f"  Model: {generator.model}")
            print(f"  Max tokens: {generator.max_tokens}")
            print(f"  Temperature: {generator.temperature}")

            # Test with sample data
            print("\n  Testing report generation with sample data...")

            sample_guide = """
# Sprint Report Guide

## Sprint Overview
Provide a high-level summary of the Sprint including goals and achievements.

## Completed Work
List all completed issues with their impact on the project.

## In Progress
Document work items currently in progress.

## Blockers and Risks
Identify any blockers, impediments, or risks to the Sprint.

## Metrics
Include Sprint metrics such as velocity, completion rate, and burndown.

## Next Sprint Plan
Outline the plan and goals for the upcoming Sprint.
"""

            sample_jira_data = {
                "completed": [
                    {
                        "key": "BOPS-123",
                        "summary": "Implement user authentication",
                        "points": 8
                    },
                    {
                        "key": "BOPS-124",
                        "summary": "Fix payment gateway integration",
                        "points": 5
                    }
                ],
                "in_progress": [
                    {
                        "key": "BOPS-125",
                        "summary": "Add admin dashboard",
                        "points": 13
                    }
                ],
                "blocked": [],
                "metrics": {
                    "velocity": 42,
                    "completion_rate": 85,
                    "total_issues": 10,
                    "completed_issues": 8,
                    "total_points": 50,
                    "completed_points": 42
                }
            }

            sample_meeting_notes = [
                {
                    "date": "2025-12-01",
                    "title": "Sprint Planning",
                    "summary": "Team discussed Sprint goals and committed to 50 story points. Focus on authentication and payment features."
                },
                {
                    "date": "2025-12-05",
                    "title": "Daily Standup",
                    "summary": "Authentication feature completed. Payment gateway fix in progress. No blockers reported."
                }
            ]

            sample_sprint_metadata = {
                "sprint_id": "SPRINT-45",
                "sprint_name": "Sprint 45 - Authentication & Payments",
                "start_date": "2025-11-25",
                "end_date": "2025-12-08",
                "goal": "Complete user authentication and fix payment gateway integration"
            }

            # Generate report (this will make an API call)
            try:
                report = await generator.generate_sprint_report(
                    sprint_guide=sample_guide,
                    jira_data=sample_jira_data,
                    meeting_notes=sample_meeting_notes,
                    sprint_metadata=sample_sprint_metadata,
                    validate=True
                )

                print(f"  ✓ Report generated successfully ({len(report)} characters)")

                # Validate report
                validation = generator.validate_report(report)
                print(f"\n  Report validation:")
                print(f"    Valid: {validation['valid']}")
                print(f"    Word count: {validation['word_count']}")
                print(f"    Sections found: {len(validation['found_sections'])}")

                if validation['warnings']:
                    print(f"    Warnings: {validation['warnings']}")

                # Save sample report
                output_path = Path("reports/sample_report.md")
                output_path.parent.mkdir(exist_ok=True)
                output_path.write_text(report, encoding="utf-8")
                print(f"\n  ✓ Sample report saved to: {output_path}")

                # Show preview
                print("\n  Report preview (first 500 characters):")
                print("  " + "-" * 68)
                preview = report[:500].replace("\n", "\n  ")
                print(f"  {preview}...")
                print("  " + "-" * 68)

            except Exception as e:
                print(f"  ✗ Report generation failed: {e}")
                logger.exception("Report generation failed")

    except Exception as e:
        print(f"✗ Claude API client error: {e}")
        logger.exception("Claude API client initialization failed")

    print("\n" + "=" * 70)
    print("Example Usage Complete")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
