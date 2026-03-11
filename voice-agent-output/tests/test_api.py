"""API endpoint tests.

Project: enterprise-grade-real-time
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestRootEndpoint:
    """Tests for / root endpoint."""

    def test_root_returns_200(self, client: TestClient) -> None:
        """Root endpoint returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_structure(self, client: TestClient) -> None:
        """Root response returns HTML content."""
        response = client.get("/")
        assert "<!DOCTYPE html>" in response.text
        assert "enterprise-grade-real-time" in response.text

    def test_root_status_running(self, client: TestClient) -> None:
        """Root HTML includes running status indicator."""
        response = client.get("/")
        assert "Status: Running" in response.text

    def test_root_has_docs_link(self, client: TestClient) -> None:
        """Root HTML includes docs URL."""
        response = client.get("/")
        assert 'href="/docs"' in response.text


class TestDocsEndpoint:
    """Tests for /docs OpenAPI endpoint."""

    def test_docs_returns_200(self, client: TestClient) -> None:
        """Docs endpoint is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_disabled(self, client: TestClient) -> None:
        """ReDoc is disabled as configured."""
        response = client.get("/redoc")
        assert response.status_code == 404


class TestNotFound:
    """Tests for undefined routes."""

    def test_undefined_route_returns_404(self, client: TestClient) -> None:
        """Undefined routes return 404."""
        response = client.get("/nonexistent")
        assert response.status_code == 404
