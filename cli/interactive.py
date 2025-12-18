"""
Interactive CLI - Rich UI workflow for sprint report generation.

Provides step-by-step interactive prompts with progress tracking and
human-in-the-loop confirmation at each stage.
"""
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn
from rich import box
from typing import List, Optional, Dict, Any
from datetime import datetime
import sys

from cli.jira_mcp import JiraMCPClient, Sprint, Issue
from utils.exceptions import JiraMCPError
from cli.transcript_filter import filter_transcripts_smart, parse_selection, FilteredTranscript
from utils.config import Config

console = Console()


def validate_config_interactive(config: Config) -> bool:
    """Validate configuration with user-friendly error messages.

    Args:
        config: Configuration object to validate

    Returns:
        True if validation passes, exits on failure
    """
    console.print(Panel("[bold]Sprint Report Generator[/bold]", border_style="green"))

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Validating configuration...", total=None)

        # Check API keys
        errors = []
        if not config.claude.api_key or config.claude.api_key == 'your_key_here':
            errors.append("ANTHROPIC_API_KEY not configured")
        if not config.fathom.api_key or config.fathom.api_key == 'your_key_here':
            errors.append("FATHOM_API_KEY not configured")
        if not config.jira.api_token or config.jira.api_token == 'your_token_here':
            errors.append("JIRA_API_TOKEN not configured")

        # Check file paths
        if not config.report.guide_path.exists():
            errors.append(f"Sprint guide not found: {config.report.guide_path}")
        if not config.report.template_path.exists():
            errors.append(f"Report template not found: {config.report.template_path}")

        progress.update(task, completed=True)

    if errors:
        console.print("\n[bold red]Configuration Errors:[/bold red]")
        for error in errors:
            console.print(f"  X {error}")
        console.print("\n[yellow]Fix these issues in .env and config.yaml, then try again.[/yellow]")
        sys.exit(1)

    console.print("[green]OK Configuration validated[/green]\n")
    return True


