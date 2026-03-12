"""Storage integration tests.

Project: agent365
Tests for Azure Blob Storage connectivity.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestStorageEndpoint:
    """Tests for /storage/status endpoint."""

    def test_storage_status_connected(self, client: TestClient) -> None:
        """Storage status returns connected when accessible."""
        with patch("src.app.main.get_blob_client") as mock_client:
            mock_client.return_value.list_containers.return_value = []
            response = client.get("/storage/status")
            assert response.status_code == 200
            assert response.json()["status"] == "connected"

    def test_storage_failure_returns_503(self, client: TestClient) -> None:
        """Storage failures return 503."""
        with patch("src.app.main.get_blob_client", side_effect=Exception("Storage unavailable")):
            response = client.get("/storage/status")
            assert response.status_code == 503

    def test_storage_missing_url(self) -> None:
        """Missing STORAGE_ACCOUNT_URL raises ValueError."""
        import pytest

        from src.app.main import get_blob_client

        with patch.dict(os.environ, {"STORAGE_ACCOUNT_URL": ""}):
            with pytest.raises(ValueError, match="STORAGE_ACCOUNT_URL"):
                get_blob_client()
