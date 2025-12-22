"""
PDF Generator Service

Converts Markdown and HTML content to professional PDF documents using WeasyPrint.
Includes template rendering capabilities with Jinja2 for branded report generation.

Features:
- Markdown to PDF conversion
- HTML to PDF conversion with CSS3 support
- Template rendering with metadata injection
- Professional page layout with headers/footers
- UTF-8 encoding support
- Windows compatibility

Dependencies:
- weasyprint: HTML to PDF rendering engine
- jinja2: Template engine
- markdown: Markdown to HTML converter
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime

# WeasyPrint is imported lazily inside functions that use it
# This allows the module to load even if WeasyPrint/GTK3 is not available
WEASYPRINT_AVAILABLE = None  # None = not yet checked, True = available, False = unavailable
WEASYPRINT_ERROR = None

from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound
import markdown

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDFGeneratorError(Exception):
    """Base exception for PDF generation errors."""
    pass


class WeasyPrintNotAvailableError(PDFGeneratorError):
    """Raised when WeasyPrint is not available or cannot be imported."""
    pass


class TemplateRenderError(PDFGeneratorError):
    """Raised when template rendering fails."""
    pass


def check_weasyprint_availability() -> None:
    """
    Check if WeasyPrint is available and properly configured.

    This function attempts to import WeasyPrint on first call and caches the result.
    Subsequent calls use the cached result for performance.

    Raises:
        WeasyPrintNotAvailableError: If WeasyPrint cannot be imported or is misconfigured
    """
    global WEASYPRINT_AVAILABLE, WEASYPRINT_ERROR

    # Try importing WeasyPrint if we haven't checked yet
    if WEASYPRINT_AVAILABLE is None:
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            WEASYPRINT_AVAILABLE = True
            logger.info("WeasyPrint is available and ready")
        except ImportError as e:
            WEASYPRINT_AVAILABLE = False
            WEASYPRINT_ERROR = str(e)
            logger.warning(f"WeasyPrint import failed: {e}")

    # Raise error if WeasyPrint is not available
    if not WEASYPRINT_AVAILABLE:
        error_msg = (
            f"WeasyPrint is not available: {WEASYPRINT_ERROR}\n\n"
            "Installation instructions:\n"
            "1. Windows: Install GTK3 runtime from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer\n"
            "2. pip install weasyprint\n\n"
            "Alternative: Use weasyprint==58.1 which has fewer dependencies:\n"
            "pip install weasyprint==58.1"
        )
        logger.error(error_msg)
        raise WeasyPrintNotAvailableError(error_msg)


def get_template_dir() -> Path:
    """
    Get the templates directory path.

    Returns:
        Path: Absolute path to templates directory
    """
    # Get the directory containing this file (services/)
    services_dir = Path(__file__).parent
    # Go up one level to project root, then into templates/
    template_dir = services_dir.parent / 'templates'

    if not template_dir.exists():
        logger.warning(f"Templates directory not found: {template_dir}")
        template_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created templates directory: {template_dir}")

    return template_dir


def get_output_dir(output_type: str = 'pdfs') -> Path:
    """
    Get the output directory path for PDFs or HTML files.

    Args:
        output_type: Type of output ('pdfs' or 'html')

    Returns:
        Path: Absolute path to output directory
    """
    services_dir = Path(__file__).parent
    output_dir = services_dir.parent / 'output' / output_type

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")

    return output_dir


def markdown_to_html(markdown_content: str) -> str:
    """
    Convert Markdown content to HTML.

    Args:
        markdown_content: Markdown text to convert

    Returns:
        str: HTML content
    """
    md = markdown.Markdown(extensions=[
        'extra',      # Tables, fenced code blocks, etc.
        'nl2br',      # Convert newlines to <br>
        'sane_lists', # Better list handling
        'toc',        # Table of contents
        'codehilite'  # Syntax highlighting
    ])

    html_content = md.convert(markdown_content)
    logger.debug(f"Converted {len(markdown_content)} chars of Markdown to {len(html_content)} chars of HTML")

    return html_content


def render_report_template(
    template_name: str = 'report_template.html',
    report_content: str = '',
    metadata: Optional[Dict[str, Any]] = None,
    is_markdown: bool = True
) -> str:
    """
    Render a report template with provided content and metadata.

    Args:
        template_name: Name of the Jinja2 template file
        report_content: Main report content (Markdown or HTML)
        metadata: Dictionary of metadata to inject into template
        is_markdown: If True, convert report_content from Markdown to HTML

    Returns:
        str: Rendered HTML content

    Raises:
        TemplateRenderError: If template rendering fails
        TemplateNotFound: If template file doesn't exist
    """
    try:
        template_dir = get_template_dir()

        # Set up Jinja2 environment
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True  # XSS protection
        )

        # Load template
        template = env.get_template(template_name)
        logger.info(f"Loaded template: {template_name}")

        # Convert Markdown to HTML if needed
        if is_markdown and report_content:
            report_content = markdown_to_html(report_content)

        # Prepare template variables
        template_vars = {
            'report_content': report_content,
            'metadata': metadata or {},
            'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'current_year': datetime.now().year
        }

        # Merge in any additional metadata
        if metadata:
            template_vars.update(metadata)

        # Render template
        rendered_html = template.render(**template_vars)
        logger.info(f"Successfully rendered template with {len(rendered_html)} chars")

        return rendered_html

    except TemplateNotFound as e:
        error_msg = f"Template not found: {template_name} in {template_dir}"
        logger.error(error_msg)
        raise TemplateNotFound(error_msg)

    except Exception as e:
        error_msg = f"Failed to render template {template_name}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise TemplateRenderError(error_msg)


def generate_pdf_from_html(
    html_content: str,
    output_path: Union[str, Path],
    base_url: Optional[str] = None,
    stylesheets: Optional[list] = None
) -> Path:
    """
    Generate a PDF file from HTML content.

    Args:
        html_content: HTML string to convert to PDF
        output_path: Path where PDF should be saved
        base_url: Base URL for resolving relative URLs in HTML
        stylesheets: List of CSS files or CSS objects to apply

    Returns:
        Path: Absolute path to generated PDF file

    Raises:
        WeasyPrintNotAvailableError: If WeasyPrint is not available
        PDFGeneratorError: If PDF generation fails
    """
    check_weasyprint_availability()

    # Import WeasyPrint classes (only when PDF generation is actually needed)
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration

    try:
        output_path = Path(output_path)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Configure font handling
        font_config = FontConfiguration()

        # Create HTML document
        html_doc = HTML(string=html_content, base_url=base_url)

        # Prepare stylesheets
        css_list = []
        if stylesheets:
            for stylesheet in stylesheets:
                if isinstance(stylesheet, str):
                    # Treat as CSS file path
                    css_list.append(CSS(filename=stylesheet, font_config=font_config))
                else:
                    # Assume it's a CSS object
                    css_list.append(stylesheet)

        # Generate PDF
        logger.info(f"Generating PDF: {output_path}")
        html_doc.write_pdf(
            output_path,
            stylesheets=css_list,
            font_config=font_config
        )

        # Verify file was created
        if not output_path.exists():
            raise PDFGeneratorError(f"PDF file was not created: {output_path}")

        file_size = output_path.stat().st_size
        logger.info(f"Successfully generated PDF: {output_path} ({file_size:,} bytes)")

        return output_path.absolute()

    except WeasyPrintNotAvailableError:
        raise

    except Exception as e:
        error_msg = f"Failed to generate PDF: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise PDFGeneratorError(error_msg)


def generate_pdf_from_markdown(
    markdown_content: str,
    output_path: Union[str, Path],
    template_name: str = 'csg_sprint_report_template.html',
    metadata: Optional[Dict[str, Any]] = None,
    save_html: bool = True
) -> Dict[str, Path]:
    """
    Generate a PDF file from Markdown content using a template.

    This is the high-level function that combines:
    1. Markdown to HTML conversion
    2. Template rendering with metadata
    3. HTML to PDF conversion

    Args:
        markdown_content: Markdown text to convert
        output_path: Path where PDF should be saved
        template_name: Name of Jinja2 template to use
        metadata: Dictionary of metadata for template
        save_html: If True, also save rendered HTML file

    Returns:
        Dict with keys:
            - 'pdf_path': Path to generated PDF
            - 'html_path': Path to HTML file (if save_html=True)

    Raises:
        WeasyPrintNotAvailableError: If WeasyPrint is not available
        TemplateRenderError: If template rendering fails
        PDFGeneratorError: If PDF generation fails
    """
    try:
        output_path = Path(output_path)

        # Render HTML from template
        html_content = render_report_template(
            template_name=template_name,
            report_content=markdown_content,
            metadata=metadata,
            is_markdown=True
        )

        # Save HTML file if requested
        html_path = None
        if save_html:
            html_path = output_path.with_suffix('.html')
            html_path.write_text(html_content, encoding='utf-8')
            logger.info(f"Saved HTML file: {html_path}")

        # Generate PDF
        pdf_path = generate_pdf_from_html(
            html_content=html_content,
            output_path=output_path
        )

        result = {'pdf_path': pdf_path}
        if html_path:
            result['html_path'] = html_path

        return result

    except (WeasyPrintNotAvailableError, TemplateRenderError, PDFGeneratorError):
        raise

    except Exception as e:
        error_msg = f"Failed to generate PDF from Markdown: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise PDFGeneratorError(error_msg)


# Convenience function for testing
def generate_sample_pdf(output_filename: str = 'sample_report.pdf') -> Dict[str, Path]:
    """
    Generate a sample PDF for testing purposes.

    Args:
        output_filename: Name of output PDF file

    Returns:
        Dict with paths to generated files
    """
    sample_markdown = """
