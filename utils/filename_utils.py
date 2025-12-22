"""
Filename sanitization utilities for cross-platform compatibility.

Ensures filenames are safe for Windows, Linux, and macOS filesystems.
Specifically addresses the NTFS Alternate Data Stream issue caused by colons
in filenames like "BOPS: Sprint 11".
"""
import re
import unicodedata


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """Sanitize a filename by replacing invalid characters.

    Handles:
    - Windows reserved chars: < > : " / \\ | ? *
    - Colons (common in sprint names like "BOPS: Sprint 11")
    - Unicode normalization
    - Control characters (0x00-0x1F)
    - Trailing dots and spaces (Windows restriction)

    Args:
        filename: Raw filename (may contain colons, spaces, etc.)
        max_length: Maximum filename length (default: 200)

    Returns:
        Safe filename string

    Examples:
        >>> sanitize_filename("BOPS: Sprint 11")
        'BOPS-Sprint-11'
        >>> sanitize_filename("Q4/FY25: Final Report")
        'Q4_FY25-Final-Report'
        >>> sanitize_filename("Test<>Report")
        'Test__Report'
        >>> sanitize_filename("  Name  ")
        'Name'
    """
    if not filename:
        return "untitled"

    # Normalize unicode (handle accented characters)
    filename = unicodedata.normalize('NFKD', filename)
    filename = filename.encode('ascii', 'ignore').decode('ascii')

    # Replace colon with hyphen (most common issue - prevents NTFS ADS)
    filename = filename.replace(':', '-')

    # Replace other Windows reserved characters with underscore
    filename = re.sub(r'[<>"/\\|?*]', '_', filename)

    # Remove control characters (0x00-0x1F)
    filename = ''.join(c for c in filename if ord(c) >= 32)

    # Trim trailing dots and spaces (Windows restriction)
    filename = filename.strip('. ')

    # Replace multiple spaces/hyphens with single
    filename = re.sub(r'[-\s]+', '-', filename)

    # Limit length
    if len(filename) > max_length:
        filename = filename[:max_length].rstrip('-_')

    return filename or 'report'


def generate_report_filename(sprint_name: str, sprint_id: int) -> str:
    """Generate safe PDF filename for sprint reports.

    Args:
        sprint_name: Sprint name (may contain unsafe characters)
        sprint_id: Numeric sprint ID

    Returns:
        Safe filename with .pdf extension

    Examples:
        >>> generate_report_filename("BOPS: Sprint 11", 2239)
        'BOPS-Sprint-11_2239.pdf'
        >>> generate_report_filename("Q4/FY25: Final", 123)
        'Q4_FY25-Final_123.pdf'
    """
    safe_name = sanitize_filename(sprint_name)
    return f"{safe_name}_{sprint_id}.pdf"


# Test cases (for manual verification)
if __name__ == "__main__":
    test_cases = [
        ("BOPS: Sprint 11", "BOPS-Sprint-11"),
        ("Q4/FY25: Final", "Q4_FY25-Final"),
        ("Test<>Report", "Test__Report"),
        ("  Name  ", "Name"),
        ("Report|with*special?chars", "Report_with_special_chars"),
    ]

    print("Testing filename sanitization:")
    for input_name, expected in test_cases:
        result = sanitize_filename(input_name)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{input_name}' → '{result}' (expected: '{expected}')")

    print("\nTesting report filename generation:")
    print(f"  '{generate_report_filename('BOPS: Sprint 11', 2239)}'")
