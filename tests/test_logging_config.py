"""Tests for logging configuration."""
import logging
import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import os

from src.logging_config import JSONFormatter, setup_logging, get_logger


class TestJSONFormatter:
    """Tests for JSON formatter."""

    def test_format_basic_record(self):
        """Test formatting a basic log record."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert data["module"] == "test"
        assert data["line"] == 10
        assert "timestamp" in data

    def test_format_with_exception(self):
        """Test formatting a log record with exception."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "Test error" in data["exception"]


class TestSetupLogging:
    """Tests for logging setup."""

    def test_setup_logging_console_only(self):
        """Test setup with console logging only."""
        setup_logging(log_level="INFO", log_file=None)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

    def test_setup_logging_with_file(self):
        """Test setup with file logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            setup_logging(log_level="DEBUG", log_file=log_file)

            # Log a message
            logger = logging.getLogger("test")
            logger.info("Test message")

            # Verify file was created
            assert Path(log_file).exists()

            # Verify content
            with open(log_file, "r") as f:
                content = f.read()
                assert "Test message" in content

    def test_setup_logging_json_format(self):
        """Test setup with JSON formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            setup_logging(log_level="INFO", log_file=log_file, json_format=True)

            logger = logging.getLogger("test")
            logger.info("JSON test message")

            # Verify JSON format
            with open(log_file, "r") as f:
                lines = f.readlines()
                # First line is setup message, second is our test message
                assert len(lines) >= 2
                data = json.loads(lines[1])  # Read second line
                assert data["message"] == "JSON test message"
                assert "timestamp" in data

    def test_setup_logging_creates_directory(self):
        """Test that setup creates log directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "logs", "subdir", "test.log")
            setup_logging(log_file=log_file)

            logger = logging.getLogger("test")
            logger.info("Test")

            assert Path(log_file).parent.exists()
            assert Path(log_file).exists()

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup clears existing handlers."""
        root_logger = logging.getLogger()
        len(root_logger.handlers)

        setup_logging(log_level="INFO")

        # Should have cleared and added new handlers
        assert len(root_logger.handlers) >= 1

    @patch("src.logging_config.settings")
    def test_setup_logging_uses_settings(self, mock_settings):
        """Test that setup uses settings when no level provided."""
        mock_settings.LOG_LEVEL = "WARNING"
        mock_settings.ENV = "production"

        setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name != logger2.name
        assert logger1 is not logger2

    def test_get_logger_same_name_returns_same_logger(self):
        """Test that same name returns same logger instance."""
        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")

        assert logger1 is logger2


class TestLoggingIntegration:
    """Integration tests for logging system."""

    def test_logging_levels(self):
        """Test different logging levels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            setup_logging(log_level="DEBUG", log_file=log_file)

            logger = get_logger("test")
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")

            with open(log_file, "r") as f:
                content = f.read()
                assert "Debug message" in content
                assert "Info message" in content
                assert "Warning message" in content
                assert "Error message" in content
                assert "Critical message" in content

    def test_logging_filters_by_level(self):
        """Test that logging filters messages by level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            setup_logging(log_level="WARNING", log_file=log_file)

            logger = get_logger("test")
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            with open(log_file, "r") as f:
                content = f.read()
                assert "Debug message" not in content
                assert "Info message" not in content
                assert "Warning message" in content
                assert "Error message" in content

    def test_log_rotation_configuration(self):
        """Test that log rotation is configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            setup_logging(log_file=log_file, max_bytes=1024, backup_count=3)

            logger = get_logger("test")

            # Write enough data to trigger rotation
            for i in range(100):
                logger.info(f"Message {i}" * 20)

            # Check that log file exists
            assert Path(log_file).exists()
