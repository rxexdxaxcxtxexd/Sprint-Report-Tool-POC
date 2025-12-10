"""
Report Generator Service

High-level orchestrator for generating sprint reports. Integrates with:
- JIRA API (sprint data and issues)
- Fathom API (meeting recordings)
- Claude API (report generation)
- PDF Generator (document creation)

Features:
- Synchronous report generation
- Asynchronous background job processing
- Comprehensive error handling
- Retry logic with exponential backoff
- Progress tracking and status updates

Dependencies:
- requests: HTTP API calls
- anthropic: Claude API client
- pdf_generator: PDF conversion
"""

import os
import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import wraps
import time

import requests
from anthropic import Anthropic, APIError, RateLimitError

from .pdf_generator import generate_pdf_from_markdown, render_report_template

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReportGeneratorError(Exception):
    """Base exception for report generator errors."""
    pass


class JiraAPIError(ReportGeneratorError):
    """Raised when JIRA API calls fail."""
    pass


class FathomAPIError(ReportGeneratorError):
    """Raised when Fathom API calls fail."""
    pass


class ClaudeAPIError(ReportGeneratorError):
    """Raised when Claude API calls fail."""
    pass


class ReportGenerationError(ReportGeneratorError):
    """Raised when overall report generation fails."""
    pass


