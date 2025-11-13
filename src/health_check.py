"""Health check utilities for monitoring system status.

This module provides health check functions to verify that all system
components are functioning correctly.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.config import settings
from src.db import BetRecord, get_session
from src.logging_config import get_logger

logger = get_logger(__name__)


class HealthCheckResult:
    """Result of a health check."""

    def __init__(self, name: str, status: str, message: str = "", details: Dict[str, Any] = None):
        """Initialize health check result.

        Args:
            name: Name of the check
            status: Status ('healthy', 'degraded', 'unhealthy')
            message: Optional message
            details: Optional additional details
        """
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    @property
    def is_healthy(self) -> bool:
        """Check if status is healthy."""
        return self.status == "healthy"


def check_database() -> HealthCheckResult:
    """Check database connectivity and basic operations.

    Returns:
        HealthCheckResult with database status
    """
    try:
        with get_session() as session:
            # Try a simple query
            count = session.query(BetRecord).count()

            return HealthCheckResult(
                name="database",
                status="healthy",
                message="Database connection successful",
                details={"bet_count": count},
            )
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return HealthCheckResult(
            name="database", status="unhealthy", message=f"Database error: {str(e)}"
        )


def check_disk_space(min_free_gb: float = 1.0) -> HealthCheckResult:
    """Check available disk space.

    Args:
        min_free_gb: Minimum free space in GB

    Returns:
        HealthCheckResult with disk space status
    """
    try:
        import shutil

        # Check data directory
        data_dir = Path("data")
        if data_dir.exists():
            stat = shutil.disk_usage(data_dir)
            free_gb = stat.free / (1024**3)
            total_gb = stat.total / (1024**3)
            used_percent = (stat.used / stat.total) * 100

            if free_gb < min_free_gb:
                return HealthCheckResult(
                    name="disk_space",
                    status="degraded",
                    message=f"Low disk space: {free_gb:.2f} GB free",
                    details={
                        "free_gb": round(free_gb, 2),
                        "total_gb": round(total_gb, 2),
                        "used_percent": round(used_percent, 2),
                    },
                )

            return HealthCheckResult(
                name="disk_space",
                status="healthy",
                message=f"Sufficient disk space: {free_gb:.2f} GB free",
                details={
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(total_gb, 2),
                    "used_percent": round(used_percent, 2),
                },
            )
        else:
            return HealthCheckResult(
                name="disk_space", status="degraded", message="Data directory not found"
            )
    except Exception as e:
        logger.error(f"Disk space check failed: {e}")
        return HealthCheckResult(
            name="disk_space", status="unhealthy", message=f"Error checking disk space: {str(e)}"
        )


def check_configuration() -> HealthCheckResult:
    """Check configuration validity.

    Returns:
        HealthCheckResult with configuration status
    """
    try:
        issues = []

        # Check critical settings
        if not settings.DB_URL:
            issues.append("DB_URL not configured")

        if settings.MODE not in ["DRY_RUN", "LIVE"]:
            issues.append(f"Invalid MODE: {settings.MODE}")

        if settings.MAX_STAKE_FRAC <= 0 or settings.MAX_STAKE_FRAC > 1:
            issues.append(f"Invalid MAX_STAKE_FRAC: {settings.MAX_STAKE_FRAC}")

        if settings.DEFAULT_KELLY_FRACTION <= 0 or settings.DEFAULT_KELLY_FRACTION > 1:
            issues.append(f"Invalid DEFAULT_KELLY_FRACTION: {settings.DEFAULT_KELLY_FRACTION}")

        if issues:
            return HealthCheckResult(
                name="configuration",
                status="unhealthy",
                message="Configuration issues detected",
                details={"issues": issues},
            )

        return HealthCheckResult(
            name="configuration",
            status="healthy",
            message="Configuration valid",
            details={"mode": settings.MODE, "env": settings.ENV},
        )
    except Exception as e:
        logger.error(f"Configuration check failed: {e}")
        return HealthCheckResult(
            name="configuration",
            status="unhealthy",
            message=f"Error checking configuration: {str(e)}",
        )


def check_models() -> HealthCheckResult:
    """Check if ML models are available.

    Returns:
        HealthCheckResult with model status
    """
    try:
        models_dir = Path("models")
        if not models_dir.exists():
            return HealthCheckResult(
                name="models", status="degraded", message="Models directory not found"
            )

        model_files = list(models_dir.glob("*.pkl"))

        if not model_files:
            return HealthCheckResult(
                name="models",
                status="degraded",
                message="No trained models found",
                details={"models_dir": str(models_dir)},
            )

        return HealthCheckResult(
            name="models",
            status="healthy",
            message=f"Found {len(model_files)} model(s)",
            details={"model_count": len(model_files), "models": [f.name for f in model_files]},
        )
    except Exception as e:
        logger.error(f"Models check failed: {e}")
        return HealthCheckResult(
            name="models", status="unhealthy", message=f"Error checking models: {str(e)}"
        )


def run_all_health_checks() -> Dict[str, Any]:
    """Run all health checks and return comprehensive status.

    Returns:
        Dictionary with overall health status and individual check results
    """
    checks = [check_database(), check_disk_space(), check_configuration(), check_models()]

    # Determine overall status
    if all(check.is_healthy for check in checks):
        overall_status = "healthy"
    elif any(check.status == "unhealthy" for check in checks):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": [check.to_dict() for check in checks],
        "summary": {
            "total": len(checks),
            "healthy": sum(1 for c in checks if c.status == "healthy"),
            "degraded": sum(1 for c in checks if c.status == "degraded"),
            "unhealthy": sum(1 for c in checks if c.status == "unhealthy"),
        },
    }


def print_health_status() -> None:
    """Print health status to console in a readable format."""
    results = run_all_health_checks()

    print("\n" + "=" * 60)
    print(f"SYSTEM HEALTH CHECK - {results['timestamp']}")
    print("=" * 60)
    print(f"\nOverall Status: {results['status'].upper()}")
    print(f"\nSummary: {results['summary']['healthy']}/{results['summary']['total']} checks passed")
    print("\nDetailed Results:")
    print("-" * 60)

    for check in results["checks"]:
        status_symbol = {"healthy": "✓", "degraded": "⚠", "unhealthy": "✗"}.get(
            check["status"], "?"
        )

        print(f"\n{status_symbol} {check['name'].upper()}: {check['status']}")
        if check["message"]:
            print(f"  Message: {check['message']}")
        if check["details"]:
            print(f"  Details: {check['details']}")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    # Run health checks when executed directly
    print_health_status()
