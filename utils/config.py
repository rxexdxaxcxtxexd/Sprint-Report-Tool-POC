"""
Configuration management for Sprint Report CLI.

Loads configuration from .env file (API keys) and config.yaml (settings).
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List
import yaml
from dotenv import load_dotenv


@dataclass
class JiraConfig:
    """JIRA configuration settings."""
    url: str
    username: str
    api_token: str
    default_board_id: int
    default_project: str


@dataclass
class FathomConfig:
    """Fathom API configuration settings."""
    api_key: str
    search_terms: List[str]
    date_range_padding_days: int


@dataclass
class ReportConfig:
    """Report generation settings."""
    team_name: str
    guide_path: Path
    template_path: Path


@dataclass
class OutputConfig:
    """Output file settings."""
    pdf_dir: Path
    html_dir: Path
    auto_open_pdf: bool


@dataclass
class ClaudeConfig:
    """Claude AI configuration."""
    api_key: str
    model: str
    max_tokens: int
    temperature: float


@dataclass
class Config:
    """Complete application configuration."""
    jira: JiraConfig
    fathom: FathomConfig
    report: ReportConfig
    output: OutputConfig
    claude: ClaudeConfig
    project_root: Path


def load_config(config_path: str = None, env_path: str = None) -> Config:
    """Load configuration from .env and config.yaml files.

    Args:
        config_path: Path to config.yaml (default: ./config.yaml)
        env_path: Path to .env file (default: ./.env)

    Returns:
        Config object with all settings loaded

    Raises:
        FileNotFoundError: If config files are missing
        KeyError: If required environment variables are missing
        ValueError: If configuration values are invalid
    """
    # Determine project root (where this script is run from)
    if config_path is None:
        project_root = Path.cwd()
        config_path = project_root / "config.yaml"
    else:
        config_path = Path(config_path)
        project_root = config_path.parent

    # Load environment variables
    if env_path is None:
        env_path = project_root / ".env"

    load_dotenv(env_path, override=True)

    # Verify .env file exists and is readable
    if not Path(env_path).exists():
        raise FileNotFoundError(
            f".env file not found at {env_path}\n"
            f"Copy .env.template to .env and configure your API keys."
        )

    # Load YAML configuration
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at {config_path}\n"
            f"Ensure config.yaml exists in the project root."
        )

    with open(config_path, 'r') as f:
        yaml_config = yaml.safe_load(f)

    # Extract environment variables (with validation)
    required_env_vars = [
        'ANTHROPIC_API_KEY',
        'FATHOM_API_KEY',
        'JIRA_URL',
        'JIRA_USERNAME',
        'JIRA_API_TOKEN'
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise KeyError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            f"Configure these in your .env file."
        )

    # Build configuration objects
    jira_config = JiraConfig(
        url=os.getenv('JIRA_URL'),
        username=os.getenv('JIRA_USERNAME'),
        api_token=os.getenv('JIRA_API_TOKEN'),
        default_board_id=yaml_config['jira']['default_board_id'],
        default_project=yaml_config['jira']['default_project']
    )

    fathom_config = FathomConfig(
        api_key=os.getenv('FATHOM_API_KEY'),
        search_terms=yaml_config['fathom']['search_terms'],
        date_range_padding_days=yaml_config['fathom'].get('date_range_padding_days', 2)
    )

    report_config = ReportConfig(
        team_name=yaml_config['report']['team_name'],
        guide_path=project_root / yaml_config['report']['guide_path'],
        template_path=project_root / yaml_config['report']['template_path']
    )

    output_config = OutputConfig(
        pdf_dir=project_root / yaml_config['output']['pdf_dir'],
        html_dir=project_root / yaml_config['output']['html_dir'],
        auto_open_pdf=yaml_config['output'].get('auto_open_pdf', True)
    )

    claude_config = ClaudeConfig(
        api_key=os.getenv('ANTHROPIC_API_KEY'),
        model=yaml_config['claude'].get('model', 'claude-sonnet-4-5-20250929'),
        max_tokens=yaml_config['claude'].get('max_tokens', 4096),
        temperature=yaml_config['claude'].get('temperature', 0.7)
    )

    # Create output directories if they don't exist
    output_config.pdf_dir.mkdir(parents=True, exist_ok=True)
    output_config.html_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        jira=jira_config,
        fathom=fathom_config,
        report=report_config,
        output=output_config,
        claude=claude_config,
        project_root=project_root
    )


def validate_config(config: Config) -> List[str]:
    """Validate configuration for common issues.

    Args:
        config: Configuration object to validate

    Returns:
        List of warning messages (empty if all valid)
    """
    warnings = []

    # Check if guide file exists
    if not config.report.guide_path.exists():
        warnings.append(f"Sprint guide not found: {config.report.guide_path}")

    # Check if template file exists
    if not config.report.template_path.exists():
        warnings.append(f"Report template not found: {config.report.template_path}")

    # Check JIRA URL format
    if not config.jira.url.startswith('https://'):
        warnings.append(f"JIRA URL should use HTTPS: {config.jira.url}")

    # Check board ID is positive
    if config.jira.default_board_id <= 0:
        warnings.append(f"Invalid JIRA board ID: {config.jira.default_board_id}")

    return warnings


if __name__ == "__main__":
    """Test configuration loading."""
    try:
        print("Loading configuration...")
        config = load_config()
        print(f"✓ Configuration loaded successfully")
        print(f"  JIRA: {config.jira.url}")
        print(f"  Fathom: API key configured")
        print(f"  Claude: {config.claude.model}")
        print(f"  Output: {config.output.pdf_dir}")

        warnings = validate_config(config)
        if warnings:
            print("\n⚠ Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        else:
            print("\n✓ All validation checks passed")

    except Exception as e:
        print(f"✗ Configuration error: {e}")
