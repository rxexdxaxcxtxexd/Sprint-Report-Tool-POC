"""
JIRA MCP Client - Wrapper for JIRA MCP Docker container.

Provides a Python interface to the MCP Atlassian server running in Docker.
Communicates via JSON-RPC over stdin/stdout.
"""
import json
import subprocess
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from utils.data_validation import validate_story_points
from utils.mcp_validation import validate_mcp_response, validate_sprint_data, validate_issue_data


class JiraMCPError(Exception):
    """Exception raised for JIRA MCP communication errors."""
    pass


logger = logging.getLogger(__name__)


@dataclass
class Sprint:
    """Sprint data model."""
    id: int
    name: str
    state: str  # 'future', 'active', 'closed'
    start_date: Optional[str]
    end_date: Optional[str]
    board_id: int


@dataclass
class Issue:
    """JIRA issue data model."""
    key: str
    summary: str
    status: str
    assignee: Optional[str]
    issue_type: str
    story_points: Optional[float]


class JiraMCPClient:
    """Client for JIRA MCP Docker container."""

    def __init__(self, jira_url: str, jira_username: str, jira_api_token: str):
        """Initialize JIRA MCP client.

        Args:
            jira_url: JIRA instance URL (e.g., https://company.atlassian.net)
            jira_username: JIRA username/email
            jira_api_token: JIRA API token
        """
        self.jira_url = jira_url
        self.jira_username = jira_username
        self.jira_api_token = jira_api_token
        self.docker_image = "ghcr.io/sooperset/mcp-atlassian:latest"

    def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call an MCP tool via Docker container.

        Args:
            tool_name: Name of the MCP tool (e.g., 'jira_get_sprints')
            arguments: Dictionary of tool arguments

        Returns:
            Tool result data

        Raises:
            JiraMCPError: If Docker fails or MCP returns an error
        """
        # Build Docker command with environment variables
        docker_cmd = [
            'docker', 'run', '--rm', '-i',
            '-e', f'JIRA_URL={self.jira_url}',
            '-e', f'JIRA_USERNAME={self.jira_username}',
            '-e', f'JIRA_API_TOKEN={self.jira_api_token}',
            '-e', 'LANG=C.UTF-8',
            '-e', 'LC_ALL=C.UTF-8',
            self.docker_image
        ]

        # Build JSON-RPC requests (initialize first, then call tool)
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "sprint-report-cli",
                    "version": "1.0.0"
                }
            }
        }

        # Send initialized notification (required by MCP protocol)
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }

        tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        # Combine requests (newline-delimited JSON)
        combined_input = (
            json.dumps(init_request) + "\n" +
            json.dumps(initialized_notification) + "\n" +
            json.dumps(tool_request) + "\n"
        )

        try:
            # Execute Docker command
            process = subprocess.Popen(
                docker_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            # Send requests and get responses (text mode handles encoding)
            stdout, stderr = process.communicate(
                input=combined_input,
                timeout=30  # 30 second timeout
            )

            # Check for Docker errors
            if process.returncode != 0:
                raise JiraMCPError(
                    f"Docker command failed (exit code {process.returncode}):\n{stderr}"
                )

            # Parse JSON-RPC responses (newline-delimited)
            responses = []
            for line in stdout.strip().split('\n'):
                if line.strip():
                    try:
                        responses.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # Skip non-JSON lines (e.g., INFO logs)

            if not responses:
                raise JiraMCPError(f"No valid JSON responses from MCP: {stdout[:200]}")

            # Get the tool response (should be the last response after init)
            tool_response = responses[-1]

            # Validate MCP response structure and extract data
            return validate_mcp_response(tool_response)

        except subprocess.TimeoutExpired:
            process.kill()
            raise JiraMCPError("MCP tool call timed out after 30 seconds")
        except Exception as e:
            if isinstance(e, JiraMCPError):
                raise
            raise JiraMCPError(f"Unexpected error calling MCP: {e}")

    def list_sprints(self, board_id: int, limit: int = 10) -> List[Sprint]:
        """List recent sprints from a JIRA board.

        Args:
            board_id: JIRA board ID
            limit: Maximum number of sprints to return

        Returns:
            List of Sprint objects

        Raises:
            JiraMCPError: If the MCP call fails
        """
        result = self._call_mcp_tool('jira_get_sprints_from_board', {
            'board_id': str(board_id),
            'limit': limit,
            'start_at': 0
        })

        # Parse and validate sprint data
        sprints = []
        if isinstance(result, list):
            for sprint_data in result:
                # Validate sprint data schema (logs warning if invalid, continues with next)
                if not validate_sprint_data(sprint_data):
                    continue  # Skip invalid sprint

                sprints.append(Sprint(
                    id=int(sprint_data['id']),
                    name=sprint_data['name'],
                    state=sprint_data['state'],
                    start_date=sprint_data.get('start_date'),
                    end_date=sprint_data.get('end_date'),
                    board_id=board_id
                ))

        return sprints

    def get_sprint_issues(self, sprint_id: int) -> List[Issue]:
        """Get all issues in a sprint.

        Args:
            sprint_id: Sprint ID

        Returns:
            List of Issue objects

        Raises:
            JiraMCPError: If the MCP call fails
        """
        result = self._call_mcp_tool('jira_get_sprint_issues', {
            'sprint_id': str(sprint_id)
        })

        # Parse and validate issue data
        issues = []
        if isinstance(result, dict) and 'issues' in result:
            for issue_data in result['issues']:
                # Validate issue data schema (logs warning if invalid, continues with next)
                if not validate_issue_data(issue_data):
                    continue  # Skip invalid issue

                # Extract fields from flattened MCP format
                status_obj = issue_data.get('status', {})
                assignee_obj = issue_data.get('assignee', {})

                issues.append(Issue(
                    key=issue_data.get('key', 'N/A'),
                    summary=issue_data.get('summary', ''),
                    status=status_obj.get('name', 'Unknown') if isinstance(status_obj, dict) else str(status_obj),
                    assignee=assignee_obj.get('display_name') if isinstance(assignee_obj, dict) and assignee_obj else None,
                    issue_type=issue_data.get('issue_type', {}).get('name', 'Task') if isinstance(issue_data.get('issue_type'), dict) else 'Task',
                    story_points=validate_story_points(issue_data.get('story_points'))
                ))

        return issues

    def get_sprint_by_id(self, sprint_id: int) -> Sprint:
        """Get sprint details by ID.

        Args:
            sprint_id: Sprint ID

        Returns:
            Sprint object

        Raises:
            JiraMCPError: If the MCP call fails
        """
        result = self._call_mcp_tool('jira_get_sprint', {
            'sprint_id': str(sprint_id)
        })

        return Sprint(
            id=result['id'],
            name=result['name'],
            state=result['state'],
            start_date=result.get('startDate'),
            end_date=result.get('endDate'),
            board_id=result.get('originBoardId', 0)
        )

    def check_connection(self) -> bool:
        """Test JIRA MCP connection.

        Returns:
            True if connection successful

        Raises:
            JiraMCPError: If connection fails
        """
        try:
            # Try to list sprints as a connection test
            self._call_mcp_tool('jira_search', {
                'jql': 'project != null',
                'max_results': 1
            })
            return True
        except Exception as e:
            raise JiraMCPError(f"Connection test failed: {e}")


if __name__ == "__main__":
    """Test JIRA MCP client."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    client = JiraMCPClient(
        jira_url=os.getenv('JIRA_URL'),
        jira_username=os.getenv('JIRA_USERNAME'),
        jira_api_token=os.getenv('JIRA_API_TOKEN')
    )

    print("Testing JIRA MCP connection...")
    try:
        client.check_connection()
        print("✓ Connection successful")

        print("\nFetching recent sprints...")
        sprints = client.list_sprints(board_id=38, limit=5)
        for sprint in sprints:
            print(f"  - {sprint.name} ({sprint.state})")

    except JiraMCPError as e:
        print(f"✗ Error: {e}")
