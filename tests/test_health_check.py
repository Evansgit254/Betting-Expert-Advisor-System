"""Tests for health check system."""
from unittest.mock import MagicMock, patch

from src.health_check import (
    HealthCheckResult,
    check_configuration,
    check_database,
    check_disk_space,
    check_models,
    print_health_status,
    run_all_health_checks,
)


class TestHealthCheckResult:
    """Tests for HealthCheckResult class."""

    def test_create_result(self):
        """Test creating a health check result."""
        result = HealthCheckResult(
            name="test", status="healthy", message="All good", details={"key": "value"}
        )
        assert result.name == "test"
        assert result.status == "healthy"
        assert result.message == "All good"
        assert result.details == {"key": "value"}
        assert result.timestamp is not None

    def test_is_healthy_property(self):
        """Test is_healthy property."""
        healthy = HealthCheckResult("test", "healthy")
        assert healthy.is_healthy is True

        degraded = HealthCheckResult("test", "degraded")
        assert degraded.is_healthy is False

        unhealthy = HealthCheckResult("test", "unhealthy")
        assert unhealthy.is_healthy is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = HealthCheckResult(
            name="test", status="healthy", message="Test message", details={"count": 5}
        )
        data = result.to_dict()

        assert data["name"] == "test"
        assert data["status"] == "healthy"
        assert data["message"] == "Test message"
        assert data["details"] == {"count": 5}
        assert "timestamp" in data


class TestCheckDatabase:
    """Tests for database health check."""

    def test_database_healthy(self):
        """Test successful database check."""
        result = check_database()
        assert result.name == "database"
        assert result.status in ["healthy", "unhealthy"]

    @patch("src.health_check.handle_db_errors")
    def test_database_connection_success(self, mock_handle_db_errors):
        """Test database check with successful connection."""
        mock_session = MagicMock()
        mock_session.query.return_value.count.return_value = 10
        mock_handle_db_errors.return_value.__enter__.return_value = mock_session

        result = check_database()
        assert result.status == "healthy"
        assert result.details["bet_count"] == 10

    @patch("src.health_check.handle_db_errors")
    def test_database_connection_failure(self, mock_handle_db_errors):
        """Test database check with connection failure."""
        mock_handle_db_errors.side_effect = Exception("Connection failed")

        result = check_database()
        assert result.status == "unhealthy"
        assert "Connection failed" in result.message


class TestCheckDiskSpace:
    """Tests for disk space health check."""

    def test_disk_space_sufficient(self):
        """Test disk space check with sufficient space."""
        # Test with actual disk space (should pass on most systems)
        result = check_disk_space(min_free_gb=0.1)  # Very low threshold

        # Should be healthy or degraded, not unhealthy
        assert result.status in ["healthy", "degraded"]
        assert result.name == "disk_space"

    def test_disk_space_low(self):
        """Test disk space check with low space threshold."""
        # Test with very high threshold to simulate low space
        result = check_disk_space(min_free_gb=999999.0)  # Impossibly high

        # Should be degraded due to insufficient space
        assert result.status == "degraded"
        assert result.name == "disk_space"

    @patch("src.health_check.Path")
    def test_disk_space_directory_not_found(self, mock_path_class):
        """Test disk space check when directory doesn't exist."""
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path_class.return_value = mock_path_instance

        result = check_disk_space()
        assert result.status == "degraded"
        assert "not found" in result.message


class TestCheckConfiguration:
    """Tests for configuration health check."""

    @patch("src.health_check.settings")
    def test_configuration_valid(self, mock_settings):
        """Test configuration check with valid settings."""
        mock_settings.DB_URL = "sqlite:///test.db"
        mock_settings.MODE = "DRY_RUN"
        mock_settings.MAX_STAKE_FRAC = 0.1
        mock_settings.DEFAULT_KELLY_FRACTION = 0.25
        mock_settings.ENV = "development"

        result = check_configuration()
        assert result.status == "healthy"

    @patch("src.health_check.settings")
    def test_configuration_missing_db_url(self, mock_settings):
        """Test configuration check with missing DB_URL."""
        mock_settings.DB_URL = ""
        mock_settings.MODE = "DRY_RUN"
        mock_settings.MAX_STAKE_FRAC = 0.1
        mock_settings.DEFAULT_KELLY_FRACTION = 0.25

        result = check_configuration()
        assert result.status == "unhealthy"
        assert "DB_URL not configured" in result.details["issues"]

    @patch("src.health_check.settings")
    def test_configuration_invalid_mode(self, mock_settings):
        """Test configuration check with invalid MODE."""
        mock_settings.DB_URL = "sqlite:///test.db"
        mock_settings.MODE = "INVALID"
        mock_settings.MAX_STAKE_FRAC = 0.1
        mock_settings.DEFAULT_KELLY_FRACTION = 0.25

        result = check_configuration()
        assert result.status == "unhealthy"
        assert any("Invalid MODE" in issue for issue in result.details["issues"])

    @patch("src.health_check.settings")
    def test_configuration_invalid_stake_fraction(self, mock_settings):
        """Test configuration check with invalid stake fraction."""
        mock_settings.DB_URL = "sqlite:///test.db"
        mock_settings.MODE = "DRY_RUN"
        mock_settings.MAX_STAKE_FRAC = 1.5  # Invalid
        mock_settings.DEFAULT_KELLY_FRACTION = 0.25

        result = check_configuration()
        assert result.status == "unhealthy"


