"""
Sprint Report Service - Services Package

This package contains core services for generating sprint reports:
- pdf_generator: PDF generation from Markdown/HTML
- report_generator: High-level report generation orchestrator
"""

from .pdf_generator import (
    generate_pdf_from_markdown,
    generate_pdf_from_html,
    render_report_template
)

from .report_generator import (
    generate_report,
    process_sprint_report_async
)

__all__ = [
    'generate_pdf_from_markdown',
    'generate_pdf_from_html',
    'render_report_template',
    'generate_report',
    'process_sprint_report_async'
]

__version__ = '1.0.0'
