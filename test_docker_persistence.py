"""
Test Docker Persistence Performance

This script tests the persistent Docker container implementation
by making 3 MCP calls and measuring the time taken.

Success Criteria:
- All 3 calls complete successfully
- Total time < 35 seconds (vs ~78s before optimization)
- Container reused across calls (not restarted each time)
"""
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cli.jira_mcp import JiraMCPClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def test_docker_persistence():
    """Test persistent Docker container performance."""
    print("=" * 60)
    print("Docker Persistence Performance Test")
    print("=" * 60)
    print()

    # Get credentials from environment
    jira_url = os.getenv('JIRA_URL')
    jira_username = os.getenv('JIRA_USERNAME')
    jira_api_token = os.getenv('JIRA_API_TOKEN')

    if not all([jira_url, jira_username, jira_api_token]):
        print("❌ Error: JIRA credentials not found in environment")
        print("   Please set JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN")
        return False

    print(f"JIRA URL: {jira_url}")
    print(f"Username: {jira_username}")
    print()

    # Start timer
    start_time = time.time()

    try:
        print("Step 1: Initializing JIRA MCP client with context manager...")
        with JiraMCPClient(
            jira_url=jira_url,
            jira_username=jira_username,
            jira_api_token=jira_api_token
        ) as client:
            print("✅ Client initialized")
            init_time = time.time() - start_time
            print(f"   Time: {init_time:.2f}s")
            print()

            # Call 1: List sprints
            print("Step 2: Fetching sprints (MCP Call #1)...")
            call1_start = time.time()
            sprints = client.list_sprints(board_id=38, limit=5)
            call1_time = time.time() - call1_start
            print(f"✅ Fetched {len(sprints)} sprints")
            print(f"   Time: {call1_time:.2f}s")
            print()

            if not sprints:
                print("❌ No sprints found - cannot continue test")
                return False

            # Call 2: Get sprint by ID
            print("Step 3: Fetching sprint details (MCP Call #2)...")
            call2_start = time.time()
            sprint = client.get_sprint_by_id(sprints[0].id)
            call2_time = time.time() - call2_start
            print(f"✅ Fetched sprint: {sprint.name}")
            print(f"   Time: {call2_time:.2f}s")
            print()

            # Call 3: Get sprint issues
            print("Step 4: Fetching sprint issues (MCP Call #3)...")
            call3_start = time.time()
            issues = client.get_sprint_issues(sprints[0].id)
            call3_time = time.time() - call3_start
            print(f"✅ Fetched {len(issues)} issues")
            print(f"   Time: {call3_time:.2f}s")
            print()

        # Container automatically cleaned up here
        print("Step 5: Container cleanup")
        print("✅ JIRA client context manager exited cleanly")
        print()

        # Calculate total time
        total_time = time.time() - start_time

        # Print results
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Container initialization: {init_time:.2f}s")
        print(f"MCP Call #1 (list_sprints): {call1_time:.2f}s")
        print(f"MCP Call #2 (get_sprint_by_id): {call2_time:.2f}s")
        print(f"MCP Call #3 (get_sprint_issues): {call3_time:.2f}s")
        print(f"Total time: {total_time:.2f}s")
        print()

        # Check success criteria
        success = total_time < 35

        if success:
            print(f"✅ SUCCESS: Completed in {total_time:.2f}s (< 35s target)")
            print(f"   Performance gain: ~{78 - total_time:.0f}s faster than before")
            print(f"   Speed improvement: {((78 - total_time) / 78 * 100):.0f}%")
        else:
            print(f"❌ FAILED: Took {total_time:.2f}s (>= 35s target)")
            print(f"   Expected < 35s, but persistent container should fix this")

        print()
        print("=" * 60)

        return success

    except Exception as e:
        elapsed = time.time() - start_time
        print()
        print("=" * 60)
        print(f"❌ ERROR after {elapsed:.2f}s: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_docker_persistence()
    sys.exit(0 if success else 1)
