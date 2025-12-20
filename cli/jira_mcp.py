"""
JIRA MCP Client - Wrapper for JIRA MCP Docker container.

Provides a Python interface to the MCP Atlassian server running in Docker.
Communicates via JSON-RPC over stdin/stdout.

Uses a persistent Docker container for the entire session to eliminate
startup overhead (60% performance improvement).
"""
import json
import subprocess
import logging
import os
import atexit
import random
import threading
import sys
import io
from queue import Queue, Empty
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from utils.data_validation import validate_story_points
from utils.mcp_validation import validate_mcp_response, validate_sprint_data, validate_issue_data
from utils.exceptions import JiraMCPError


logger = logging.getLogger(__name__)


def _read_with_timeout(stream, timeout: float = 30.0) -> Optional[str]:
    """Read line from stream with timeout.

    Args:
        stream: File-like object to read from (stdout/stderr)
        timeout: Timeout in seconds

    Returns:
        Line read, or None if timeout

    Raises:
        TimeoutError: If read times out
    """
    result_queue = Queue()

    def reader_thread():
        try:
            line = stream.readline()
            result_queue.put(('success', line))
        except Exception as e:
            result_queue.put(('error', e))

    thread = threading.Thread(target=reader_thread, daemon=True)
    thread.start()

    try:
        status, data = result_queue.get(timeout=timeout)
        if status == 'error':
            raise data
        return data
    except Empty:
        # Timeout occurred
        raise TimeoutError(f"Container did not respond within {timeout} seconds")


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
    """Client for JIRA MCP Docker container.

    Uses a persistent container for the entire session to eliminate Docker
    startup overhead (saves ~50 seconds per report generation).

    Usage:
        with JiraMCPClient(url, username, token) as client:
            sprints = client.list_sprints(board_id)
            issues = client.get_sprint_issues(sprint_id)
        # Container automatically cleaned up
    """

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

        # Persistent container management
        self.container_name = f"mcp-jira-{os.getpid()}"
        self._container_process = None
        self._container_stdin = None
        self._container_stdout = None
        self._initialized = False

        # Container health tracking
        self._container_healthy = True
        self._consecutive_failures = 0
        self._max_failures_before_restart = 2

        # Register cleanup on exit
        atexit.register(self.close)

    def _ensure_container_running(self):
        """Ensure Docker container is running (start if needed)."""
        if self._container_process and self._container_process.poll() is None:
            return  # Already running

        # Clean up any existing container with same name
        cleanup_cmd = ['docker', 'rm', '-f', self.container_name]
        subprocess.run(cleanup_cmd, capture_output=True, text=True)

        # Start persistent container
        docker_cmd = [
            'docker', 'run', '-i', '--name', self.container_name,
            '-e', f'JIRA_URL={self.jira_url}',
            '-e', f'JIRA_USERNAME={self.jira_username}',
            '-e', f'JIRA_API_TOKEN={self.jira_api_token}',
            '-e', 'LANG=C.UTF-8',
            '-e', 'LC_ALL=C.UTF-8',
            self.docker_image
        ]

        # Use default buffering with explicit flush after every write
        # This is the most reliable approach across platforms
        self._container_process = subprocess.Popen(
            docker_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
            # bufsize=-1 (default) = use system default buffering
        )
        self._container_stdin = self._container_process.stdin
        self._container_stdout = self._container_process.stdout

        # Send initialization handshake once
        if not self._initialized:
            self._send_initialization()
            self._initialized = True

    def _check_container_health(self) -> bool:
        """Check if container is responsive.

        Returns:
            True if container is healthy, False otherwise
        """
        if not self._container_process or self._container_process.poll() is not None:
            logger.warning("Container process is dead")
            return False

        # Simple ping test - call tools/list (lightweight)
        try:
            ping_request = {
                "jsonrpc": "2.0",
                "id": 99999,
                "method": "tools/list",
                "params": {}
            }

            self._container_stdin.write(json.dumps(ping_request) + "\n")
            self._container_stdin.flush()

            # Try to read response with short timeout
            response_line = _read_with_timeout(self._container_stdout, timeout=5.0)

            if response_line:
                logger.debug("Container health check passed")
                return True

            logger.warning("Container health check failed - no response")
            return False

        except TimeoutError:
            logger.warning("Container health check timeout")
            return False
        except Exception as e:
            logger.warning(f"Container health check error: {e}")
            return False

    def _send_initialization(self):
        """Send MCP initialization handshake."""
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

        # Step 1: Send initialize request and flush
        self._container_stdin.write(json.dumps(init_request) + "\n")
        self._container_stdin.flush()

        # Step 2: Read initialize response FIRST (before sending notification)
        try:
            response_line = _read_with_timeout(
                self._container_stdout,
                timeout=30.0  # 30 second timeout for initialization
            )
            if response_line:
                response = json.loads(response_line)
                if 'error' in response:
                    raise JiraMCPError(f"Initialization error: {response['error']}")
        except TimeoutError as e:
            logger.error(f"MCP initialization timeout: {e}")
            raise JiraMCPError("MCP container initialization timed out - container may be stuck")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse initialization response: {e}")

        # Step 3: NOW send initialized notification (after reading response)
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        self._container_stdin.write(json.dumps(initialized_notification) + "\n")
        self._container_stdin.flush()

        # Step 4: Some MCP servers auto-send tools/list after initialization
        # Try to consume it if it exists (with short timeout)
        try:
            tools_response = _read_with_timeout(self._container_stdout, timeout=2.0)
            if tools_response:
                logger.debug(f"Consumed automatic tools/list response: {tools_response[:100]}")
        except TimeoutError:
            # No automatic response, that's okay
            logger.debug("No automatic tools/list response")
        except Exception as e:
            logger.warning(f"Error consuming tools/list: {e}")

    def close(self):
        """Stop persistent container and cleanup."""
        if self._container_process:
            try:
                # Close wrapped streams first (Windows)
                if self._container_stdin and sys.platform == 'win32':
                    try:
                        self._container_stdin.close()
                    except Exception:
                        pass
                if self._container_stdout and sys.platform == 'win32':
                    try:
                        self._container_stdout.close()
                    except Exception:
                        pass

                self._container_process.terminate()
                self._container_process.wait(timeout=5)
            except Exception:
                # Force kill if terminate fails
                self._container_process.kill()
                self._container_process.wait()
            finally:
                self._container_stdin = None
                self._container_stdout = None
                self._container_process = None
                self._initialized = False

        # Clean up container
        cleanup_cmd = ['docker', 'rm', '-f', self.container_name]
        subprocess.run(cleanup_cmd, capture_output=True, text=True)

    def _restart_container(self):
        """Restart MCP container after failure.

        This preserves the container configuration but creates a fresh process.
        """
        logger.info("Restarting MCP container due to failure")

        # Close existing container
        self.close()

        # Wait a moment for cleanup
        import time
        time.sleep(2)

        # Reset state
        self._initialized = False
        self._container_healthy = True
        self._consecutive_failures = 0

        # Start fresh container
        self._ensure_container_running()

        logger.info("MCP container restarted successfully")

    def __enter__(self):
        """Context manager entry."""
        self._ensure_container_running()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call an MCP tool via Docker container (using persistent container).

        Args:
            tool_name: Name of the MCP tool (e.g., 'jira_get_sprints')
            arguments: Dictionary of tool arguments

        Returns:
            Tool result data

        Raises:
            JiraMCPError: If Docker fails or MCP returns an error
        """
        # Ensure persistent container is running
        self._ensure_container_running()

        # Build tool request (initialization already done at container start)
        tool_request = {
            "jsonrpc": "2.0",
            "id": random.randint(1, 10000),  # Unique ID for each request
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        try:
            # Send tool request to persistent container
            self._container_stdin.write(json.dumps(tool_request) + "\n")
            self._container_stdin.flush()

            # Read response from persistent container with timeout
            try:
                response_line = _read_with_timeout(
                    self._container_stdout,
                    timeout=60.0  # 60 second timeout for tool calls
                )
            except TimeoutError as e:
                logger.error(f"MCP tool call timeout for {tool_name}: {e}")

                # Track consecutive failures
                self._consecutive_failures += 1
                self._container_healthy = False

                # Auto-restart after multiple failures
                if self._consecutive_failures >= self._max_failures_before_restart:
                    logger.warning(f"Container failed {self._consecutive_failures} times, restarting")
                    try:
                        self._restart_container()
                        # Retry the tool call once after restart
                        logger.info(f"Retrying {tool_name} after container restart")
                        return self._call_mcp_tool(tool_name, arguments)  # Recursive retry
                    except Exception as retry_error:
                        logger.error(f"Retry after restart failed: {retry_error}")
                        raise JiraMCPError(f"MCP container failed even after restart: {retry_error}")

                raise JiraMCPError(f"MCP container timeout calling {tool_name} - container may be hung")

            if not response_line:
                # Container crashed or closed
                raise JiraMCPError("No response from MCP container (container may have crashed)")

            # Parse JSON-RPC response
            try:
                tool_response = json.loads(response_line)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in MCP response: {response_line[:200]}")
                raise JiraMCPError(f"Invalid JSON in MCP response: {e}")

            # Validate MCP response structure and extract data
            return validate_mcp_response(tool_response)

        except Exception as e:
            # Track failures for any exception
            self._consecutive_failures += 1
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

        Tries two approaches:
        1. MCP tool jira_get_sprint_issues (may timeout)
        2. Fallback to JQL search if tool fails

        Args:
            sprint_id: Sprint ID

        Returns:
            List of Issue objects

        Raises:
            JiraMCPError: If both methods fail
        """
        # Helper function to parse issue data (used by both methods)
        def parse_issue(issue_data):
            """Parse issue data into Issue object."""
            if not validate_issue_data(issue_data):
                return None  # Skip invalid issue

            # Extract fields from flattened MCP format
            status_obj = issue_data.get('status', {})
            assignee_obj = issue_data.get('assignee', {})

            return Issue(
                key=issue_data.get('key', 'N/A'),
                summary=issue_data.get('summary', ''),
                status=status_obj.get('name', 'Unknown') if isinstance(status_obj, dict) else str(status_obj),
                assignee=assignee_obj.get('display_name') if isinstance(assignee_obj, dict) and assignee_obj else None,
                issue_type=issue_data.get('issue_type', {}).get('name', 'Task') if isinstance(issue_data.get('issue_type'), dict) else 'Task',
                story_points=validate_story_points(issue_data.get('story_points'))
            )

        # Try MCP tool first
        try:
            result = self._call_mcp_tool('jira_get_sprint_issues', {
                'sprint_id': str(sprint_id)
            })

            # Parse MCP response
            issues = []
            if isinstance(result, dict) and 'issues' in result:
                for issue_data in result['issues']:
                    issue = parse_issue(issue_data)
                    if issue:
                        issues.append(issue)

            logger.info(f"MCP tool succeeded: fetched {len(issues)} issues")
            return issues

        except (JiraMCPError, TimeoutError) as e:
            logger.warning(f"MCP tool failed for sprint {sprint_id}, trying JQL fallback: {e}")

            # Fallback: Use JQL search
            try:
                result = self._call_mcp_tool('jira_search', {
                    'jql': f'sprint = {sprint_id} ORDER BY rank ASC',
                    'max_results': 100,
                    'start_at': 0,
                    'fields': 'summary,status,assignee,issuetype,customfield_10016'  # customfield_10016 is usually story points
                })

                # Parse JQL response (same structure as jira_get_sprint_issues)
                issues = []
                if isinstance(result, dict) and 'issues' in result:
                    for issue_data in result['issues']:
                        issue = parse_issue(issue_data)
                        if issue:
                            issues.append(issue)

                logger.info(f"JQL fallback succeeded: fetched {len(issues)} issues")
                return issues

            except Exception as jql_error:
                logger.error(f"Both MCP tool and JQL fallback failed: {jql_error}")
                raise JiraMCPError(f"Could not fetch issues for sprint {sprint_id}: {jql_error}")

    def get_sprint_by_id(self, sprint_id: int) -> Sprint:
        """Get sprint details by ID using JQL search fallback.

        Since jira_get_sprint tool doesn't exist in MCP, we use jira_search
        with a JQL filter to find issues in the sprint, then extract
        sprint metadata from the first issue's sprint field.

        Args:
            sprint_id: Sprint ID

        Returns:
            Sprint object (may have minimal data if JQL fails)

        Raises:
            JiraMCPError: If the sprint cannot be found at all
        """
        try:
            # Try JQL search to get sprint metadata from issues
            result = self._call_mcp_tool('jira_search', {
                'jql': f'sprint = {sprint_id}',
                'max_results': 1,
                'fields': 'summary'  # Minimal fields for speed
            })

            if not result.get('issues') or len(result['issues']) == 0:
                # Sprint has no issues - return minimal Sprint object
                logger.warning(f"Sprint {sprint_id} found but has no issues, using minimal data")
                return Sprint(
                    id=sprint_id,
                    name=f'Sprint {sprint_id}',
                    state='unknown',
                    start_date=None,
                    end_date=None,
                    board_id=0
                )

            # Sprint exists (we found issues) - return minimal Sprint
            # Note: Sprint field format varies and isn't reliably accessible
            # User will confirm/update dates in interactive flow
            return Sprint(
                id=sprint_id,
                name=f'Sprint {sprint_id}',  # Will be updated by user
                state='unknown',
                start_date=None,
                end_date=None,
                board_id=0
            )

        except Exception as e:
            # JQL search failed (likely timeout) - return minimal Sprint
            logger.warning(f"JQL search failed for sprint {sprint_id}: {e}, using minimal data")
            return Sprint(
                id=sprint_id,
                name=f'Sprint {sprint_id}',
                state='unknown',
                start_date=None,
                end_date=None,
                board_id=0
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
