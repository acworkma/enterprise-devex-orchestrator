"""Health endpoint tests.

Project: intent-legal-contract-review
"""

from __future__ import annotations


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, client) -> None:
        """Health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client) -> None:
        """Health response contains required fields."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_status_healthy(self, client) -> None:
        """Health status is 'healthy'."""
        response = client.get("/health")
        assert response.json()["status"] == "healthy"

    def test_health_service_name(self, client) -> None:
        """Health response contains correct service name."""
        response = client.get("/health")
        assert response.json()["service"] == "intent-legal-contract-review"

    def test_health_version_format(self, client) -> None:
        """Version follows semver format."""
        response = client.get("/health")
        version = response.json()["version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