# Retry decorator with exponential backoff
def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator to retry function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be exponentially increased)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, RateLimitError) as e:
                    retries += 1
                    if retries >= max_retries:
                        raise

                    delay = base_delay * (2 ** (retries - 1))
                    logger.warning(
                        f"Attempt {retries}/{max_retries} failed: {str(e)}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)

            return func(*args, **kwargs)
        return wrapper
    return decorator


class JiraClient:
    """Client for interacting with JIRA API."""

    def __init__(self, base_url: str, email: str, api_token: str):
        """
        Initialize JIRA client.

        Args:
            base_url: JIRA instance base URL (e.g., https://your-domain.atlassian.net)
            email: JIRA user email
            api_token: JIRA API token
        """
        self.base_url = base_url.rstrip('/')
        self.auth = (email, api_token)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    @retry_with_backoff(max_retries=3)
    def get_sprint_info(self, sprint_id: int) -> Dict[str, Any]:
        """
        Get sprint information from JIRA.

        Args:
            sprint_id: JIRA sprint ID

        Returns:
            Dict containing sprint data

        Raises:
            JiraAPIError: If API call fails
        """
        try:
            url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}"
            logger.info(f"Fetching sprint info: {sprint_id}")

            response = requests.get(url, auth=self.auth, headers=self.headers, timeout=30)
            response.raise_for_status()

            sprint_data = response.json()
            logger.info(f"Retrieved sprint: {sprint_data.get('name', 'Unknown')}")

            return sprint_data

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch sprint {sprint_id}: {str(e)}"
            logger.error(error_msg)
            raise JiraAPIError(error_msg)

    @retry_with_backoff(max_retries=3)
    def get_sprint_issues(self, sprint_id: int, board_id: int) -> List[Dict[str, Any]]:
        """
        Get all issues in a sprint.

        Args:
            sprint_id: JIRA sprint ID
            board_id: JIRA board ID

        Returns:
            List of issue dictionaries

        Raises:
            JiraAPIError: If API call fails
        """
        try:
            url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint/{sprint_id}/issue"
            logger.info(f"Fetching sprint issues: sprint={sprint_id}, board={board_id}")

            all_issues = []
            start_at = 0
            max_results = 100

            while True:
                params = {
                    'startAt': start_at,
                    'maxResults': max_results,
                    'fields': 'summary,status,assignee,priority,issuetype,created,updated,resolutiondate'
                }

                response = requests.get(
                    url,
                    auth=self.auth,
                    headers=self.headers,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()

                data = response.json()
                issues = data.get('issues', [])
                all_issues.extend(issues)

                logger.debug(f"Retrieved {len(issues)} issues (total: {len(all_issues)})")

                # Check if there are more issues
                total = data.get('total', 0)
                if start_at + len(issues) >= total:
                    break

                start_at += max_results

            logger.info(f"Retrieved {len(all_issues)} total issues")
            return all_issues

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch sprint issues: {str(e)}"
            logger.error(error_msg)
            raise JiraAPIError(error_msg)


class FathomClient:
    """Client for interacting with Fathom API."""

    def __init__(self, api_key: str):
        """
        Initialize Fathom client.

        Args:
            api_key: Fathom API key
        """
        self.api_key = api_key
        self.base_url = "https://api.fathom.video/v1"
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    @retry_with_backoff(max_retries=3)
    def get_meetings(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get meetings from Fathom within date range.

        Args:
            start_date: Filter meetings after this date
            end_date: Filter meetings before this date
            limit: Maximum number of meetings to return

        Returns:
            List of meeting dictionaries

        Raises:
            FathomAPIError: If API call fails
        """
        try:
            url = f"{self.base_url}/meetings"
            logger.info(f"Fetching Fathom meetings: {start_date} to {end_date}")

            params = {'limit': limit}
            if start_date:
                params['start_date'] = start_date.isoformat()
            if end_date:
                params['end_date'] = end_date.isoformat()

            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            meetings = response.json().get('meetings', [])
            logger.info(f"Retrieved {len(meetings)} meetings")

            return meetings

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch Fathom meetings: {str(e)}"
            logger.error(error_msg)
            raise FathomAPIError(error_msg)


class ReportGenerator:
    """High-level orchestrator for sprint report generation."""

    def __init__(
        self,
        jira_client: JiraClient,
        fathom_client: Optional[FathomClient] = None,
        claude_api_key: Optional[str] = None,
        guide_path: Optional[str] = None
    ):
        """
        Initialize report generator.

        Args:
            jira_client: Initialized JIRA client
            fathom_client: Optional Fathom client
            claude_api_key: Claude API key
            guide_path: Path to sprint report guide template
        """
        self.jira = jira_client
        self.fathom = fathom_client
        self.claude = Anthropic(api_key=claude_api_key) if claude_api_key else None
        self.guide_path = guide_path or self._get_default_guide_path()

    def _get_default_guide_path(self) -> Path:
        """Get default path to sprint report guide."""
        services_dir = Path(__file__).parent
        guide_path = services_dir.parent / 'guides' / 'sprint_report_guide.md'
        return guide_path

    def _load_sprint_guide(self) -> str:
        """
        Load sprint report guide template.

        Returns:
            Guide content as string

        Raises:
            FileNotFoundError: If guide file doesn't exist
        """
        guide_path = Path(self.guide_path)

        if not guide_path.exists():
            logger.warning(f"Sprint guide not found: {guide_path}")
            return self._get_default_guide()

        try:
            content = guide_path.read_text(encoding='utf-8')
            logger.info(f"Loaded sprint guide: {guide_path}")
            return content

        except Exception as e:
            logger.error(f"Failed to read sprint guide: {str(e)}")
            return self._get_default_guide()

    def _get_default_guide(self) -> str:
        """Get default sprint report guide if file doesn't exist."""
        return """
You are generating a comprehensive sprint report. Please include:

1. **Sprint Overview**: Summary of sprint goals and outcomes
2. **Key Achievements**: Major accomplishments and completed work
3. **Metrics**: Story points, velocity, completion rates
4. **Team Performance**: Highlights and areas for improvement
5. **Blockers & Challenges**: Issues encountered and resolutions
6. **Action Items**: Next steps and follow-ups
7. **Meeting Highlights**: Key decisions and discussions

Format the report professionally with clear sections, tables for metrics,
and bullet points for readability.
"""

    @retry_with_backoff(max_retries=3)
    def _generate_report_with_claude(
        self,
        sprint_data: Dict[str, Any],
        issues: List[Dict[str, Any]],
        meetings: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate report using Claude API.

        Args:
            sprint_data: Sprint information from JIRA
            issues: List of sprint issues
            meetings: Optional list of Fathom meetings

        Returns:
            Generated report as Markdown string

        Raises:
            ClaudeAPIError: If Claude API call fails
        """
        if not self.claude:
            raise ClaudeAPIError("Claude API client not initialized")

        try:
            # Load guide
            guide = self._load_sprint_guide()

            # Prepare context
            context = {
                'sprint': sprint_data,
                'issues': issues,
                'meetings': meetings or []
            }

            # Build prompt
            prompt = f"""
{guide}

## Sprint Data

{json.dumps(context, indent=2, default=str)}

Please generate a comprehensive sprint report based on the above data.
Format the output as professional Markdown suitable for PDF generation.
"""

            logger.info("Calling Claude API to generate report...")

            # Call Claude API
            message = self.claude.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract report content
            report_content = message.content[0].text
            logger.info(f"Generated report: {len(report_content)} characters")

            return report_content

        except APIError as e:
            error_msg = f"Claude API error: {str(e)}"
            logger.error(error_msg)
            raise ClaudeAPIError(error_msg)

        except Exception as e:
            error_msg = f"Failed to generate report with Claude: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ClaudeAPIError(error_msg)

    def generate_report(
        self,
        sprint_id: int,
        board_id: int = 38,
        save_pdf: bool = True,
        save_html: bool = True
    ) -> Dict[str, Any]:
        """
        Generate complete sprint report.

        This is the main entry point for synchronous report generation.

        Args:
            sprint_id: JIRA sprint ID
            board_id: JIRA board ID
            save_pdf: If True, generate PDF file
            save_html: If True, save HTML file

        Returns:
            Dict containing:
                - report_content: Markdown report text
                - pdf_path: Path to PDF (if save_pdf=True)
                - html_path: Path to HTML (if save_html=True)
                - metadata: Sprint metadata

        Raises:
            ReportGenerationError: If report generation fails
        """
        try:
            logger.info(f"Starting report generation: sprint={sprint_id}, board={board_id}")

            # Step 1: Fetch JIRA data
            logger.info("Step 1/4: Fetching JIRA sprint data...")
            sprint_data = self.jira.get_sprint_info(sprint_id)
            issues = self.jira.get_sprint_issues(sprint_id, board_id)

            # Step 2: Fetch Fathom meetings (optional)
            meetings = []
            if self.fathom:
                try:
                    logger.info("Step 2/4: Fetching Fathom meetings...")
                    start_date = datetime.fromisoformat(sprint_data.get('startDate', '').replace('Z', '+00:00'))
                    end_date = datetime.fromisoformat(sprint_data.get('endDate', '').replace('Z', '+00:00'))
                    meetings = self.fathom.get_meetings(start_date, end_date)
                except Exception as e:
                    logger.warning(f"Failed to fetch Fathom meetings: {str(e)}")
            else:
                logger.info("Step 2/4: Skipping Fathom (not configured)")

            # Step 3: Generate report with Claude
            logger.info("Step 3/4: Generating report with Claude API...")
            report_content = self._generate_report_with_claude(sprint_data, issues, meetings)

            # Step 4: Generate PDF/HTML
            result = {
                'report_content': report_content,
                'metadata': {
                    'sprint_id': str(sprint_id),
                    'sprint_name': sprint_data.get('name', 'Unknown Sprint'),
                    'start_date': sprint_data.get('startDate', 'N/A')[:10],
                    'end_date': sprint_data.get('endDate', 'N/A')[:10],
                    'state': sprint_data.get('state', 'Unknown'),
                    'board_id': str(board_id),
                    'issue_count': len(issues),
                    'meeting_count': len(meetings)
                }
            }

            if save_pdf or save_html:
                logger.info("Step 4/4: Generating PDF/HTML files...")

                # Get output directory
                from .pdf_generator import get_output_dir
                output_dir = get_output_dir('pdfs')

                # Generate filename
                safe_name = sprint_data.get('name', 'sprint_report').replace(' ', '_').replace('/', '_')
                filename = f"{safe_name}_{sprint_id}.pdf"
                output_path = output_dir / filename

                # Generate files
                files = generate_pdf_from_markdown(
                    markdown_content=report_content,
                    output_path=output_path,
                    metadata=result['metadata'],
                    save_html=save_html
                )

                result.update(files)
            else:
                logger.info("Step 4/4: Skipping PDF/HTML generation")

            logger.info("Report generation completed successfully!")
            return result

        except (JiraAPIError, FathomAPIError, ClaudeAPIError) as e:
            logger.error(f"Report generation failed: {str(e)}")
            raise ReportGenerationError(str(e))

        except Exception as e:
            error_msg = f"Unexpected error during report generation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ReportGenerationError(error_msg)


async def process_sprint_report_async(
    job_id: str,
    sprint_id: int,
    board_id: int = 38,
    status_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Process sprint report generation asynchronously.

    This function can be used for background job processing with status updates.

    Args:
        job_id: Unique job identifier
        sprint_id: JIRA sprint ID
        board_id: JIRA board ID
        status_callback: Optional callback function for status updates

    Returns:
        Dict containing report results

    Raises:
        ReportGenerationError: If generation fails
    """
    def update_status(status: str, progress: int = 0):
        """Update job status."""
        if status_callback:
            status_callback(job_id, status, progress)
        logger.info(f"Job {job_id}: {status} ({progress}%)")

    try:
        update_status("Initializing", 0)

        # Initialize clients from environment
        jira_client = JiraClient(
            base_url=os.getenv('JIRA_BASE_URL'),
            email=os.getenv('JIRA_EMAIL'),
            api_token=os.getenv('JIRA_API_TOKEN')
        )

        fathom_client = None
        if os.getenv('FATHOM_API_KEY'):
            fathom_client = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))

        generator = ReportGenerator(
            jira_client=jira_client,
            fathom_client=fathom_client,
            claude_api_key=os.getenv('ANTHROPIC_API_KEY')
        )

        update_status("Fetching sprint data", 20)

        # Run synchronous generation in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            generator.generate_report,
            sprint_id,
            board_id
        )

        update_status("Completed", 100)

        return result

    except Exception as e:
        update_status(f"Failed: {str(e)}", -1)
        raise


