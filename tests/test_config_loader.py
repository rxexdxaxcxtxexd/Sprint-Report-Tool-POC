"""
Unit tests for utils/config_loader.py

Run with: pytest tests/test_config_loader.py -v
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import yaml

from utils.config_loader import (
    ConfigLoader,
    ConfigurationError,
    load_config,
    get_board_config,
    get_env_var,
    get_claude_config,
    get_sprint_guide_path
)


# Sample configuration for testing
SAMPLE_CONFIG = {
    "jira": {
        "default_board_id": 38,
        "boards": {
            38: {
                "name": "BOPS Board",
                "project": "BOPS",
                "url": "https://csgsolutions.atlassian.net/jira/software/c/projects/BOPS/boards/38"
            }
        }
    },
    "sprint_report": {
        "guide_path": "test_guide.docx",
        "output_dir": "output"
    },
    "claude": {
        "model": "claude-opus-4-5-20251101",
        "max_tokens": 8192,
        "temperature": 0.7
    }
}


class TestConfigLoader:
    """Test ConfigLoader class."""

    def test_init_success(self, tmp_path):
        """Test successful initialization."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        loader = ConfigLoader(str(config_file))
        assert loader.config_path == config_file
        assert loader._config is not None

    def test_init_file_not_found(self):
        """Test initialization with missing file."""
        with pytest.raises(ConfigurationError, match="not found"):
            ConfigLoader("nonexistent.yaml")

    def test_get_with_dot_notation(self, tmp_path):
        """Test getting config values with dot notation."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        loader = ConfigLoader(str(config_file))

        # Test nested access
        assert loader.get("jira.default_board_id") == 38
        assert loader.get("claude.model") == "claude-opus-4-5-20251101"

    def test_get_with_default(self, tmp_path):
        """Test getting config with default value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        loader = ConfigLoader(str(config_file))

        # Existing key
        assert loader.get("jira.default_board_id", default=999) == 38

        # Non-existing key
        assert loader.get("nonexistent.key", default="default") == "default"

    @patch.dict(os.environ, {"TEST_VAR": "test_value"})
    def test_get_env_var(self, tmp_path):
        """Test getting environment variables."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        loader = ConfigLoader(str(config_file))

        # Existing env var
        assert loader.get_env_var("TEST_VAR") == "test_value"

        # Non-existing with default
        assert loader.get_env_var("NONEXISTENT", default="default") == "default"

    @patch.dict(os.environ, {}, clear=True)
    def test_get_env_var_required_missing(self, tmp_path):
        """Test getting required env var that's missing."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        loader = ConfigLoader(str(config_file))

        with pytest.raises(ConfigurationError, match="Required environment variable"):
            loader.get_env_var("MISSING_VAR", required=True)

    def test_get_board_config(self, tmp_path):
        """Test getting board configuration."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        loader = ConfigLoader(str(config_file))

        # Get specific board
        board_config = loader.get_board_config(38)
        assert board_config["id"] == 38
        assert board_config["name"] == "BOPS Board"

        # Get default board (no ID specified)
        default_board = loader.get_board_config()
        assert default_board["id"] == 38

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_missing_env_vars(self, tmp_path):
        """Test validation with missing environment variables."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        loader = ConfigLoader(str(config_file))
        validation = loader.validate()

        # Should have errors for missing API keys
        assert len(validation["errors"]) > 0
        assert any("ANTHROPIC_API_KEY" in err for err in validation["errors"])


class TestLoadConfig:
    """Test load_config function."""

    def test_load_valid_config(self, tmp_path):
        """Test loading valid YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        config = load_config(str(config_file))
        assert config["jira"]["default_board_id"] == 38

    def test_load_nonexistent_file(self):
        """Test loading non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content:")

        with pytest.raises(yaml.YAMLError):
            load_config(str(config_file))


class TestGetBoardConfig:
    """Test get_board_config function."""

    def test_get_existing_board(self, tmp_path):
        """Test getting existing board config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        config = load_config(str(config_file))
        board_config = get_board_config(38, config)

        assert board_config["id"] == 38
        assert board_config["name"] == "BOPS Board"

    def test_get_nonexistent_board(self, tmp_path):
        """Test getting non-existent board."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(SAMPLE_CONFIG))

        config = load_config(str(config_file))

        with pytest.raises(ConfigurationError, match="Board.*not found"):
            get_board_config(999, config)


class TestGetEnvVar:
    """Test get_env_var function."""

    @patch.dict(os.environ, {"TEST_VAR": "test_value"})
    def test_get_existing_var(self):
        """Test getting existing environment variable."""
        assert get_env_var("TEST_VAR") == "test_value"

    @patch.dict(os.environ, {}, clear=True)
    def test_get_missing_var_with_default(self):
        """Test getting missing var with default."""
        assert get_env_var("MISSING", default="default") == "default"

    @patch.dict(os.environ, {}, clear=True)
    def test_get_missing_required_var(self):
        """Test getting missing required var."""
        with pytest.raises(ConfigurationError, match="Required environment variable"):
            get_env_var("MISSING", required=True)


class TestGetClaudeConfig:
    """Test get_claude_config function."""

    def test_get_claude_config_with_defaults(self):
        """Test getting Claude config with defaults."""
        config = {}
        claude_config = get_claude_config(config)

        assert claude_config["model"] == "claude-opus-4-5-20251101"
        assert claude_config["max_tokens"] == 4096
        assert claude_config["temperature"] == 0.7

    def test_get_claude_config_with_overrides(self):
        """Test getting Claude config with custom values."""
        config = {
            "claude": {
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 8192
            }
        }

        claude_config = get_claude_config(config)
        assert claude_config["model"] == "claude-sonnet-4-5-20250929"
        assert claude_config["max_tokens"] == 8192


class TestGetSprintGuidePath:
    """Test get_sprint_guide_path function."""

    def test_get_existing_path(self, tmp_path):
        """Test getting path to existing file."""
        guide_file = tmp_path / "guide.docx"
        guide_file.write_text("test")

        config = {
            "sprint_report": {
                "guide_path": str(guide_file)
            }
        }

        path = get_sprint_guide_path(config)
        assert path == guide_file

    def test_get_missing_path(self, tmp_path):
        """Test getting path to non-existent file."""
        config = {
            "sprint_report": {
                "guide_path": "nonexistent.docx"
            }
        }

        with pytest.raises(ConfigurationError, match="not found"):
            get_sprint_guide_path(config)

    def test_get_path_not_configured(self):
        """Test when guide_path not in config."""
        config = {"sprint_report": {}}

        with pytest.raises(ConfigurationError, match="not configured"):
            get_sprint_guide_path(config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
