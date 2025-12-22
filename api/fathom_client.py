"""
Fathom Video API Client for Sprint Report Service.

This module provides a production-ready client for interacting with Fathom's API
to fetch meeting recordings, transcripts, and AI-generated summaries.

Example usage:
    from api.fathom_client import FathomClient
    from datetime import datetime, timedelta

    # Initialize client
    client = FathomClient(api_key="your-fathom-api-key")

    # Fetch meetings from last sprint (2 weeks)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)

    meetings = client.list_meetings(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )

    # Get detailed info for each meeting
    for meeting in meetings:
        transcript = client.get_meeting_transcript(meeting['id'])
        summary = client.get_meeting_summary(meeting['id'])
        print(f"Meeting: {meeting['title']}")
        print(f"Summary: {summary}")
"""

import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


# Configure module logger
logger = logging.getLogger(__name__)


class FathomAPIError(Exception):
    """Base exception for Fathom API errors."""
    pass


class FathomAuthenticationError(FathomAPIError):
    """Raised when authentication fails."""
    pass


class FathomNotFoundError(FathomAPIError):
    """Raised when resource is not found."""
    pass


class FathomRateLimitError(FathomAPIError):
    """Raised when rate limit is exceeded."""
    pass


class FathomClient:
    """
    Client for interacting with Fathom Video API.

    This client provides methods to fetch meeting data, transcripts, and summaries
    from Fathom's meeting assistant platform.

    Attributes:
        api_key (str): Fathom API key
        base_url (str): Fathom API base URL
        session (requests.Session): Reusable HTTP session
    """

    BASE_URL = "https://api.fathom.ai/external/v1"

    def __init__(self, api_key: str):
        """
        Initialize Fathom client.

        Args:
            api_key: Fathom API key (generate from User Settings > API Access)

        Raises:
            ValueError: If api_key is empty or invalid
        """
        if not api_key or not isinstance(api_key, str):
            raise ValueError("api_key must be a non-empty string")

        self.api_key = api_key
        self.base_url = self.BASE_URL

        # Create reusable session with authentication
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        logger.info(f"Initialized Fathom client for {self.base_url}")

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Union[Dict[str, Any], List[Any]]:
        """
        Make GET request to Fathom API.

        Args:
            endpoint: API endpoint (e.g., /meetings)
            params: Optional query parameters

        Returns:
            JSON response as dictionary or list

        Raises:
            FathomAuthenticationError: Invalid API key (401)
            FathomNotFoundError: Resource not found (404)
            FathomRateLimitError: Rate limit exceeded (429)
            FathomAPIError: Other API errors (500, network issues)
        """
        url = f"{self.base_url}{endpoint}"

        try:
            logger.debug(f"GET {url} with params={params}")
            response = self.session.get(url, params=params, timeout=30)

            # Handle specific error cases
            if response.status_code == 401:
                raise FathomAuthenticationError(
                    "Authentication failed. Invalid API key. "
                    "Generate a new key at: Fathom Settings > API Access"
                )
            elif response.status_code == 404:
                # For 404, return empty result instead of raising
                # This is expected when no meetings exist in date range
                logger.debug(f"Resource not found: {endpoint}")
                return [] if 'meetings' in endpoint or 'recordings' in endpoint else {}
            elif response.status_code == 429:
                raise FathomRateLimitError(
                    "Rate limit exceeded. Please wait before making more requests. "
                    "Check response headers for retry timing."
                )
            elif response.status_code >= 500:
                raise FathomAPIError(
                    f"Fathom server error ({response.status_code}). "
                    "The Fathom service may be temporarily unavailable. Try again later."
                )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise FathomAPIError(
                f"Request timed out after 30 seconds. Check your network connection."
            )
        except requests.exceptions.ConnectionError as e:
            raise FathomAPIError(
                f"Connection error: {str(e)}. Check your network connection."
            )
        except requests.exceptions.RequestException as e:
            if not isinstance(e, (FathomAuthenticationError, FathomNotFoundError, FathomRateLimitError)):
                raise FathomAPIError(f"Request failed: {str(e)}")
            raise

    def _paginate(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Handle pagination for Fathom API endpoints.

        Fathom uses cursor-based pagination. This method automatically follows
        pagination to retrieve all results.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            List of all results across all pages

        Raises:
            FathomAPIError: API request failed
        """
        all_results = []
        cursor = None
        params = params or {}

        logger.debug(f"Starting pagination for {endpoint}")

        while True:
            if cursor:
                params['cursor'] = cursor

            response = self._get(endpoint, params=params)

            # Handle both list and dict responses
            if isinstance(response, list):
                # Some endpoints return a list directly
                all_results.extend(response)
                break  # No pagination for list responses
            elif isinstance(response, dict):
                # Standard paginated response
                items = response.get('data', response.get('meetings', []))
                all_results.extend(items)

                # Check for next page
                cursor = response.get('next_cursor') or response.get('cursor')
                if not cursor:
                    break
            else:
                # Unexpected response format
                logger.warning(f"Unexpected response format: {type(response)}")
                break

            logger.debug(f"Retrieved {len(all_results)} results so far...")

        logger.debug(f"Pagination complete: {len(all_results)} total results")
        return all_results

    def list_meetings(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        recorded_by: Optional[str] = None,
        include_transcript: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List meetings within a date range.

        Args:
            start_date: Start date in ISO 8601 format (e.g., "2025-01-01T00:00:00Z")
            end_date: End date in ISO 8601 format
            recorded_by: Filter by email address of recorder (optional)
            include_transcript: Include transcript in response (default: False)

        Returns:
            List of meeting dictionaries, each containing:
                - id: Meeting/recording ID
                - title: Meeting title
                - meeting_title: Alternative title field
                - start_time: Meeting start time (ISO 8601)
                - end_time: Meeting end time (ISO 8601)
                - duration: Meeting duration in seconds
                - url: Fathom meeting URL
                - participants: List of participant dictionaries
                - transcript: Full transcript (if include_transcript=True)
                - summary: AI-generated summary
                - action_items: List of action items

        Raises:
            ValueError: Invalid date format
            FathomAPIError: API request failed

        Example:
            >>> meetings = client.list_meetings(
            ...     start_date="2025-12-01T00:00:00Z",
            ...     end_date="2025-12-14T23:59:59Z"
            ... )
            >>> for meeting in meetings:
            ...     print(f"{meeting['title']}: {meeting['start_time']}")
            Sprint Planning: 2025-12-02T14:00:00Z
            Daily Standup: 2025-12-03T09:00:00Z
        """
        params = {}

        # Validate and add date filters
        if start_date:
            try:
                # Validate ISO 8601 format
                datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                params['created_after'] = start_date
            except ValueError:
                raise ValueError(
                    f"Invalid start_date format: {start_date}. "
                    "Use ISO 8601 format (e.g., '2025-12-01T00:00:00Z')"
                )

        if end_date:
            try:
                datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                params['created_before'] = end_date
            except ValueError:
                raise ValueError(
                    f"Invalid end_date format: {end_date}. "
                    "Use ISO 8601 format (e.g., '2025-12-14T23:59:59Z')"
                )

        # Add email filter if provided
        if recorded_by:
            params['recorded_by[]'] = recorded_by

        # Add transcript flag if requested
        if include_transcript:
            params['include_transcript'] = 'true'

        logger.info(
            f"Listing meetings from {start_date or 'beginning'} to {end_date or 'now'}"
        )

        endpoint = "/meetings"
        meetings = self._paginate(endpoint, params=params)

        logger.info(f"Retrieved {len(meetings)} meetings")
        return meetings

    def get_meeting_details(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific meeting.

        Args:
            meeting_id: Meeting/recording ID

        Returns:
            Meeting dictionary with full details, or None if not found.
            Contains same fields as list_meetings().

        Raises:
            ValueError: Invalid meeting_id
            FathomAPIError: API request failed

        Example:
            >>> meeting = client.get_meeting_details("rec_abc123")
            >>> if meeting:
            ...     print(f"Meeting: {meeting['title']}")
            ...     print(f"Duration: {meeting['duration']} seconds")
            Meeting: Sprint Retrospective
            Duration: 3600
        """
        if not meeting_id or not isinstance(meeting_id, str):
            raise ValueError("meeting_id must be a non-empty string")

        logger.info(f"Fetching details for meeting {meeting_id}")

        # Fathom API doesn't have a direct get-by-id endpoint
        # We need to list meetings and filter, or use the recordings endpoint
        endpoint = f"/recordings/{meeting_id}"

        try:
            meeting = self._get(endpoint)
            if meeting:
                logger.info(f"Retrieved meeting: {meeting.get('title', 'Unknown')}")
            return meeting
        except FathomNotFoundError:
            logger.warning(f"Meeting {meeting_id} not found")
            return None

    def get_meeting_transcript(self, recording_id: str) -> List[Dict[str, Any]]:
        """
        Fetch transcript for a specific meeting.

        Args:
            recording_id: Recording ID (meeting ID)

        Returns:
            List of transcript segments, each containing:
                - speaker: Dictionary with display_name and email
                - text: Transcript text
                - timestamp: Timestamp in format "HH:MM:SS"

        Raises:
            ValueError: Invalid recording_id
            FathomNotFoundError: Recording not found
            FathomAPIError: API request failed

        Example:
            >>> transcript = client.get_meeting_transcript("rec_abc123")
            >>> for segment in transcript:
            ...     speaker = segment['speaker']['display_name']
            ...     text = segment['text']
            ...     timestamp = segment['timestamp']
            ...     print(f"[{timestamp}] {speaker}: {text}")
            [00:01:23] John Doe: Let's review the sprint goals
            [00:01:45] Jane Smith: We completed 8 out of 10 stories
        """
        if not recording_id or not isinstance(recording_id, str):
            raise ValueError("recording_id must be a non-empty string")

        logger.info(f"Fetching transcript for recording {recording_id}")

        endpoint = f"/recordings/{recording_id}/transcript"
        response = self._get(endpoint)

        # Handle different response formats
        if isinstance(response, list):
            transcript = response
        elif isinstance(response, dict):
            transcript = response.get('transcript', [])
        else:
            transcript = []

        logger.info(f"Retrieved transcript with {len(transcript)} segments")
        return transcript

    def get_meeting_summary(self, recording_id: str) -> str:
        """
        Fetch AI-generated summary for a meeting.

        Args:
            recording_id: Recording ID (meeting ID)

        Returns:
            Summary text in markdown format

        Raises:
            ValueError: Invalid recording_id
            FathomNotFoundError: Recording not found
            FathomAPIError: API request failed

        Example:
            >>> summary = client.get_meeting_summary("rec_abc123")
            >>> print(summary)
            # Sprint Retrospective

            ## Key Discussion Points
            - Team velocity increased by 20%
            - Need to improve code review process

            ## Action Items
            - [ ] Update sprint template
            - [ ] Schedule training session
        """
        if not recording_id or not isinstance(recording_id, str):
            raise ValueError("recording_id must be a non-empty string")

        logger.info(f"Fetching summary for recording {recording_id}")

        endpoint = f"/recordings/{recording_id}/summary"
        response = self._get(endpoint)

        # Extract summary text from response
        if isinstance(response, str):
            summary = response
        elif isinstance(response, dict):
            # Check various possible field names
            summary = (
                response.get('summary') or
                response.get('content') or
                response.get('markdown') or
                ""
            )
        else:
            summary = ""

        logger.info(f"Retrieved summary ({len(summary)} characters)")
        return summary


    def get_multiple_transcripts_concurrent(
        self,
        recording_ids: List[str],
        max_workers: int = 5
    ) -> List[Tuple[str, Optional[List[Dict[str, Any]]]]]:
        """
        Fetch transcripts for multiple recordings concurrently.

        This method uses ThreadPoolExecutor to fetch transcripts in parallel,
        dramatically improving performance when fetching multiple transcripts.

        Args:
            recording_ids: List of recording IDs to fetch
            max_workers: Maximum number of concurrent requests (default: 5)

        Returns:
            List of tuples: (recording_id, transcript or None if error)
            Order matches input recording_ids order

        Example:
            >>> recording_ids = ['rec_123', 'rec_456', 'rec_789']
            >>> results = client.get_multiple_transcripts_concurrent(recording_ids)
            >>> for rec_id, transcript in results:
            ...     if transcript:
            ...         print(f"{rec_id}: {len(transcript)} segments")
            ...     else:
            ...         print(f"{rec_id}: Failed to fetch")
            rec_123: 45 segments
            rec_456: 32 segments
            rec_789: Failed to fetch
        """
        if not recording_ids:
            return []

        logger.info(f"Fetching {len(recording_ids)} transcripts concurrently (max_workers={max_workers})")

        def fetch_single_transcript(rec_id: str) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
            """Fetch a single transcript, returning (id, transcript or None)."""
            try:
                transcript = self.get_meeting_transcript(rec_id)
                return (rec_id, transcript)
            except Exception as e:
                logger.warning(f"Failed to fetch transcript for {rec_id}: {e}")
                return (rec_id, None)

        # Use ThreadPoolExecutor for concurrent fetching
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_id = {
                executor.submit(fetch_single_transcript, rec_id): rec_id
                for rec_id in recording_ids
            }

            # Collect results as they complete
            for future in as_completed(future_to_id):
                rec_id, transcript = future.result()
                results.append((rec_id, transcript))

        # Sort results to match input order
        id_to_transcript = dict(results)
        ordered_results = [(rec_id, id_to_transcript.get(rec_id)) for rec_id in recording_ids]

        success_count = sum(1 for _, t in ordered_results if t is not None)
        logger.info(f"Successfully fetched {success_count}/{len(recording_ids)} transcripts")

        return ordered_results


    def get_sprint_meetings(
        self,
        start_date: str,
        end_date: str,
        include_transcripts: bool = True,
        include_summaries: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to fetch all meetings in a sprint with enriched data.

        This method combines multiple API calls to provide a complete view of
        sprint meetings including transcripts and summaries.

        Args:
            start_date: Sprint start date (ISO 8601)
            end_date: Sprint end date (ISO 8601)
            include_transcripts: Fetch transcript for each meeting (default: True)
            include_summaries: Fetch summary for each meeting (default: True)

        Returns:
            List of enriched meeting dictionaries with additional fields:
                - transcript: Full transcript (if include_transcripts=True)
                - summary: AI summary (if include_summaries=True)
                - All standard meeting fields from list_meetings()

        Raises:
            ValueError: Invalid date format
            FathomAPIError: API request failed

        Example:
            >>> meetings = client.get_sprint_meetings(
            ...     start_date="2025-12-01T00:00:00Z",
            ...     end_date="2025-12-14T23:59:59Z"
            ... )
            >>> for meeting in meetings:
            ...     print(f"Meeting: {meeting['title']}")
            ...     print(f"Summary: {meeting['summary'][:100]}...")
            ...     print(f"Transcript: {len(meeting['transcript'])} segments")
            Meeting: Sprint Planning
            Summary: The team discussed upcoming work and set sprint goals. Key priorities include...
            Transcript: 45 segments
        """
        logger.info(
            f"Fetching sprint meetings from {start_date} to {end_date} "
            f"(transcripts={include_transcripts}, summaries={include_summaries})"
        )

        # First, get all meetings in date range
        meetings = self.list_meetings(start_date=start_date, end_date=end_date)

        # Enrich meetings with transcripts and summaries (using concurrent fetching)
        if not meetings:
            return []

        # Extract meeting IDs
        meeting_ids = [m.get('id') for m in meetings if m.get('id')]

        # Fetch transcripts concurrently if requested
        transcript_map = {}
        if include_transcripts and meeting_ids:
            logger.info(f"Fetching {len(meeting_ids)} transcripts concurrently...")
            transcript_results = self.get_multiple_transcripts_concurrent(meeting_ids)
            transcript_map = {rec_id: transcript for rec_id, transcript in transcript_results}

        # Fetch summaries sequentially (TODO: make this concurrent too in future)
        summary_map = {}
        if include_summaries and meeting_ids:
            for meeting_id in meeting_ids:
                try:
                    summary = self.get_meeting_summary(meeting_id)
                    summary_map[meeting_id] = summary
                except FathomNotFoundError:
                    logger.warning(f"No summary found for meeting {meeting_id}")
                    summary_map[meeting_id] = ""
                except FathomAPIError as e:
                    logger.error(f"Error fetching summary for {meeting_id}: {e}")
                    summary_map[meeting_id] = ""

        # Build enriched meetings list
        enriched_meetings = []
        for meeting in meetings:
            meeting_id = meeting.get('id')

            if not meeting_id:
                logger.warning(f"Meeting missing ID: {meeting.get('title', 'Unknown')}")
                enriched_meetings.append(meeting)
                continue

            # Add transcript from concurrent fetch results
            if include_transcripts:
                meeting['transcript'] = transcript_map.get(meeting_id, [])

            # Add summary
            if include_summaries:
                meeting['summary'] = summary_map.get(meeting_id, "")

            enriched_meetings.append(meeting)

        logger.info(f"Enriched {len(enriched_meetings)} meetings with additional data")
        return enriched_meetings

    def close(self):
        """Close the HTTP session."""
        self.session.close()
        logger.info("Fathom client session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
