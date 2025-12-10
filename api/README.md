# API Client Modules

Production-ready API clients for JIRA and Fathom Video, designed for the Sprint Report Service.

## Overview

This package provides two main clients:

- **JiraClient**: Interact with JIRA Agile REST API to fetch sprint data, issues, and metrics
- **FathomClient**: Interact with Fathom Video API to retrieve meeting recordings, transcripts, and summaries

## Installation

Required dependencies (already in `requirements.txt`):

```bash
pip install requests python-dotenv
```

## Configuration

Set up your environment variables in `.env` file:

```env
# JIRA Configuration
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

# Fathom Configuration
FATHOM_API_KEY=your-fathom-api-key
```

### Getting API Credentials

**JIRA API Token:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label and copy the token

**Fathom API Key:**
1. Open Fathom settings
2. Navigate to "API Access" section
3. Generate a new API key

## Quick Start

### JIRA Client

```python
import os
from dotenv import load_dotenv
from api import JiraClient

# Load environment variables
load_dotenv()

# Initialize client
jira = JiraClient(
    base_url=os.getenv('JIRA_BASE_URL'),
    email=os.getenv('JIRA_EMAIL'),
    api_token=os.getenv('JIRA_API_TOKEN')
)

# Fetch sprint data
sprint = jira.get_sprint_by_id("123")
print(f"Sprint: {sprint['name']}")
print(f"State: {sprint['state']}")
print(f"Start: {sprint['startDate']}")

# Get all issues in sprint
issues = jira.get_sprint_issues("123")
print(f"Total issues: {len(issues)}")

# Calculate metrics
metrics = jira.get_sprint_metrics("123")
print(f"Completion rate: {metrics['completion_rate']}%")
print(f"Story points: {metrics['completed_story_points']}/{metrics['total_story_points']}")

# Get active sprint for a board
active_sprint = jira.get_active_sprint(board_id=42)
if active_sprint:
    print(f"Active sprint: {active_sprint['name']}")
```

### Fathom Client

```python
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from api import FathomClient

# Load environment variables
load_dotenv()

# Initialize client
fathom = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))

# Define date range (last 2 weeks)
end_date = datetime.now()
start_date = end_date - timedelta(days=14)

# List meetings
meetings = fathom.list_meetings(
    start_date=start_date.isoformat() + 'Z',
    end_date=end_date.isoformat() + 'Z'
)

print(f"Found {len(meetings)} meetings")

# Get details for each meeting
for meeting in meetings:
    print(f"\nMeeting: {meeting['title']}")
    print(f"Date: {meeting['start_time']}")

    # Fetch transcript
    transcript = fathom.get_meeting_transcript(meeting['id'])
    print(f"Transcript segments: {len(transcript)}")

    # Fetch summary
    summary = fathom.get_meeting_summary(meeting['id'])
    print(f"Summary: {summary[:100]}...")

# Convenience method to get everything at once
enriched_meetings = fathom.get_sprint_meetings(
    start_date=start_date.isoformat() + 'Z',
    end_date=end_date.isoformat() + 'Z',
    include_transcripts=True,
    include_summaries=True
)
```

### Combined Usage for Sprint Reports

```python
import os
from datetime import datetime
from dotenv import load_dotenv
from api import JiraClient, FathomClient

load_dotenv()

# Initialize clients
jira = JiraClient(
    base_url=os.getenv('JIRA_BASE_URL'),
    email=os.getenv('JIRA_EMAIL'),
    api_token=os.getenv('JIRA_API_TOKEN')
)

fathom = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))

# Get sprint data
sprint_id = "123"
sprint = jira.get_sprint_by_id(sprint_id)
metrics = jira.get_sprint_metrics(sprint_id)

# Get meetings during sprint
meetings = fathom.get_sprint_meetings(
    start_date=sprint['startDate'],
    end_date=sprint['endDate'],
    include_transcripts=True,
    include_summaries=True
)

# Generate report data
report_data = {
    'sprint': {
        'name': sprint['name'],
        'start': sprint['startDate'],
        'end': sprint['endDate'],
        'goal': sprint.get('goal', ''),
    },
    'metrics': {
        'total_issues': metrics['total_issues'],
        'completed': metrics['completed'],
        'completion_rate': metrics['completion_rate'],
        'total_story_points': metrics['total_story_points'],
        'completed_story_points': metrics['completed_story_points'],
    },
    'meetings': [
        {
            'title': m['title'],
            'date': m['start_time'],
            'summary': m.get('summary', ''),
            'transcript_segments': len(m.get('transcript', [])),
        }
        for m in meetings
    ]
}

print(f"Sprint Report: {report_data['sprint']['name']}")
print(f"Completion: {report_data['metrics']['completion_rate']}%")
print(f"Meetings: {len(report_data['meetings'])}")
```

