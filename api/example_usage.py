"""
Example usage of JIRA and Fathom API clients.

This script demonstrates how to use both clients to fetch sprint data
and meeting information for generating sprint reports.

Run this script to verify your API credentials are working correctly.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import JiraClient, FathomClient
from api import (
    JiraAPIError, JiraAuthenticationError, JiraPermissionError, JiraNotFoundError,
    FathomAPIError, FathomAuthenticationError, FathomRateLimitError
)


def test_jira_client():
    """Test JIRA client functionality."""
    print("\n" + "="*60)
    print("Testing JIRA Client")
    print("="*60 + "\n")

    try:
        # Initialize client
        client = JiraClient(
            base_url=os.getenv('JIRA_BASE_URL'),
            email=os.getenv('JIRA_EMAIL'),
            api_token=os.getenv('JIRA_API_TOKEN')
        )

        print("✓ JIRA client initialized successfully\n")

        # Test 1: Get active sprint
        board_id = int(os.getenv('JIRA_BOARD_ID', '1'))
        print(f"Fetching active sprint for board {board_id}...")

        active_sprint = client.get_active_sprint(board_id)

        if active_sprint:
            sprint_id = active_sprint['id']
            print(f"✓ Found active sprint: {active_sprint['name']}")
            print(f"  ID: {sprint_id}")
            print(f"  State: {active_sprint['state']}")
            print(f"  Start: {active_sprint.get('startDate', 'N/A')}")
            print(f"  End: {active_sprint.get('endDate', 'N/A')}")
            print(f"  Goal: {active_sprint.get('goal', 'No goal set')}\n")

            # Test 2: Get sprint issues
            print(f"Fetching issues for sprint {sprint_id}...")
            issues = client.get_sprint_issues(str(sprint_id))
            print(f"✓ Retrieved {len(issues)} issues\n")

            # Show first few issues
            if issues:
                print("Sample issues:")
                for i, issue in enumerate(issues[:3], 1):
                    fields = issue.get('fields', {})
                    status = fields.get('status', {}).get('name', 'Unknown')
                    summary = fields.get('summary', 'No summary')
                    print(f"  {i}. {issue['key']}: {summary}")
                    print(f"     Status: {status}")

                if len(issues) > 3:
                    print(f"  ... and {len(issues) - 3} more\n")

            # Test 3: Calculate metrics
            print(f"Calculating sprint metrics...")
            metrics = client.get_sprint_metrics(str(sprint_id))
            print(f"✓ Metrics calculated\n")

            print("Sprint Metrics:")
            print(f"  Total Issues: {metrics['total_issues']}")
            print(f"  Completed: {metrics['completed']}")
            print(f"  In Progress: {metrics['in_progress']}")
            print(f"  Todo: {metrics['todo']}")
            print(f"  Completion Rate: {metrics['completion_rate']}%")
            print(f"  Total Story Points: {metrics['total_story_points']}")
            print(f"  Completed Story Points: {metrics['completed_story_points']}")
            print(f"  Story Point Completion: {metrics['story_point_completion_rate']}%\n")

            if metrics['issues_by_type']:
                print("  Issues by Type:")
                for issue_type, count in metrics['issues_by_type'].items():
                    print(f"    {issue_type}: {count}")
                print()

        else:
            print("⚠ No active sprint found for this board")
            print("Try setting a different JIRA_BOARD_ID in your .env file\n")

        print("✓ All JIRA client tests passed!\n")
        client.close()

    except JiraAuthenticationError as e:
        print(f"✗ Authentication Error: {e}")
        print("\nCheck your JIRA credentials in .env file:")
        print("  - JIRA_BASE_URL")
        print("  - JIRA_EMAIL")
        print("  - JIRA_API_TOKEN")
        return False

    except JiraPermissionError as e:
        print(f"✗ Permission Error: {e}")
        return False

    except JiraNotFoundError as e:
        print(f"✗ Not Found Error: {e}")
        print(f"\nThe board ID {board_id} may not exist.")
        print("Update JIRA_BOARD_ID in your .env file")
        return False

    except JiraAPIError as e:
        print(f"✗ JIRA API Error: {e}")
        return False

    except Exception as e:
        print(f"✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_fathom_client():
    """Test Fathom client functionality."""
    print("\n" + "="*60)
    print("Testing Fathom Client")
    print("="*60 + "\n")

    try:
        # Initialize client
        client = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))
        print("✓ Fathom client initialized successfully\n")

        # Test 1: List recent meetings
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)

        print(f"Fetching meetings from last 14 days...")
        print(f"  Start: {start_date.strftime('%Y-%m-%d')}")
        print(f"  End: {end_date.strftime('%Y-%m-%d')}\n")

        meetings = client.list_meetings(
            start_date=start_date.isoformat() + 'Z',
            end_date=end_date.isoformat() + 'Z'
        )

        print(f"✓ Found {len(meetings)} meetings\n")

        if meetings:
            # Show first few meetings
            print("Recent meetings:")
            for i, meeting in enumerate(meetings[:3], 1):
                title = meeting.get('title', meeting.get('meeting_title', 'Untitled'))
                start_time = meeting.get('start_time', 'Unknown')
                duration = meeting.get('duration', 0)

                # Convert duration to minutes
                duration_min = duration // 60 if duration else 0

                print(f"  {i}. {title}")
                print(f"     Date: {start_time}")
                print(f"     Duration: {duration_min} minutes")
                print(f"     ID: {meeting.get('id', 'N/A')}")

            if len(meetings) > 3:
                print(f"  ... and {len(meetings) - 3} more\n")
            else:
                print()

            # Test 2: Get transcript and summary for first meeting
            first_meeting = meetings[0]
            meeting_id = first_meeting.get('id')

            if meeting_id:
                print(f"Fetching details for: {first_meeting.get('title', 'Untitled')}...\n")

                # Get transcript
                print("  Fetching transcript...")
                try:
                    transcript = client.get_meeting_transcript(meeting_id)
                    print(f"  ✓ Transcript: {len(transcript)} segments")

                    if transcript:
                        # Show first segment
                        first_segment = transcript[0]
                        speaker = first_segment.get('speaker', {}).get('display_name', 'Unknown')
                        text = first_segment.get('text', '')
                        timestamp = first_segment.get('timestamp', '00:00:00')
                        print(f"    Sample: [{timestamp}] {speaker}: {text[:60]}...")

                except FathomAPIError as e:
                    print(f"  ⚠ Could not fetch transcript: {e}")

                # Get summary
                print("\n  Fetching summary...")
                try:
                    summary = client.get_meeting_summary(meeting_id)
                    print(f"  ✓ Summary: {len(summary)} characters")

                    if summary:
                        # Show first 200 characters
                        preview = summary[:200].replace('\n', ' ')
                        print(f"    Preview: {preview}...")

                except FathomAPIError as e:
                    print(f"  ⚠ Could not fetch summary: {e}")

                print()

        else:
            print("⚠ No meetings found in the specified date range")
            print("This could be normal if you haven't had any Fathom meetings recently.\n")

        print("✓ All Fathom client tests passed!\n")
        client.close()

    except FathomAuthenticationError as e:
        print(f"✗ Authentication Error: {e}")
        print("\nCheck your FATHOM_API_KEY in .env file")
        return False

    except FathomRateLimitError as e:
        print(f"✗ Rate Limit Error: {e}")
        return False

    except FathomAPIError as e:
        print(f"✗ Fathom API Error: {e}")
        return False

    except Exception as e:
        print(f"✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_combined_usage():
    """Test combined usage for sprint report generation."""
    print("\n" + "="*60)
    print("Testing Combined Usage (Sprint Report)")
    print("="*60 + "\n")

    try:
        # Initialize both clients
        jira = JiraClient(
            base_url=os.getenv('JIRA_BASE_URL'),
            email=os.getenv('JIRA_EMAIL'),
            api_token=os.getenv('JIRA_API_TOKEN')
        )

        fathom = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))

        print("✓ Both clients initialized\n")

        # Get active sprint
        board_id = int(os.getenv('JIRA_BOARD_ID', '1'))
        sprint = jira.get_active_sprint(board_id)

        if not sprint:
            print("⚠ No active sprint found. Using date range from last 14 days.\n")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=14)
            sprint_start = start_date.isoformat() + 'Z'
            sprint_end = end_date.isoformat() + 'Z'
            sprint_name = "Last 14 Days"
        else:
            sprint_start = sprint.get('startDate')
            sprint_end = sprint.get('endDate')
            sprint_name = sprint.get('name', 'Unknown Sprint')

            print(f"Active Sprint: {sprint_name}")
            print(f"  Start: {sprint_start}")
            print(f"  End: {sprint_end}\n")

        # Get sprint meetings
        print("Fetching meetings during sprint period...")
        meetings = fathom.list_meetings(
            start_date=sprint_start,
            end_date=sprint_end
        )

        print(f"✓ Found {len(meetings)} meetings during sprint\n")

        # Create report summary
        print("="*60)
        print(f"Sprint Report Summary: {sprint_name}")
        print("="*60)

        if sprint:
            metrics = jira.get_sprint_metrics(str(sprint['id']))
            print(f"\nJIRA Metrics:")
            print(f"  Issues: {metrics['completed']}/{metrics['total_issues']} completed ({metrics['completion_rate']}%)")
            print(f"  Story Points: {metrics['completed_story_points']}/{metrics['total_story_points']} ({metrics['story_point_completion_rate']}%)")

        print(f"\nMeetings: {len(meetings)} total")
        if meetings:
            total_duration = sum(m.get('duration', 0) for m in meetings)
            total_hours = total_duration / 3600
            print(f"  Total meeting time: {total_hours:.1f} hours")

        print("\n✓ Combined usage test completed!\n")

        jira.close()
        fathom.close()

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("API Client Test Suite")
    print("="*60)

    # Load environment variables
    load_dotenv()

    # Check required environment variables
    required_vars = {
        'JIRA': ['JIRA_BASE_URL', 'JIRA_EMAIL', 'JIRA_API_TOKEN'],
        'Fathom': ['FATHOM_API_KEY']
    }

    missing_vars = []
    for service, vars in required_vars.items():
        for var in vars:
            if not os.getenv(var):
                missing_vars.append(f"{service}: {var}")

    if missing_vars:
        print("\n⚠ Missing environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in your .env file and try again.")
        print("See .env.template for the required format.\n")
        return

    # Run tests
    results = {
        'JIRA Client': test_jira_client(),
        'Fathom Client': test_fathom_client(),
        'Combined Usage': test_combined_usage(),
    }

    # Print summary
    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60 + "\n")

    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print()

    if all_passed:
        print("✓ All tests passed! API clients are working correctly.\n")
    else:
        print("⚠ Some tests failed. Check the output above for details.\n")


if __name__ == '__main__':
    main()