# Sprint Report: Sample Sprint

## Overview
This is a sample sprint report to demonstrate PDF generation capabilities.

## Sprint Summary
- **Sprint ID**: SPRINT-001
- **Sprint Name**: Sample Sprint Q4 2025
- **Start Date**: 2025-10-01
- **End Date**: 2025-10-14
- **Team**: Engineering Team Alpha

## Key Achievements
1. Implemented PDF generation service
2. Created professional report templates
3. Integrated with WeasyPrint for high-quality output

## Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Story Points | 40 | 42 |  Exceeded |
| Bugs Fixed | 10 | 12 |  Exceeded |
| Code Coverage | 85% | 87% |  Met |

## Team Feedback
The team demonstrated excellent collaboration and delivered beyond expectations.

## Next Steps
- Continue momentum into next sprint
- Address technical debt items
- Plan Q1 2026 roadmap
"""

    metadata = {
        'sprint_id': 'SPRINT-001',
        'sprint_name': 'Sample Sprint Q4 2025',
        'start_date': '2025-10-01',
        'end_date': '2025-10-14',
        'team_name': 'Engineering Team Alpha'
    }

    output_dir = get_output_dir('pdfs')
    output_path = output_dir / output_filename

    return generate_pdf_from_markdown(
        markdown_content=sample_markdown,
        output_path=output_path,
        metadata=metadata,
        save_html=True
    )


if __name__ == '__main__':
    """Test PDF generation when run directly."""
    try:
        logger.info("Starting PDF generator test...")
        result = generate_sample_pdf()

        print("\n" + "="*60)
        print("PDF Generation Test - SUCCESS")
        print("="*60)
        print(f"\nGenerated files:")
        print(f"  PDF:  {result['pdf_path']}")
        if 'html_path' in result:
            print(f"  HTML: {result['html_path']}")
        print(f"\nOpen the PDF file to verify output quality.")
        print("="*60 + "\n")

    except Exception as e:
        print("\n" + "="*60)
        print("PDF Generation Test - FAILED")
        print("="*60)
        print(f"\nError: {str(e)}")
        print("\nCheck logs for details.")
        print("="*60 + "\n")
        logger.error("Test failed", exc_info=True)
        raise