# Main entry point for CLI testing
if __name__ == '__main__':
    """Test report generation when run directly."""
    import sys
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Get sprint ID from command line
    sprint_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    board_id = int(sys.argv[2]) if len(sys.argv) > 2 else 38

    if not sprint_id:
        print("Usage: python report_generator.py <sprint_id> [board_id]")
        print("Example: python report_generator.py 123 38")
        sys.exit(1)

    try:
        # Initialize clients
        jira = JiraClient(
            base_url=os.getenv('JIRA_BASE_URL'),
            email=os.getenv('JIRA_EMAIL'),
            api_token=os.getenv('JIRA_API_TOKEN')
        )

        fathom = None
        if os.getenv('FATHOM_API_KEY'):
            fathom = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))

        generator = ReportGenerator(
            jira_client=jira,
            fathom_client=fathom,
            claude_api_key=os.getenv('ANTHROPIC_API_KEY')
        )

        # Generate report
        print(f"\nGenerating sprint report for Sprint {sprint_id}...\n")
        result = generator.generate_report(sprint_id, board_id)

        print("\n" + "="*60)
        print("REPORT GENERATION - SUCCESS")
        print("="*60)
        print(f"\nSprint: {result['metadata']['sprint_name']}")
        print(f"Period: {result['metadata']['start_date']} to {result['metadata']['end_date']}")
        print(f"Issues: {result['metadata']['issue_count']}")
        print(f"Meetings: {result['metadata']['meeting_count']}")

        if 'pdf_path' in result:
            print(f"\nPDF: {result['pdf_path']}")
        if 'html_path' in result:
            print(f"HTML: {result['html_path']}")

        print("\n" + "="*60 + "\n")

    except Exception as e:
        print("\n" + "="*60)
        print("REPORT GENERATION - FAILED")
        print("="*60)
        print(f"\nError: {str(e)}")
        print("\nCheck logs for details.")
        print("="*60 + "\n")
        logger.error("Report generation failed", exc_info=True)
        sys.exit(1)