## API Reference

### JiraClient

#### `__init__(base_url: str, email: str, api_token: str)`

Initialize JIRA client with authentication credentials.

**Parameters:**
- `base_url`: JIRA instance URL (e.g., https://your-domain.atlassian.net)
- `email`: JIRA account email
- `api_token`: JIRA API token

#### `get_sprint_by_id(sprint_id: str) -> Dict`

Fetch sprint metadata by ID.

**Returns:**
- `id`: Sprint ID
- `name`: Sprint name
- `state`: Sprint state (active, closed, future)
- `startDate`: Sprint start date (ISO 8601)
- `endDate`: Sprint end date (ISO 8601)
- `goal`: Sprint goal description

#### `get_sprint_issues(sprint_id: str, fields: Optional[List[str]]) -> List[Dict]`

Fetch all issues in sprint with automatic pagination.

**Returns:**
List of issue dictionaries with fields like key, summary, status, assignee, story points.

#### `get_active_sprint(board_id: int) -> Optional[Dict]`

Get currently active sprint for a board.

**Returns:**
Sprint dictionary or None if no active sprint.

#### `get_sprint_metrics(sprint_id: str) -> Dict`

Calculate sprint metrics based on issues.

**Returns:**
- `total_issues`: Total issue count
- `completed`: Completed issue count
- `in_progress`: In-progress issue count
- `todo`: Todo issue count
- `completion_rate`: Percentage complete (0-100)
- `total_story_points`: Sum of all story points
- `completed_story_points`: Sum of completed story points
- `story_point_completion_rate`: Percentage of points complete
- `issues_by_type`: Dictionary of counts by issue type
- `issues_by_status`: Dictionary of counts by status

### FathomClient

#### `__init__(api_key: str)`

Initialize Fathom client with API key.

**Parameters:**
- `api_key`: Fathom API key from settings

#### `list_meetings(start_date: str, end_date: str, recorded_by: Optional[str], include_transcript: bool) -> List[Dict]`

List meetings within date range.

**Parameters:**
- `start_date`: Start date (ISO 8601, e.g., "2025-12-01T00:00:00Z")
- `end_date`: End date (ISO 8601)
- `recorded_by`: Filter by email (optional)
- `include_transcript`: Include transcript in response

**Returns:**
List of meeting dictionaries with title, start_time, duration, participants, etc.

#### `get_meeting_details(meeting_id: str) -> Optional[Dict]`

Get detailed information about a specific meeting.

**Returns:**
Meeting dictionary or None if not found.

#### `get_meeting_transcript(recording_id: str) -> List[Dict]`

Fetch transcript for a meeting.

**Returns:**
List of transcript segments with speaker, text, and timestamp.

#### `get_meeting_summary(recording_id: str) -> str`

Fetch AI-generated summary for a meeting.

**Returns:**
Summary text in markdown format.

#### `get_sprint_meetings(start_date: str, end_date: str, include_transcripts: bool, include_summaries: bool) -> List[Dict]`

Convenience method to fetch all meetings with enriched data.

**Returns:**
List of enriched meeting dictionaries with transcripts and summaries.

## Error Handling

Both clients provide custom exception classes for different error scenarios:

### JIRA Exceptions

```python
from api import (
    JiraAPIError,              # Base exception
    JiraAuthenticationError,   # 401 - Invalid credentials
    JiraPermissionError,       # 403 - Insufficient permissions
    JiraNotFoundError,         # 404 - Resource not found
)

try:
    sprint = jira.get_sprint_by_id("123")
except JiraAuthenticationError:
    print("Invalid JIRA credentials. Check your API token.")
except JiraPermissionError:
    print("You don't have access to this sprint.")
except JiraNotFoundError:
    print("Sprint not found. Check the ID.")
except JiraAPIError as e:
    print(f"API error: {e}")
```

### Fathom Exceptions

```python
from api import (
    FathomAPIError,              # Base exception
    FathomAuthenticationError,   # 401 - Invalid API key
    FathomNotFoundError,         # 404 - Resource not found
    FathomRateLimitError,        # 429 - Rate limit exceeded
)

try:
    meetings = fathom.list_meetings(start_date="...", end_date="...")
except FathomAuthenticationError:
    print("Invalid Fathom API key.")
except FathomRateLimitError:
    print("Rate limit exceeded. Wait before retrying.")
except FathomAPIError as e:
    print(f"API error: {e}")
```

## Context Manager Support

Both clients support context manager protocol for automatic cleanup:

```python
with JiraClient(base_url, email, api_token) as jira:
    sprint = jira.get_sprint_by_id("123")
    # Session automatically closed when exiting

with FathomClient(api_key) as fathom:
    meetings = fathom.list_meetings(start_date, end_date)
    # Session automatically closed when exiting
```

## Logging

Both clients use Python's standard logging module. Configure logging in your application:

```python
import logging

# Enable debug logging for API clients
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Or configure specific loggers
logging.getLogger('api.jira_client').setLevel(logging.INFO)
logging.getLogger('api.fathom_client').setLevel(logging.DEBUG)
```

## Best Practices

1. **Use Environment Variables**: Never hardcode API credentials
2. **Handle Exceptions**: Always catch and handle API exceptions appropriately
3. **Use Context Managers**: Ensure sessions are properly closed
4. **Enable Logging**: Use logging for debugging and monitoring
5. **Validate Input**: Check date formats and IDs before making API calls
6. **Respect Rate Limits**: Handle rate limit errors gracefully
7. **Cache Results**: Cache API responses when appropriate to reduce calls

## Testing

Example test to verify clients are working:

```python
import os
from dotenv import load_dotenv
from api import JiraClient, FathomClient

load_dotenv()

def test_jira_client():
    """Test JIRA client connectivity."""
    client = JiraClient(
        base_url=os.getenv('JIRA_BASE_URL'),
        email=os.getenv('JIRA_EMAIL'),
        api_token=os.getenv('JIRA_API_TOKEN')
    )

    # Test with a known board ID
    board_id = 1  # Replace with your board ID
    sprint = client.get_active_sprint(board_id)

    if sprint:
        print(f"✓ JIRA client working: {sprint['name']}")
    else:
        print("✓ JIRA client working (no active sprint)")

def test_fathom_client():
    """Test Fathom client connectivity."""
    from datetime import datetime, timedelta

    client = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))

    # Test with recent date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    meetings = client.list_meetings(
        start_date=start_date.isoformat() + 'Z',
        end_date=end_date.isoformat() + 'Z'
    )

    print(f"✓ Fathom client working: {len(meetings)} meetings found")

if __name__ == '__main__':
    test_jira_client()
    test_fathom_client()
```

## Troubleshooting

### JIRA Issues

**401 Unauthorized:**
- Verify email and API token are correct
- Generate a new API token if needed
- Check that token has not expired

**403 Forbidden:**
- Verify you have permission to access the sprint/board
- Contact JIRA admin for required permissions

**404 Not Found:**
- Verify sprint/board ID is correct
- Check that resource exists and you have access

### Fathom Issues

**401 Unauthorized:**
- Verify API key is correct
- Generate a new API key from Fathom settings

**429 Rate Limited:**
- Wait before making more requests
- Implement exponential backoff for retries
- Contact Fathom support if limits are too restrictive

**Empty Results:**
- Verify date range is correct
- Check that meetings exist in the specified range
- Ensure meetings are shared with you

## Support

For issues or questions:

1. Check error messages for specific guidance
2. Review API documentation:
   - JIRA: https://developer.atlassian.com/cloud/jira/software/rest/
   - Fathom: https://developers.fathom.ai/quickstart
3. Enable debug logging to see detailed API interactions
4. Contact API support if needed

## License

This code is part of the Sprint Report Service project.
