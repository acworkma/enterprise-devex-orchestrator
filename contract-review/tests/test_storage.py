"""Storage integration tests.

Project: intent-legal-contract-review
Tests for Azure Blob Storage connectivity.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestStorageEndpoint:
    """Tests for /storage/status endpoint."""

    def test_storage_status_connected(self, client) -> None:
        """Storage status returns connected when accessible."""
        with patch("src.app.main.get_blob_client") as mock_client:
            mock_client.return_value.list_containers.return_value = []
            response = client.get("/storage/status")
            assert response.status_code == 200
            assert response.json()["status"] == "connected"

    def test_storage_failure_returns_503(self, client) -> None:
        """Storage failures return 503."""
        with patch("src.app.main.get_blob_client", side_effect=Exception("Storage unavailable")):
            response = client.get("/storage/status")
            assert response.status_code == 503

    def test_storage_missing_url(self) -> None:
        """Missing STORAGE_ACCOUNT_URL raises ValueError."""
        from src.app.main import get_blob_client

        with (
            patch.dict(os.environ, {"STORAGE_ACCOUNT_URL": ""}),
            pytest.raises(ValueError, match="STORAGE_ACCOUNT_URL"),
        ):
            get_blob_client()
