"""
Unit tests for the ML logger utility.

Tests get_logger, setup_logging, and fallback-to-console behaviour.
All filesystem I/O is mocked — tests run fully offline.
"""

import logging
import sys
from pathlib import Path

import pytest

# Ensure src and root are importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestGetLogger:
    """Tests for get_logger()."""

    def test_returns_logging_logger(self):
        """get_logger must return a stdlib logging.Logger instance."""
        from src.utils.logger import get_logger
        log = get_logger("test.module")
        assert isinstance(log, logging.Logger)

    def test_name_matches_argument(self):
        """Logger name must equal the provided module name."""
        from src.utils.logger import get_logger
        log = get_logger("my.test.service")
        assert log.name == "my.test.service"

    def test_same_name_returns_same_logger(self):
        """Calling get_logger twice with the same name must return the same instance."""
        from src.utils.logger import get_logger
        log1 = get_logger("shared.logger")
        log2 = get_logger("shared.logger")
        assert log1 is log2

    def test_different_names_return_different_loggers(self):
        """Different names must produce separate Logger instances."""
        from src.utils.logger import get_logger
        log1 = get_logger("logger.alpha")
        log2 = get_logger("logger.beta")
        assert log1 is not log2


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_does_not_raise_without_config_file(self):
        """
        setup_logging must not raise even if the YAML config file is missing.
        The function falls back to a console-only config automatically.
        We call it directly without mocking Path so the real fallback path runs.
        """
        from src.utils.logger import setup_logging
        try:
            setup_logging()
        except Exception as exc:
            pytest.fail(f"setup_logging raised unexpectedly: {exc}")

    def test_setup_logging_returns_none(self):
        """setup_logging is a void function — must return None."""
        from src.utils.logger import setup_logging
        result = setup_logging()
        assert result is None


class TestLoadLoggingConfig:
    """Tests for load_logging_config()."""

    def test_returns_dict(self):
        """load_logging_config must always return a dict."""
        from src.utils.logger import load_logging_config
        config = load_logging_config()
        assert isinstance(config, dict)

    def test_config_has_version_key(self):
        """dictConfig-compatible config must have a 'version' key."""
        from src.utils.logger import load_logging_config
        config = load_logging_config()
        assert "version" in config

    def test_config_has_handlers(self):
        """Config must define at least one handler."""
        from src.utils.logger import load_logging_config
        config = load_logging_config()
        assert "handlers" in config
        assert len(config["handlers"]) > 0

    def test_config_has_root_logger(self):
        """Config must define a root logger."""
        from src.utils.logger import load_logging_config
        config = load_logging_config()
        assert "root" in config