class TestCheckModels:
    """Tests for models health check."""

    @patch("src.health_check.Path")
    def test_models_found(self, mock_path_class):
        """Test models check when models exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.glob.return_value = [MagicMock(name="model1.pkl"), MagicMock(name="model2.pkl")]
        mock_path_class.return_value = mock_path

        result = check_models()
        assert result.status == "healthy"
        assert result.details["model_count"] == 2

    @patch("src.health_check.Path")
    def test_models_directory_not_found(self, mock_path_class):
        """Test models check when directory doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        result = check_models()
        assert result.status == "degraded"
        assert "not found" in result.message

    @patch("src.health_check.Path")
    def test_models_no_models_found(self, mock_path_class):
        """Test models check when no models exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.glob.return_value = []
        mock_path_class.return_value = mock_path

        result = check_models()
        assert result.status == "degraded"
        assert "No trained models found" in result.message


class TestRunAllHealthChecks:
    """Tests for running all health checks."""

    @patch("src.health_check.check_models")
    @patch("src.health_check.check_configuration")
    @patch("src.health_check.check_disk_space")
    @patch("src.health_check.check_database")
    def test_all_checks_healthy(self, mock_db, mock_disk, mock_config, mock_models):
        """Test when all checks are healthy."""
        mock_db.return_value = HealthCheckResult("database", "healthy")
        mock_disk.return_value = HealthCheckResult("disk_space", "healthy")
        mock_config.return_value = HealthCheckResult("configuration", "healthy")
        mock_models.return_value = HealthCheckResult("models", "healthy")

        result = run_all_health_checks()
        assert result["status"] == "healthy"
        assert result["summary"]["healthy"] == 4
        assert result["summary"]["degraded"] == 0
        assert result["summary"]["unhealthy"] == 0

    @patch("src.health_check.check_models")
    @patch("src.health_check.check_configuration")
    @patch("src.health_check.check_disk_space")
    @patch("src.health_check.check_database")
    def test_some_checks_degraded(self, mock_db, mock_disk, mock_config, mock_models):
        """Test when some checks are degraded."""
        mock_db.return_value = HealthCheckResult("database", "healthy")
        mock_disk.return_value = HealthCheckResult("disk_space", "degraded")
        mock_config.return_value = HealthCheckResult("configuration", "healthy")
        mock_models.return_value = HealthCheckResult("models", "degraded")

        result = run_all_health_checks()
        assert result["status"] == "degraded"
        assert result["summary"]["healthy"] == 2
        assert result["summary"]["degraded"] == 2

    @patch("src.health_check.check_models")
    @patch("src.health_check.check_configuration")
    @patch("src.health_check.check_disk_space")
    @patch("src.health_check.check_database")
    def test_some_checks_unhealthy(self, mock_db, mock_disk, mock_config, mock_models):
        """Test when some checks are unhealthy."""
        mock_db.return_value = HealthCheckResult("database", "unhealthy")
        mock_disk.return_value = HealthCheckResult("disk_space", "healthy")
        mock_config.return_value = HealthCheckResult("configuration", "healthy")
        mock_models.return_value = HealthCheckResult("models", "healthy")

        result = run_all_health_checks()
        assert result["status"] == "unhealthy"
        assert result["summary"]["unhealthy"] == 1


class TestPrintHealthStatus:
    """Tests for printing health status."""

    @patch("src.health_check.run_all_health_checks")
    @patch("builtins.print")
    def test_print_health_status(self, mock_print, mock_run_checks):
        """Test printing health status."""
        mock_run_checks.return_value = {
            "status": "healthy",
            "timestamp": "2025-10-23T12:00:00",
            "summary": {"total": 4, "healthy": 4, "degraded": 0, "unhealthy": 0},
            "checks": [{"name": "database", "status": "healthy", "message": "OK", "details": {}}],
        }

        print_health_status()

        # Verify print was called
        assert mock_print.called
        # Verify status was printed
        call_args = [str(call) for call in mock_print.call_args_list]
        assert any("healthy" in str(arg).lower() for arg in call_args)
