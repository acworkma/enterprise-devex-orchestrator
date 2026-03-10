"""API endpoint tests.

Project: intent-legal-contract-review
"""

from __future__ import annotations


class TestRootEndpoint:
    """Tests for / root endpoint."""

    def test_root_returns_200(self, client) -> None:
        """Root endpoint returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_html(self, client) -> None:
        """Root endpoint returns HTML landing page."""
        response = client.get("/")
        assert "text/html" in response.headers.get("content-type", "")
        assert "<!DOCTYPE html>" in response.text

    def test_root_contains_app_name(self, client) -> None:
        """Root HTML contains the application name."""
        response = client.get("/")
        assert "intent-legal-contract-review" in response.text

    def test_root_has_docs_link(self, client) -> None:
        """Root HTML includes docs URL."""
        response = client.get("/")
        assert 'href="/docs"' in response.text


class TestDocsEndpoint:
    """Tests for /docs OpenAPI endpoint."""

    def test_docs_returns_200(self, client) -> None:
        """Docs endpoint is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_disabled(self, client) -> None:
        """ReDoc is disabled as configured."""
        response = client.get("/redoc")
        assert response.status_code == 404


class TestNotFound:
    """Tests for undefined routes."""

    def test_undefined_route_returns_404(self, client) -> None:
        """Undefined routes return 404."""
        response = client.get("/nonexistent")
        assert response.status_code == 404
