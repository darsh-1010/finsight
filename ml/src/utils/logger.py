"""Logging utilities with YAML configuration support."""

import logging
import logging.config
from pathlib import Path
from typing import Any

import yaml

_loggers: dict[str, logging.Logger] = {}


def load_logging_config() -> dict[str, Any]:
    """Load logging configuration from YAML file."""
    config_path = Path(__file__).parent.parent.parent / "config" / "logging_config.yaml"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # Default configuration if file not found
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "app_file": {
                "class": "logging.FileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": "logs/app.log",
                "mode": "a",
                "encoding": "utf-8",
            },
            "scraper_file": {
                "class": "logging.FileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": "logs/web_scraping.log",
                "mode": "a",
                "encoding": "utf-8",
            },
        },
        "root": {"level": "INFO", "handlers": ["console", "app_file"]},
    }
    return config


def setup_logging() -> None:
    """Setup logging configuration from YAML file."""
    config = load_logging_config()

    # Ensure logs directory exists
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Update file handler paths to absolute paths
    if "handlers" in config:
        if "app_file" in config["handlers"]:
            config["handlers"]["app_file"]["filename"] = str(log_dir / "app.log")
        if "scraper_file" in config["handlers"]:
            config["handlers"]["scraper_file"]["filename"] = str(
                log_dir / "web_scraping.log"
            )

    _apply_logging_config(config)


def _apply_logging_config(config: dict[str, Any]) -> None:
    """Apply logging configuration, falling back to console-only if file handlers fail.

    File handlers will fail when the /app/logs/ directory is not writable (e.g. a host
    volume mount with root ownership). Rather than crashing the entire application, we
    strip file handlers and retry so structured console logging is still available.

    Args:
        config: dictConfig-compatible logging configuration dictionary.
    """
    try:
        logging.config.dictConfig(config)
    except (ValueError, OSError):
        # Strip all file-based handlers so we can still start with console logging.
        # This keeps the app alive even when the log directory is not writable.
        console_only = {**config}
        console_only["handlers"] = {
            name: handler
            for name, handler in config.get("handlers", {}).items()
            if "Stream" in handler.get("class", "")
            or "stream" in handler.get("class", "")
        }
        console_only["root"] = {
            "level": config.get("root", {}).get("level", "INFO"),
            "handlers": list(console_only["handlers"].keys()),
        }
        for logger_name in console_only.get("loggers", {}).values():
            logger_name["handlers"] = [
                h
                for h in logger_name.get("handlers", [])
                if h in console_only["handlers"]
            ]
        logging.config.dictConfig(console_only)
        logging.warning(
            "[LOGGING_FALLBACK] File handlers failed (permission denied). "
            "Logging to console only."
        )


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    if name not in _loggers:
        # Ensure logging is setup
        if not logging.getLogger().handlers:
            setup_logging()

        logger = logging.getLogger(name)
        _loggers[name] = logger

    return _loggers[name]
