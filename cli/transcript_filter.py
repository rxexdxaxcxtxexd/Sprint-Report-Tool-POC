"""
Fathom Transcript Filtering - Smart search and ranking.

Provides intelligent filtering of Fathom transcripts based on search terms,
ranking them by confidence level (high/medium/low).
"""
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class FilteredTranscript:
    """Fathom transcript with confidence ranking."""
    meeting_id: str
    title: str
    date: str
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'
    match_type: str  # 'title_match', 'content_match', 'none'
    raw_data: Dict[str, Any]


def filter_transcripts_smart(
    transcripts: List[Dict[str, Any]],
    search_terms: List[str] = None
) -> Dict[str, List[FilteredTranscript]]:
    """Filter and rank transcripts by relevance to search terms.

    Args:
        transcripts: List of transcript dictionaries from Fathom API
        search_terms: Terms to search for (default: ['ibobs', 'ibops'])

    Returns:
        Dictionary with keys:
        - 'high_confidence': Transcripts with search terms in title
        - 'medium_confidence': Transcripts with terms in content
        - 'other': All other transcripts

    Examples:
        >>> transcripts = [
        ...     {'title': 'iBOPS Sprint Planning', 'date': '2024-12-01'},
        ...     {'title': 'Team Sync', 'date': '2024-12-02'}
        ... ]
        >>> filtered = filter_transcripts_smart(transcripts)
        >>> len(filtered['high_confidence'])
        1
    """
    if search_terms is None:
        search_terms = ['ibobs', 'ibops', 'ibop', 'ibob']

    high_confidence = []
    medium_confidence = []
    other = []

    # Normalize search terms to lowercase
    search_terms_lower = [term.lower() for term in search_terms]

    for transcript in transcripts:
        title = transcript.get('title', '').lower()
        meeting_id = transcript.get('id', str(transcript.get('recording_id', 'unknown')))
        date = transcript.get('date', transcript.get('created_at', 'Unknown'))

        # High confidence: keyword in meeting title
        if any(term in title for term in search_terms_lower):
            filtered = FilteredTranscript(
                meeting_id=meeting_id,
                title=transcript.get('title', 'Untitled'),
                date=date,
                confidence='HIGH',
                match_type='title_match',
                raw_data=transcript
            )
            high_confidence.append(filtered)

        # Medium confidence: would check transcript content
        # (requires downloading full transcript - expensive operation)
        # For MVP, we'll skip this and let user manually review

        # Low confidence: everything else
        else:
            filtered = FilteredTranscript(
                meeting_id=meeting_id,
                title=transcript.get('title', 'Untitled'),
                date=date,
                confidence='LOW',
                match_type='none',
                raw_data=transcript
            )
            other.append(filtered)

    return {
        'high_confidence': high_confidence,
        'medium_confidence': medium_confidence,  # Empty for MVP
        'other': other
    }


def parse_selection(
    selection: str,
    filtered_transcripts: Dict[str, List[FilteredTranscript]]
) -> List[FilteredTranscript]:
    """Parse user selection input and return selected transcripts.

    Args:
        selection: User input string (e.g., '1,2,5' or 'all' or 'none' or 'all high')
        filtered_transcripts: Dictionary from filter_transcripts_smart()

    Returns:
        List of selected FilteredTranscript objects

    Examples:
        >>> selection = "1,2,5"
        >>> # Returns transcripts at indices 0, 1, 4 (0-indexed)

        >>> selection = "all high"
        >>> # Returns all high confidence transcripts

        >>> selection = "none"
        >>> # Returns empty list
    """
    selection = selection.lower().strip()

    # Flatten all transcripts for indexing
    all_transcripts = (
        filtered_transcripts['high_confidence'] +
        filtered_transcripts['medium_confidence'] +
        filtered_transcripts['other']
    )

    # Handle special cases
    if selection == 'none' or selection == '':
        return []

    if selection == 'all':
        return all_transcripts

    if 'all high' in selection or selection == 'high':
        return filtered_transcripts['high_confidence']

    if 'all medium' in selection or selection == 'medium':
        return filtered_transcripts['medium_confidence']

    # Parse comma-separated indices
    try:
        # Remove spaces and split by comma
        indices = [int(idx.strip()) for idx in selection.split(',')]

        # Convert to 0-indexed and filter valid indices
        selected = []
        for idx in indices:
            array_idx = idx - 1  # User sees 1-indexed, we use 0-indexed
            if 0 <= array_idx < len(all_transcripts):
                selected.append(all_transcripts[array_idx])

        return selected

    except ValueError:
        # Invalid input format
        return []


def get_transcript_display_index(
    transcript: FilteredTranscript,
    filtered_transcripts: Dict[str, List[FilteredTranscript]]
) -> int:
    """Get the display index (1-indexed) for a transcript.

    Args:
        transcript: Transcript to find index for
        filtered_transcripts: Dictionary from filter_transcripts_smart()

    Returns:
        Display index (1-indexed), or -1 if not found
    """
    all_transcripts = (
        filtered_transcripts['high_confidence'] +
        filtered_transcripts['medium_confidence'] +
        filtered_transcripts['other']
    )

    try:
        return all_transcripts.index(transcript) + 1  # 1-indexed for display
    except ValueError:
        return -1


if __name__ == "__main__":
    """Test transcript filtering."""
    # Sample test data
    test_transcripts = [
        {'id': '1', 'title': 'iBOPS Sprint Planning Meeting', 'date': '2024-12-01'},
        {'id': '2', 'title': 'IBOPS Technical Review', 'date': '2024-12-02'},
        {'id': '3', 'title': 'Team Sync Meeting', 'date': '2024-12-03'},
        {'id': '4', 'title': 'Daily Standup', 'date': '2024-12-04'},
    ]

    print("Testing transcript filtering:")
    filtered = filter_transcripts_smart(test_transcripts)

    print(f"\nHigh Confidence ({len(filtered['high_confidence'])}):")
    for t in filtered['high_confidence']:
        print(f"  - {t.title}")

    print(f"\nOther ({len(filtered['other'])}):")
    for t in filtered['other']:
        print(f"  - {t.title}")

    print("\nTesting selection parsing:")
    print(f"  'all high' → {len(parse_selection('all high', filtered))} transcripts")
    print(f"  '1,2' → {len(parse_selection('1,2', filtered))} transcripts")
    print(f"  'none' → {len(parse_selection('none', filtered))} transcripts")
