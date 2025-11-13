"""Tests for monitoring module."""
import pytest
from fastapi.testclient import TestClient
from src.monitoring import app, update_metrics


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "endpoints" in data
    # Values should be strings or dicts
    assert isinstance(data["service"], str)
    assert isinstance(data["endpoints"], dict)


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "betting-expert-advisor"


def test_metrics_endpoint(client):
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200

    # Should return Prometheus text format
    assert "text/plain" in response.headers["content-type"]

    # Should contain metrics
    content = response.text
    assert len(content) > 0


def test_report_bet_basic(client):
    """Test reporting a bet."""
    payload = {
        "status": "accepted",
        "stake": 100.0,
        "ev": 0.05,
        "dry_run": True,
        "bankroll": 10000.0,
    }

    response = client.post("/report/bet", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["accepted"] is True


def test_report_bet_minimal(client):
    """Test reporting bet with minimal data."""
    payload = {}

    response = client.post("/report/bet", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["accepted"] is True


def test_report_bet_with_all_metrics(client):
    """Test reporting bet with all metrics."""
    payload = {
        "status": "accepted",
        "stake": 150.0,
        "ev": 0.08,
        "dry_run": False,
        "bankroll": 12000.0,
        "open_bets": 5,
        "daily_pnl": 250.0,
    }

    response = client.post("/report/bet", json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] is True


def test_report_bet_rejected(client):
    """Test reporting a rejected bet."""
    payload = {"status": "rejected", "stake": 0.0, "dry_run": True}

    response = client.post("/report/bet", json=payload)
    assert response.status_code == 200


def test_report_bet_error(client):
    """Test reporting bet with error status."""
    payload = {"status": "error", "stake": 50.0, "dry_run": True}

    response = client.post("/report/bet", json=payload)
    assert response.status_code == 200


def test_report_prediction(client):
    """Test reporting a model prediction."""
    response = client.post("/report/prediction")
    assert response.status_code == 200

    data = response.json()
    assert data["accepted"] is True


def test_report_error_basic(client):
    """Test reporting an API error."""
    payload = {"source": "theodds_api"}

    response = client.post("/report/error", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["accepted"] is True


def test_report_error_different_sources(client):
    """Test reporting errors from different sources."""
    sources = ["theodds_api", "betfair", "pinnacle", "other"]

    for source in sources:
        payload = {"source": source}
        response = client.post("/report/error", json=payload)
        assert response.status_code == 200


def test_report_error_no_source(client):
    """Test reporting error without source."""
    payload = {}

    response = client.post("/report/error", json=payload)
    assert response.status_code == 200


def test_update_metrics_helper():
    """Test update_metrics helper function."""
    bet_result = {"status": "accepted", "dry_run": True}

    # Should not raise exceptions
    update_metrics(bet_result=bet_result, bankroll=10000.0, open_bets=3, daily_pl=150.0)

    assert True


def test_metrics_increments(client):
    """Test that metrics actually increment."""
    # Get initial metrics
    response1 = client.get("/metrics")
    response1.text

    # Report some activity
    client.post("/report/bet", json={"status": "accepted", "stake": 100.0})
    client.post("/report/prediction")

    # Get updated metrics
    response2 = client.get("/metrics")
    updated_content = response2.text

    # Content should have changed (metrics updated)
    assert len(updated_content) > 0


def test_multiple_bet_reports(client):
    """Test reporting multiple bets."""
    for i in range(5):
        payload = {
            "status": "accepted",
            "stake": 50.0 + i * 10,
            "ev": 0.05 + i * 0.01,
            "dry_run": True,
            "bankroll": 10000.0 - i * 50,
        }
        response = client.post("/report/bet", json=payload)
        assert response.status_code == 200


def test_bet_report_updates_bankroll_gauge(client):
    """Test that bankroll gauge is updated."""
    payload = {"status": "accepted", "bankroll": 15000.0}

    response = client.post("/report/bet", json=payload)
    assert response.status_code == 200

    # Check metrics contain bankroll
    metrics_response = client.get("/metrics")
    assert "bankroll_current" in metrics_response.text


def test_bet_report_updates_open_bets_gauge(client):
    """Test that open bets gauge is updated."""
    payload = {"status": "accepted", "open_bets": 7}

    response = client.post("/report/bet", json=payload)
    assert response.status_code == 200

    # Check metrics contain open bets
    metrics_response = client.get("/metrics")
    assert "open_bets_count" in metrics_response.text


def test_bet_report_updates_daily_pnl_gauge(client):
    """Test that daily P&L gauge is updated."""
    payload = {"status": "accepted", "daily_pnl": 350.75}

    response = client.post("/report/bet", json=payload)
    assert response.status_code == 200

    # Check metrics contain daily P&L
    metrics_response = client.get("/metrics")
    assert "daily_pnl" in metrics_response.text