def select_sprint_interactive(jira_client: JiraMCPClient, board_id: int) -> Sprint:
    """Interactive sprint selection.

    Args:
        jira_client: JIRA MCP client
        board_id: JIRA board ID to query

    Returns:
        Selected Sprint object
    """
    console.print("[bold cyan]Step 1: Select Sprint[/bold cyan]")

    with Progress(

        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Fetching sprints from JIRA...", total=None)

        try:
            sprints = jira_client.list_sprints(board_id, limit=15)
            progress.update(task, completed=True)
        except JiraMCPError as e:
            progress.stop()
            console.print(Panel(
                f"[red]JIRA MCP Error:[/red] {e}\n\n"
                "[yellow]Troubleshooting:[/yellow]\n"
                "1. Ensure Docker Desktop is running\n"
                "2. Check JIRA credentials in .env\n"
                "3. Run: docker pull ghcr.io/sooperset/mcp-atlassian:latest",
                title="Connection Error",
                border_style="red"
            ))
            sys.exit(1)

    if not sprints:
        console.print("[red]No sprints found on this board[/red]")
        sys.exit(1)

    # Display sprints table
    table = Table(title="Available Sprints", box=box.ROUNDED)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Sprint Name", style="white")
    table.add_column("State", style="green")
    table.add_column("Dates", style="yellow")

    for idx, sprint in enumerate(sprints, 1):
        # Format state with color
        state_color = {
            'active': 'green',
            'closed': 'blue',
            'future': 'yellow'
        }.get(sprint.state, 'white')

        state_display = f"[{state_color}]{sprint.state.upper()}[/{state_color}]"

        # Format dates
        dates = "Not scheduled"
        if sprint.start_date and sprint.end_date:
            start = sprint.start_date[:10] if 'T' in sprint.start_date else sprint.start_date
            end = sprint.end_date[:10] if 'T' in sprint.end_date else sprint.end_date
            dates = f"{start}  to  {end}"

        table.add_row(str(idx), sprint.name, state_display, dates)

    console.print(table)

    # Get user selection
    while True:
        selection = Prompt.ask(
            "\n[bold]Select sprint number[/bold]",
            default="1"
        )

        try:
            idx = int(selection)
            if 1 <= idx <= len(sprints):
                selected = sprints[idx - 1]
                console.print(f"\n[green]OK Selected: {selected.name}[/green]")
                return selected
            else:
                console.print(f"[red]Invalid selection. Enter a number between 1 and {len(sprints)}[/red]")
        except ValueError:
            console.print("[red]Invalid input. Enter a number.[/red]")


def confirm_sprint_dates_interactive(sprint: Sprint) -> Dict[str, str]:
    """Confirm or adjust sprint dates.

    Args:
        sprint: Sprint object with dates

    Returns:
        Dictionary with 'start_date' and 'end_date' keys
    """
    console.print("\n[bold cyan]Step 2: Confirm Sprint Dates[/bold cyan]")

    if not sprint.start_date or not sprint.end_date:
        console.print("[yellow]Sprint has no scheduled dates. Please enter dates manually.[/yellow]")

        start_date = Prompt.ask("Start date (YYYY-MM-DD)")
        end_date = Prompt.ask("End date (YYYY-MM-DD)")

        return {'start_date': start_date, 'end_date': end_date}

    # Format dates for display
    start = sprint.start_date[:10] if 'T' in sprint.start_date else sprint.start_date
    end = sprint.end_date[:10] if 'T' in sprint.end_date else sprint.end_date

    console.print(f"Sprint dates: [bold]{start}[/bold]  to  [bold]{end}[/bold]")

    if Confirm.ask("Are these dates correct?", default=True):
        return {'start_date': start, 'end_date': end}
    else:
        start_date = Prompt.ask("Enter start date (YYYY-MM-DD)", default=start)
        end_date = Prompt.ask("Enter end date (YYYY-MM-DD)", default=end)
        return {'start_date': start_date, 'end_date': end_date}


def select_transcripts_interactive(
    fathom_client,
    dates: Dict[str, str],
    config: Config
) -> List[FilteredTranscript]:
    """Interactive transcript selection with smart filtering.

    Args:
        fathom_client: Fathom API client
        dates: Dictionary with 'start_date' and 'end_date'
        config: Configuration object

    Returns:
        List of selected FilteredTranscript objects
    """
    console.print("\n[bold cyan]Step 3: Select Fathom Transcripts[/bold cyan]")

    with Progress(

        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Fetching Fathom meetings...", total=None)

        try:
            # Fetch meetings in date range
            meetings = fathom_client.list_meetings(
                start_date=dates['start_date'],
                end_date=dates['end_date'],
                recorded_by=None,
                include_transcript=False
            )
            progress.update(task, completed=True)
        except Exception as e:
            progress.stop()
            console.print(f"[red]Fathom API Error: {e}[/red]")
            console.print("[yellow]Proceeding without transcripts...[/yellow]")
            return []

    if not meetings:
        console.print("[yellow]No Fathom meetings found in sprint date range[/yellow]")
        if not Confirm.ask("Proceed without transcripts?", default=True):
            sys.exit(0)
        return []

    # Filter and rank transcripts
    filtered = filter_transcripts_smart(meetings, config.fathom.search_terms)

    total_count = (
        len(filtered['high_confidence']) +
        len(filtered['medium_confidence']) +
        len(filtered['other'])
    )

    console.print(f"Found {total_count} meetings in date range")

    # Display ranked transcripts
    table = Table(title="Fathom Transcripts (Select Relevant)", box=box.ROUNDED)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Title", style="white", no_wrap=False)
    table.add_column("Date", style="green")
    table.add_column("Match", style="yellow")

    idx = 1

    # High confidence (pre-selected)
    for t in filtered['high_confidence']:
        table.add_row(
            f"[OK] {idx}",
            t.title,
            t.date[:10] if len(t.date) > 10 else t.date,
            "[green]HIGH[/green]"
        )
        idx += 1

    # Medium confidence
    for t in filtered['medium_confidence']:
        table.add_row(
            f"[ ] {idx}",
            t.title,
            t.date[:10] if len(t.date) > 10 else t.date,
            "[yellow]MEDIUM[/yellow]"
        )
        idx += 1

    # Others
    for t in filtered['other']:
        table.add_row(
            f"[ ] {idx}",
            t.title,
            t.date[:10] if len(t.date) > 10 else t.date,
            "[dim]LOW[/dim]"
        )
        idx += 1

    console.print(table)

    # Get user selection
    console.print("\n[dim]Enter selections:[/dim]")
    console.print("  [dim]• Numbers: '1,2,5'[/dim]")
    console.print("  [dim]• All high confidence: 'all high' or 'high'[/dim]")
    console.print("  [dim]• All transcripts: 'all'[/dim]")
    console.print("  [dim]• Skip transcripts: 'none'[/dim]")

    selection = Prompt.ask(
        "\n[bold]Select transcripts[/bold]",
        default="all high"
    )

    selected = parse_selection(selection, filtered)

    console.print(f"\n[green]OK Selected {len(selected)} transcript(s)[/green]")
    return selected


def review_report_interactive(report_markdown: str) -> str:
    """Interactive report review and editing.

    Args:
        report_markdown: Generated report in Markdown format

    Returns:
        Final approved report (may be edited)
    """
    console.print("\n[bold cyan]Step 4: Review Report[/bold cyan]")

    # Show preview
    preview_length = 1000
    if len(report_markdown) > preview_length:
        preview = report_markdown[:preview_length] + "\n\n[... truncated ...]"
    else:
        preview = report_markdown

    console.print(Panel(preview, title="Report Preview", border_style="blue"))

    console.print(f"\nReport length: {len(report_markdown)} characters")

    # Review options
    console.print("\n[bold]Review options:[/bold]")
    console.print("  1. Accept report as-is")
    console.print("  2. View full report")
    console.print("  3. Edit report (opens in notepad)")

    choice = Prompt.ask("Select option", choices=["1", "2", "3"], default="1")

    if choice == "1":
        console.print("[green]OK Report accepted[/green]")
        return report_markdown

    elif choice == "2":
        console.print("\n" + "="*80)
        console.print(report_markdown)
        console.print("="*80 + "\n")

        if Confirm.ask("Accept this report?", default=True):
            return report_markdown
        else:
            # Recursively call for edit
            return review_report_interactive(report_markdown)

    elif choice == "3":
        import tempfile
        import subprocess

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(report_markdown)
            temp_path = f.name

        console.print(f"[yellow]Opening report in notepad...[/yellow]")
        console.print(f"[dim]Edit the file, save, and close notepad to continue[/dim]")

        # Open in notepad (Windows)
        subprocess.run(['notepad', temp_path], check=True)

        # Read edited content
        with open(temp_path, 'r') as f:
            edited_content = f.read()

        if edited_content != report_markdown:
            console.print("[green]OK Report updated with your edits[/green]")
            return edited_content
        else:
            console.print("[yellow]No changes made[/yellow]")
            return report_markdown

    return report_markdown


if __name__ == "__main__":
    """Test interactive CLI components."""
    from utils.config import load_config

    try:
        config = load_config()
        validate_config_interactive(config)

        jira_client = JiraMCPClient(
            jira_url=config.jira.url,
            jira_username=config.jira.username,
            jira_api_token=config.jira.api_token
        )

        sprint = select_sprint_interactive(jira_client, config.jira.default_board_id)
        dates = confirm_sprint_dates_interactive(sprint)

        console.print(f"\nSelected: {sprint.name}")
        console.print(f"Dates: {dates['start_date']}  to  {dates['end_date']}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        sys.exit(0)
