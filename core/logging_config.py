"""
Structured logging configuration for the visual testing framework.

Provides consistent formatting with timestamps, module names, method names, and log levels.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path


class MethodNameFilter(logging.Filter):
    """Adds the method name to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.method_name = record.funcName or "module"
        return True


def _configure_third_party_loggers() -> None:
    """Keep noisy Selenium/WebDriver internals out of project logs."""
    noisy_loggers = (
        "WDM",
        "urllib3",
        "selenium",
        "selenium.webdriver",
    )
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def setup_logging(project: str = None, log_dir: str = None) -> logging.Logger:
    """
    Configure structured logging with file and console handlers.

    Args:
        project: Sub-project name (optional, used for log directory)
        log_dir: Custom log directory (optional)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger()
    
    # Clear existing handlers to prevent duplicates
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    # Log format: [TIMESTAMP] [LEVEL] [MODULE] [METHOD] MESSAGE
    fmt_str = (
        "[%(asctime)s] [%(levelname)-7s] [%(name)-25s] [%(method_name)-20s] %(message)s"
    )
    formatter = logging.Formatter(fmt_str, datefmt="%Y-%m-%d %H:%M:%S")

    # ── Console handler (stdout for INFO+, stderr for WARNING+) ──────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(MethodNameFilter())
    # Handle cp1252 encoding in Jenkins by replacing uncodable characters
    if hasattr(console_handler, 'stream'):
        console_handler.stream.reconfigure(encoding='utf-8', errors='replace') if hasattr(console_handler.stream, 'reconfigure') else None
    logger.addHandler(console_handler)

    # ── File handler (optional) ──────────────────────────────────────────
    if project:
        if not log_dir:
            log_dir = f"projects/{project}/logs"
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        log_file = log_path / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(str(log_file), mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(MethodNameFilter())
        logger.addHandler(file_handler)

    _configure_third_party_loggers()

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a specific module with the module name as the logger name.

    Args:
        module_name: Name of the calling module (e.g., 'core.comparison')

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(module_name)
    logger.addFilter(MethodNameFilter())
    return logger
