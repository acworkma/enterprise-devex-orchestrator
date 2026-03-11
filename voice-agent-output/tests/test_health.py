"""Health endpoint tests.

Project: enterprise-grade-real-time
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client: TestClient) -> None:
        """Health response contains required fields."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_status_healthy(self, client: TestClient) -> None:
        """Health status is 'healthy'."""
        response = client.get("/health")
        assert response.json()["status"] == "healthy"

    def test_health_service_name(self, client: TestClient) -> None:
        """Health response contains correct service name."""
        response = client.get("/health")
        assert response.json()["service"] == "enterprise-grade-real-time"

    def test_health_version_format(self, client: TestClient) -> None:
        """Version follows semver format."""
        response = client.get("/health")
        version = response.json()["version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
