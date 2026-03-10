"""Security tests for the application.

Project: intent-legal-contract-review
Tests cover: input validation, auth patterns, response headers.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestKeyvaultSecurity:
    """Key Vault integration security tests."""

    def test_keyvault_uses_managed_identity(self, client) -> None:
        """Key Vault client uses DefaultAzureCredential (Managed Identity)."""
        with (
            patch("src.app.main.DefaultAzureCredential") as mock_cred,
            patch("src.app.main.SecretClient") as mock_kv,
        ):
            mock_kv.return_value.list_properties_of_secrets.return_value = []
            client.get("/keyvault/status")
            mock_cred.assert_called()

    def test_keyvault_failure_returns_503(self, client) -> None:
        """Key Vault failures return 503 Service Unavailable."""
        with patch("src.app.main.get_keyvault_client", side_effect=Exception("Connection failed")):
            response = client.get("/keyvault/status")
            assert response.status_code == 503
            assert "error" in response.json()["status"]

    def test_keyvault_missing_vault_name(self) -> None:
        """Missing Key Vault configuration raises ValueError."""
        from src.app.main import get_keyvault_client

        with (
            patch.dict(os.environ, {"KEY_VAULT_NAME": "", "KEY_VAULT_URI": ""}),
            pytest.raises(ValueError, match="KEY_VAULT"),
        ):
            get_keyvault_client()


class TestResponseHeaders:
    """Response header security tests."""

    def test_json_content_type(self, client) -> None:
        """API responses use application/json content type."""
        response = client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")


class TestInputValidation:
    """Input validation and injection prevention tests."""

    def test_unknown_query_params_ignored(self, client) -> None:
        """Unknown query parameters are safely ignored."""
        response = client.get("/health?inject=<script>alert(1)</script>")
        assert response.status_code == 200

    def test_path_traversal_rejected(self, client) -> None:
        """Path traversal attempts return 404 not 500."""
        response = client.get("/../../../etc/passwd")
        assert response.status_code in (404, 307)
