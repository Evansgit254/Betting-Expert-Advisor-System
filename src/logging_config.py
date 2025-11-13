"""Centralized logging configuration for the betting system.

This module provides a consistent logging setup across all modules with:
- Structured logging with JSON formatting
- Different log levels for different environments
- File rotation to prevent disk space issues
- Console and file handlers
"""
import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import settings


class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler that recreates missing directories on the fly."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.stream is None:
                Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
                self.stream = self._open()
            super().emit(record)
        except FileNotFoundError:
            Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
            self.stream = self._open()
            super().emit(record)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    json_format: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """Setup logging configuration for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. If None, logs only to console
        json_format: If True, use JSON formatting for logs
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
    """
    # Get log level from settings or parameter
    level = log_level or settings.LOG_LEVEL
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    if json_format:
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        file_handler = SafeRotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8", delay=True
        )
        file_handler.setLevel(numeric_level)

        if json_format:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Log the configuration
    root_logger.info(f"Logging configured: level={level}, file={log_file}, json={json_format}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Name of the logger (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Setup logging on module import if not already configured
if not logging.getLogger().handlers:
    setup_logging(log_file="logs/betting_advisor.log", json_format=settings.ENV == "production")
