"""
JIRA API Client for Sprint Report Service.

This module provides a production-ready client for interacting with JIRA's Agile REST API
to fetch sprint data, issues, and calculate sprint metrics.

Example usage:
    from api.jira_client import JiraClient

    # Initialize client
    client = JiraClient(
        base_url="https://your-domain.atlassian.net",
        email="your-email@company.com",
        api_token="your-api-token"
    )

    # Fetch sprint data
    sprint = client.get_sprint_by_id("123")
    issues = client.get_sprint_issues("123")
    metrics = client.get_sprint_metrics("123")

    print(f"Sprint: {sprint['name']}")
    print(f"Completion Rate: {metrics['completion_rate']}%")
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth


# Configure module logger
logger = logging.getLogger(__name__)


class JiraAPIError(Exception):
    """Base exception for JIRA API errors."""
    pass


class JiraAuthenticationError(JiraAPIError):
    """Raised when authentication fails."""
    pass


class JiraPermissionError(JiraAPIError):
    """Raised when user lacks permissions."""
    pass


class JiraNotFoundError(JiraAPIError):
    """Raised when resource is not found."""
    pass


class JiraClient:
    """
    Client for interacting with JIRA Agile REST API.

    This client provides methods to fetch sprint data, issues, and calculate
    sprint metrics. All API calls use HTTP Basic Authentication with email
    and API token.

    Attributes:
        base_url (str): JIRA instance base URL (e.g., https://your-domain.atlassian.net)
        email (str): JIRA account email
        api_token (str): JIRA API token
        session (requests.Session): Reusable HTTP session
    """

    def __init__(self, base_url: str, email: str, api_token: str):
        """
        Initialize JIRA client.

        Args:
            base_url: JIRA instance base URL (e.g., https://your-domain.atlassian.net)
            email: JIRA account email address
            api_token: JIRA API token (generate from account settings)

        Raises:
            ValueError: If any required parameter is empty or invalid
        """
        if not base_url or not base_url.startswith(('http://', 'https://')):
            raise ValueError("base_url must be a valid HTTP(S) URL")
        if not email or '@' not in email:
            raise ValueError("email must be a valid email address")
        if not api_token:
            raise ValueError("api_token cannot be empty")

        self.base_url = base_url.rstrip('/')
        self.email = email
        self.api_token = api_token

        # Create reusable session with authentication
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(email, api_token)
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        logger.info(f"Initialized JIRA client for {self.base_url}")

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make GET request to JIRA API.

        Args:
            endpoint: API endpoint (e.g., /rest/agile/1.0/sprint/123)
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            JiraAuthenticationError: Invalid credentials (401)
            JiraPermissionError: Insufficient permissions (403)
            JiraNotFoundError: Resource not found (404)
            JiraAPIError: Other API errors (500, network issues)
        """
        url = f"{self.base_url}{endpoint}"

        try:
            logger.debug(f"GET {url} with params={params}")
            response = self.session.get(url, params=params, timeout=30)

            # Handle specific error cases
            if response.status_code == 401:
                raise JiraAuthenticationError(
                    "Authentication failed. Check your email and API token. "
                    "Generate a new token at: https://id.atlassian.com/manage-profile/security/api-tokens"
                )
            elif response.status_code == 403:
                raise JiraPermissionError(
                    f"Permission denied. You don't have access to: {endpoint}. "
                    "Contact your JIRA administrator for required permissions."
                )
            elif response.status_code == 404:
                raise JiraNotFoundError(
                    f"Resource not found: {endpoint}. "
                    "Check that the sprint/board ID exists and you have access."
                )
            elif response.status_code >= 500:
                raise JiraAPIError(
                    f"JIRA server error ({response.status_code}). "
                    "The JIRA service may be temporarily unavailable. Try again later."
                )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise JiraAPIError(
                f"Request timed out after 30 seconds. Check your network connection."
            )
        except requests.exceptions.ConnectionError as e:
            raise JiraAPIError(
                f"Connection error: {str(e)}. Check your network and JIRA URL."
            )
        except requests.exceptions.RequestException as e:
            if not isinstance(e, (JiraAuthenticationError, JiraPermissionError, JiraNotFoundError)):
                raise JiraAPIError(f"Request failed: {str(e)}")
            raise

    def get_sprint_by_id(self, sprint_id: str) -> Dict[str, Any]:
        """
        Fetch sprint details by ID.

        Args:
            sprint_id: Sprint ID (numeric string)

        Returns:
            Dictionary containing sprint data:
                - id: Sprint ID
                - name: Sprint name
                - state: Sprint state (active, closed, future)
                - startDate: Sprint start date (ISO 8601)
                - endDate: Sprint end date (ISO 8601)
                - completeDate: Sprint completion date (ISO 8601, if closed)
                - goal: Sprint goal description
                - originBoardId: Board ID sprint belongs to

        Raises:
            ValueError: Invalid sprint_id
            JiraNotFoundError: Sprint does not exist
            JiraAPIError: API request failed

        Example:
            >>> sprint = client.get_sprint_by_id("123")
            >>> print(f"{sprint['name']}: {sprint['state']}")
            Sprint 5: active
        """
        if not sprint_id or not str(sprint_id).isdigit():
            raise ValueError("sprint_id must be a numeric string")

        endpoint = f"/rest/agile/1.0/sprint/{sprint_id}"
        logger.info(f"Fetching sprint {sprint_id}")

        sprint_data = self._get(endpoint)
        logger.info(f"Retrieved sprint: {sprint_data.get('name', 'Unknown')}")

        return sprint_data

    def get_sprint_issues(self, sprint_id: str, fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch all issues in a sprint with pagination support.

        JIRA returns a maximum of 50 issues per request. This method automatically
        handles pagination to retrieve all issues.

        Args:
            sprint_id: Sprint ID (numeric string)
            fields: Optional list of field names to retrieve. Defaults to common fields.

        Returns:
            List of issue dictionaries, each containing:
                - key: Issue key (e.g., "PROJ-123")
                - id: Issue ID
                - fields: Dictionary of field values including:
                    - summary: Issue title
                    - status: Current status
                    - assignee: Assigned user
                    - customfield_*: Story points (field name varies by instance)
                    - issuetype: Issue type (Story, Bug, Task, etc.)

        Raises:
            ValueError: Invalid sprint_id
            JiraNotFoundError: Sprint does not exist
            JiraAPIError: API request failed

        Example:
            >>> issues = client.get_sprint_issues("123")
            >>> completed = [i for i in issues if i['fields']['status']['name'] == 'Done']
            >>> print(f"Completed: {len(completed)}/{len(issues)}")
            Completed: 8/12
        """
        if not sprint_id or not str(sprint_id).isdigit():
            raise ValueError("sprint_id must be a numeric string")

        # Default fields to retrieve
        if fields is None:
            fields = [
                'summary', 'status', 'assignee', 'issuetype',
                'priority', 'created', 'updated', 'resolutiondate',
                'customfield_10016',  # Story points (Scrum)
                'customfield_10026',  # Story points (alternative)
            ]

        endpoint = f"/rest/agile/1.0/sprint/{sprint_id}/issue"
        all_issues = []
        start_at = 0
        max_results = 50

        logger.info(f"Fetching issues for sprint {sprint_id}")

        while True:
            params = {
                'startAt': start_at,
                'maxResults': max_results,
                'fields': ','.join(fields)
            }

            response = self._get(endpoint, params=params)
            issues = response.get('issues', [])
            all_issues.extend(issues)

            total = response.get('total', 0)
            logger.debug(f"Retrieved {len(all_issues)}/{total} issues")

            # Check if we've retrieved all issues
            if len(all_issues) >= total:
                break

            start_at += max_results

        logger.info(f"Retrieved {len(all_issues)} total issues for sprint {sprint_id}")
        return all_issues

    def get_active_sprint(self, board_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the currently active sprint for a board.

        Args:
            board_id: JIRA board ID (numeric)

        Returns:
            Sprint dictionary if active sprint exists, None otherwise.
            Sprint dictionary has same structure as get_sprint_by_id().

        Raises:
            ValueError: Invalid board_id
            JiraNotFoundError: Board does not exist
            JiraAPIError: API request failed

        Example:
            >>> sprint = client.get_active_sprint(42)
            >>> if sprint:
            ...     print(f"Active sprint: {sprint['name']}")
            ... else:
            ...     print("No active sprint")
            Active sprint: Sprint 10
        """
        if not board_id or not isinstance(board_id, int) or board_id <= 0:
            raise ValueError("board_id must be a positive integer")

        endpoint = f"/rest/agile/1.0/board/{board_id}/sprint"
        params = {'state': 'active'}

        logger.info(f"Fetching active sprint for board {board_id}")

        response = self._get(endpoint, params=params)
        sprints = response.get('values', [])

        if not sprints:
            logger.info(f"No active sprint found for board {board_id}")
            return None

        # Return first active sprint (should only be one)
        active_sprint = sprints[0]
        logger.info(f"Found active sprint: {active_sprint.get('name', 'Unknown')}")

        return active_sprint

    def get_sprint_metrics(self, sprint_id: str) -> Dict[str, Any]:
        """
        Calculate sprint metrics based on issues.

        Retrieves all issues in the sprint and calculates various metrics
        including completion rate and story points.

        Args:
            sprint_id: Sprint ID (numeric string)

        Returns:
            Dictionary containing calculated metrics:
                - total_issues: Total number of issues
                - completed: Number of completed issues (status = Done)
                - in_progress: Number of in-progress issues
                - todo: Number of todo/open issues
                - completion_rate: Percentage of completed issues (0-100)
                - total_story_points: Sum of all story points (0 if none)
                - completed_story_points: Sum of completed story points
                - story_point_completion_rate: Percentage of completed points (0-100)
                - issues_by_type: Count of issues grouped by type
                - issues_by_status: Count of issues grouped by status

        Raises:
            ValueError: Invalid sprint_id
            JiraNotFoundError: Sprint does not exist
            JiraAPIError: API request failed

        Example:
            >>> metrics = client.get_sprint_metrics("123")
            >>> print(f"Completion: {metrics['completion_rate']:.1f}%")
            >>> print(f"Story Points: {metrics['completed_story_points']}/{metrics['total_story_points']}")
            Completion: 66.7%
            Story Points: 18/24
        """
        logger.info(f"Calculating metrics for sprint {sprint_id}")

        issues = self.get_sprint_issues(sprint_id)

        # Initialize counters
        total_issues = len(issues)
        completed = 0
        in_progress = 0
        todo = 0
        total_story_points = 0
        completed_story_points = 0
        issues_by_type = {}
        issues_by_status = {}

        for issue in issues:
            fields = issue.get('fields', {})

            # Get status
            status = fields.get('status', {})
            status_name = status.get('name', 'Unknown')
            status_category = status.get('statusCategory', {}).get('name', 'To Do')

            # Count by status
            issues_by_status[status_name] = issues_by_status.get(status_name, 0) + 1

            # Categorize by status
            if status_category == 'Done' or status_name.lower() in ['done', 'closed', 'resolved']:
                completed += 1
            elif status_category == 'In Progress' or status_name.lower() in ['in progress', 'in development', 'in review']:
                in_progress += 1
            else:
                todo += 1

            # Get issue type
            issue_type = fields.get('issuetype', {}).get('name', 'Unknown')
            issues_by_type[issue_type] = issues_by_type.get(issue_type, 0) + 1

            # Get story points (check common field names)
            story_points = (
                fields.get('customfield_10016') or
                fields.get('customfield_10026') or
                fields.get('customfield_10004') or
                0
            )

            if story_points:
                try:
                    story_points = float(story_points)
                    total_story_points += story_points

                    if status_category == 'Done' or status_name.lower() in ['done', 'closed', 'resolved']:
                        completed_story_points += story_points
                except (TypeError, ValueError):
                    logger.warning(f"Invalid story points for {issue.get('key')}: {story_points}")

        # Calculate completion rates
        completion_rate = (completed / total_issues * 100) if total_issues > 0 else 0
        story_point_completion_rate = (
            (completed_story_points / total_story_points * 100)
            if total_story_points > 0 else 0
        )

        metrics = {
            'total_issues': total_issues,
            'completed': completed,
            'in_progress': in_progress,
            'todo': todo,
            'completion_rate': round(completion_rate, 2),
            'total_story_points': total_story_points,
            'completed_story_points': completed_story_points,
            'story_point_completion_rate': round(story_point_completion_rate, 2),
            'issues_by_type': issues_by_type,
            'issues_by_status': issues_by_status,
        }

        logger.info(
            f"Metrics calculated: {completed}/{total_issues} issues complete "
            f"({completion_rate:.1f}%), {completed_story_points}/{total_story_points} "
            f"story points ({story_point_completion_rate:.1f}%)"
        )

        return metrics

    def close(self):
        """Close the HTTP session."""
        self.session.close()
        logger.info("JIRA client session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
