"""
Configuration loader for Sprint Report Service.

This module provides utilities for loading and managing configuration from
YAML files and environment variables. It supports:
- Loading YAML configuration files
- Safe environment variable access with validation
- Board-specific configuration with fallback to defaults
- Type-safe configuration access

Example:
    >>> from utils.config_loader import ConfigLoader
    >>> config = ConfigLoader("config.yaml")
    >>> api_key = config.get_env_var("ANTHROPIC_API_KEY", required=True)
    >>> board_config = config.get_board_config(38)
"""

import os
import yaml
import logging
from typing import Any, Optional, Dict, List
from pathlib import Path
from dotenv import load_dotenv


# Module logger
logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class ConfigLoader:
    """
    Configuration loader for Sprint Report Service.

    Loads configuration from YAML files and environment variables,
    providing a centralized interface for accessing all settings.

    Attributes:
        config_path: Path to the YAML configuration file
        _config: Loaded configuration dictionary

    Example:
        >>> config = ConfigLoader("config.yaml")
        >>> model = config.get("claude.model", default="claude-opus-4-5-20251101")
        >>> jira_url = config.get_env_var("JIRA_BASE_URL", required=True)
    """

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the configuration loader.

        Args:
            config_path: Path to YAML configuration file (default: "config.yaml")

        Raises:
            ConfigurationError: If config file doesn't exist or is invalid
        """
        self.config_path = Path(config_path)

        # Load environment variables from .env file
        load_dotenv()
        logger.debug(f"Loaded environment variables from .env")

        # Load YAML configuration
        try:
            self._config = load_config(str(self.config_path))
            logger.info(f"Configuration loaded from {self.config_path}")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}"
            )
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in configuration file: {e}")
            raise ConfigurationError(
                f"Invalid YAML in configuration file: {e}"
            )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with dot notation support.

        Supports nested keys using dot notation (e.g., "jira.default_board_id").

        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key doesn't exist

        Returns:
            Configuration value or default if not found

        Example:
            >>> config = ConfigLoader()
            >>> model = config.get("claude.model")
            >>> board_id = config.get("jira.default_board_id", default=38)
        """
        keys = key.split(".")
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            logger.debug(f"Configuration key '{key}' not found, using default: {default}")
            return default

    def get_board_config(self, board_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get board-specific configuration with fallback to defaults.

        Args:
            board_id: JIRA board ID (if None, uses default_board_id from config)

        Returns:
            Dictionary with board configuration

        Raises:
            ConfigurationError: If board_id not found and no default configured

        Example:
            >>> config = ConfigLoader()
            >>> board_config = config.get_board_config(38)
            >>> print(board_config["name"])  # "BOPS Board"
        """
        if board_id is None:
            board_id = self.get("jira.default_board_id")
            if board_id is None:
                raise ConfigurationError(
                    "No board_id provided and no default_board_id in config"
                )

        return get_board_config(board_id, self._config)

    def get_env_var(
        self,
        key: str,
        default: Optional[str] = None,
        required: bool = False
    ) -> Optional[str]:
        """
        Get environment variable with validation.

        Args:
            key: Environment variable name
            default: Default value if variable not set
            required: If True, raises error when variable not found

        Returns:
            Environment variable value or default

        Raises:
            ConfigurationError: If required=True and variable not found

        Example:
            >>> config = ConfigLoader()
            >>> api_key = config.get_env_var("ANTHROPIC_API_KEY", required=True)
            >>> port = config.get_env_var("SERVICE_PORT", default="8001")
        """
        return get_env_var(key, default, required)

    def validate(self) -> Dict[str, List[str]]:
        """
        Validate configuration completeness.

        Checks for required configuration values and environment variables.

        Returns:
            Dictionary with 'errors' and 'warnings' lists

        Example:
            >>> config = ConfigLoader()
            >>> validation = config.validate()
            >>> if validation["errors"]:
            ...     print(f"Configuration errors: {validation['errors']}")
        """
        errors = []
        warnings = []

        # Check required environment variables
        required_env_vars = [
            "ANTHROPIC_API_KEY",
            "JIRA_BASE_URL",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN"
        ]

        for var in required_env_vars:
            if not os.getenv(var):
                errors.append(f"Missing required environment variable: {var}")

        # Check required configuration keys
        required_config_keys = [
            "jira.default_board_id",
            "sprint_report.guide_path",
            "sprint_report.output_dir"
        ]

        for key in required_config_keys:
            if self.get(key) is None:
                warnings.append(f"Missing recommended configuration: {key}")

        # Check if sprint guide file exists
        guide_path = self.get("sprint_report.guide_path")
        if guide_path and not Path(guide_path).exists():
            warnings.append(
                f"Sprint Report Guide not found at: {guide_path}"
            )

        if errors:
            logger.error(f"Configuration validation errors: {errors}")
        if warnings:
            logger.warning(f"Configuration validation warnings: {warnings}")

        return {"errors": errors, "warnings": warnings}


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Load YAML configuration file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        yaml.YAMLError: If YAML is invalid

    Example:
        >>> config = load_config("config.yaml")
        >>> print(config["jira"]["default_board_id"])
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise yaml.YAMLError("Configuration must be a YAML dictionary")

        logger.debug(f"Loaded configuration from {config_path}")
        return config

    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        raise


def get_board_config(
    board_id: int,
    config: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Get board-specific configuration from config dictionary.

    Args:
        board_id: JIRA board ID
        config: Configuration dictionary (if None, loads from config.yaml)

    Returns:
        Board configuration dictionary with keys:
            - id: Board ID
            - name: Board name
            - project: Project key
            - url: Board URL

    Raises:
        ConfigurationError: If board not found in configuration

    Example:
        >>> board_config = get_board_config(38)
        >>> print(board_config["name"])  # "BOPS Board"
    """
    if config is None:
        config = load_config()

    # Get board configuration from jira.boards
    boards = config.get("jira", {}).get("boards", {})

    if board_id not in boards:
        # Check if it's the default board
        default_board_id = config.get("jira", {}).get("default_board_id")
        if board_id == default_board_id and default_board_id in boards:
            board_config = boards[default_board_id]
        else:
            raise ConfigurationError(
                f"Board {board_id} not found in configuration. "
                f"Available boards: {list(boards.keys())}"
            )
    else:
        board_config = boards[board_id]

    # Add board_id to config
    board_config["id"] = board_id

    logger.debug(f"Retrieved configuration for board {board_id}")
    return board_config


def get_env_var(
    key: str,
    default: Optional[str] = None,
    required: bool = False
) -> Optional[str]:
    """
    Get environment variable with validation.

    Safe wrapper around os.getenv with better error handling.

    Args:
        key: Environment variable name
        default: Default value if variable not set
        required: If True, raises error when variable not found

    Returns:
        Environment variable value or default

    Raises:
        ConfigurationError: If required=True and variable not found

    Example:
        >>> api_key = get_env_var("ANTHROPIC_API_KEY", required=True)
        >>> port = get_env_var("SERVICE_PORT", default="8001")
    """
    value = os.getenv(key, default)

    if required and not value:
        error_msg = (
            f"Required environment variable '{key}' not set. "
            f"Please add it to your .env file."
        )
        logger.error(error_msg)
        raise ConfigurationError(error_msg)

    if value:
        logger.debug(f"Retrieved environment variable: {key}")
    else:
        logger.debug(f"Environment variable '{key}' not set, using default: {default}")

    return value


def get_claude_config(config: Optional[dict] = None) -> Dict[str, Any]:
    """
    Get Claude API configuration.

    Args:
        config: Configuration dictionary (if None, loads from config.yaml)

    Returns:
        Dictionary with Claude configuration:
            - model: Model name
            - max_tokens: Maximum tokens
            - temperature: Temperature setting
            - max_retries: Maximum retry attempts

    Example:
        >>> claude_config = get_claude_config()
        >>> print(claude_config["model"])  # "claude-opus-4-5-20251101"
    """
    if config is None:
        config = load_config()

    # Default Claude configuration
    default_config = {
        "model": "claude-opus-4-5-20251101",
        "max_tokens": 4096,
        "temperature": 0.7,
        "max_retries": 3
    }

    # Merge with config file settings
    claude_config = config.get("claude", {})
    default_config.update(claude_config)

    return default_config


def get_sprint_guide_path(config: Optional[dict] = None) -> Path:
    """
    Get path to Sprint Report Guide DOCX file.

    Args:
        config: Configuration dictionary (if None, loads from config.yaml)

    Returns:
        Path to Sprint Report Guide file

    Raises:
        ConfigurationError: If guide_path not in config or file doesn't exist

    Example:
        >>> guide_path = get_sprint_guide_path()
        >>> print(guide_path)  # WindowsPath('C:/Users/layden/Downloads/CSG_...')
    """
    if config is None:
        config = load_config()

    guide_path = config.get("sprint_report", {}).get("guide_path")

    if not guide_path:
        raise ConfigurationError(
            "sprint_report.guide_path not configured in config.yaml"
        )

    guide_file = Path(guide_path)

    if not guide_file.exists():
        raise ConfigurationError(
            f"Sprint Report Guide not found at: {guide_path}"
        )

    return guide_file


# Convenience function for quick access
def get_config(config_path: str = "config.yaml") -> ConfigLoader:
    """
    Convenience function to get a ConfigLoader instance.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        ConfigLoader instance

    Example:
        >>> config = get_config()
        >>> api_key = config.get_env_var("ANTHROPIC_API_KEY", required=True)
    """
    return ConfigLoader(config_path)


if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        config = ConfigLoader()
        print("Configuration loaded successfully!")
        print(f"Default board ID: {config.get('jira.default_board_id')}")
        print(f"Claude model: {config.get('claude.model', 'claude-opus-4-5-20251101')}")

        # Validate configuration
        validation = config.validate()
        if validation["errors"]:
            print(f"\nErrors: {validation['errors']}")
        if validation["warnings"]:
            print(f"\nWarnings: {validation['warnings']}")

    except ConfigurationError as e:
        print(f"Configuration error: {e}")
