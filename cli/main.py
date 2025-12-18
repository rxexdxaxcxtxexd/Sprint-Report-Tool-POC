"""
Sprint Report CLI - Main entry point.

Interactive CLI tool for generating executive-level sprint reports with
JIRA MCP, Fathom transcripts, and Claude AI.
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel

from utils.config import load_config, validate_config
from utils.encoding_utils import ensure_utf8_console
from cli.interactive import (
    validate_config_interactive,
    select_sprint_interactive,
    confirm_sprint_dates_interactive,
    select_transcripts_interactive,
    review_report_interactive
)
from cli.jira_mcp import JiraMCPClient
from api.fathom_client import FathomClient


console = Console()


def main():
    """Main CLI entry point."""
    # Ensure UTF-8 console encoding (Windows compatibility)
    ensure_utf8_console()
    parser = argparse.ArgumentParser(
        description="Generate executive-level sprint reports with human-in-the-loop workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli/main.py              # Interactive mode (default)
  python cli/main.py --board 38   # Specify JIRA board ID
  python cli/main.py --help       # Show this help message

For more information, see README.md
        """
    )

    parser.add_argument(
        '--board',
        type=int,
        help='JIRA board ID (overrides config.yaml)'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to config.yaml (default: ./config.yaml)'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='Sprint Report CLI v1.0.0'
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = load_config(config_path=args.config)

        # Validate configuration
        validate_config_interactive(config)

        # Override board ID if specified
        board_id = args.board if args.board else config.jira.default_board_id


        # Ensure Docker is running (required for JIRA MCP)
        from utils.docker_helper import ensure_docker_running
        try:
            ensure_docker_running(auto_start=True, timeout=60)
        except FileNotFoundError as e:
            console.print(f"[red]Docker Desktop not installed:[/red]\n{e}")
            sys.exit(1)
        except TimeoutError as e:
            console.print(f"[yellow]Warning:[/yellow] {e}")
            console.print("[yellow]Continuing anyway - JIRA MCP may fail[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Docker check failed:[/yellow] {e}")
            console.print("[yellow]Continuing anyway - JIRA MCP may fail[/yellow]")
        # Initialize clients
        console.print("[dim]Initializing JIRA MCP client...[/dim]")
        with JiraMCPClient(
            jira_url=config.jira.url,
            jira_username=config.jira.username,
            jira_api_token=config.jira.api_token
        ) as jira_client:

            console.print("[dim]Initializing Fathom client...[/dim]")
            fathom_client = FathomClient(api_key=config.fathom.api_key)

            # Step 1: Select Sprint
            sprint = select_sprint_interactive(jira_client, board_id)

            # Step 2: Confirm Dates
            dates = confirm_sprint_dates_interactive(sprint)

            # Step 3: Fetch Sprint Data
            console.print("\n[bold cyan]Step 3: Fetching Sprint Data[/bold cyan]")
            from rich.progress import Progress, TextColumn

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Loading sprint issues...", total=None)

                try:
                    issues = jira_client.get_sprint_issues(sprint.id)
                    progress.update(task, completed=True)
                    console.print(f"[green]OK Loaded {len(issues)} issues[/green]")
                except Exception as e:
                    progress.stop()
                    console.print(f"[red]Error loading issues: {e}[/red]")
                    sys.exit(1)

            # Step 4: Select Transcripts
            transcripts = select_transcripts_interactive(fathom_client, dates, config)

            # Step 5: Generate Report with Claude
            console.print("\n[bold cyan]Step 5: Generating Report with Claude[/bold cyan]")
            console.print("[dim]This may take 30-60 seconds...[/dim]")

            # Import here to avoid loading heavy dependencies unless needed
            from services.report_generator import generate_sprint_report

            try:
                report_markdown = generate_sprint_report(
                    sprint=sprint,
                    issues=issues,
                    transcripts=transcripts,
                    config=config
                )
                console.print("[green]OK Report generated[/green]")
            except Exception as e:
                console.print(f"[red]Error generating report: {e}[/red]")
                sys.exit(1)

            # Step 6: Review Report
            final_report = review_report_interactive(report_markdown)

            # Step 7: Generate PDF
            console.print("\n[bold cyan]Step 6: Creating PDF[/bold cyan]")

            from services.pdf_generator import generate_pdf_report
            from utils.filename_utils import generate_report_filename

            try:
                # Generate safe filename
                filename = generate_report_filename(sprint.name, sprint.id)
                pdf_path = config.output.pdf_dir / filename

                # Generate PDF
                generate_pdf_report(
                    markdown_content=final_report,
                    output_path=pdf_path,
                    template_path=config.report.template_path,
                    metadata={
                        'sprint_name': sprint.name,
                        'sprint_id': sprint.id,
                        'team_name': config.report.team_name,
                        'generated_date': dates['start_date']
                    }
                )

                console.print(f"[green]OK PDF created: {pdf_path}[/green]")

                # Success panel
                console.print(Panel(
                    f"[green]OK Report generated successfully![/green]\n\n"
                    f"[bold]Sprint:[/bold] {sprint.name}\n"
                    f"[bold]PDF:[/bold] {pdf_path}\n"
                    f"[bold]HTML:[/bold] {str(pdf_path).replace('.pdf', '.html')}",
                    title="Success",
                    border_style="green"
                ))

                # Auto-open PDF if configured
                if config.output.auto_open_pdf:
                    import os
                    console.print("[dim]Opening PDF...[/dim]")
                    os.startfile(str(pdf_path))  # Windows

            except Exception as e:
                console.print(f"[red]Error creating PDF: {e}[/red]")
                sys.exit(1)
        # JIRA client automatically cleaned up here

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Cancelled by user[/yellow]")
        sys.exit(0)

    except FileNotFoundError as e:
        console.print(f"\n[red]Configuration Error:[/red] {e}")
        sys.exit(1)

    except Exception as e:
        console.print(f"\n[red]Unexpected Error:[/red] {e}")
        import traceback
        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
