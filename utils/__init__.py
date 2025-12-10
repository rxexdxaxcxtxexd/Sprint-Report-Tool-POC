"""
Utility modules for Sprint Report Service.

This package provides utility functions and classes for:
- Configuration management (config_loader)
- DOCX parsing (docx_parser)

Example usage:
    from utils import ConfigLoader, parse_sprint_guide

    # Load configuration
    config = ConfigLoader("config.yaml")
    api_key = config.get_env_var("ANTHROPIC_API_KEY", required=True)

    # Parse Sprint Report Guide
    guide_content = parse_sprint_guide("guide.docx")
    sections = extract_sections("guide.docx")
"""

from .config_loader import (
    ConfigLoader,
    ConfigurationError,
    load_config,
    get_board_config,
    get_env_var,
    get_claude_config,
    get_sprint_guide_path,
    get_config
)

from .docx_parser import (
    DOCXParsingError,
    parse_sprint_guide,
    extract_sections,
    validate_guide,
    get_section,
    get_document_stats,
    EXPECTED_SECTIONS
)

__all__ = [
    # Configuration
    'ConfigLoader',
    'ConfigurationError',
    'load_config',
    'get_board_config',
    'get_env_var',
    'get_claude_config',
    'get_sprint_guide_path',
    'get_config',
    # DOCX Parsing
    'DOCXParsingError',
    'parse_sprint_guide',
    'extract_sections',
    'validate_guide',
    'get_section',
    'get_document_stats',
    'EXPECTED_SECTIONS',
]

__version__ = '1.0.0'
