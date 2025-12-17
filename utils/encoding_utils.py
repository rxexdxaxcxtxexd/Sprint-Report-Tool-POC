"""
UTF-8 encoding utilities for Windows console compatibility.

Ensures proper UTF-8 handling across Windows console, Python, and Docker containers.
"""
import sys
import os


def ensure_utf8_console():
    """Ensure console is configured for UTF-8 on Windows.

    This function:
    - Sets Windows console code page to UTF-8 (chcp 65001)
    - Reconfigures Python's stdout/stderr to use UTF-8 encoding
    - Handles non-Windows platforms gracefully

    Called at application startup to prevent UnicodeEncodeError and
    garbled character output when displaying non-ASCII content.
    """
    if sys.platform == 'win32':
        # Set console code page to UTF-8
        os.system('chcp 65001 >nul 2>&1')

        # Set Python's default encoding (Python 3.7+)
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
