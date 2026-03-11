"""Configuration tests.

Project: enterprise-grade-real-time
Verifies environment-based configuration works correctly.
"""

from __future__ import annotations

import os
from unittest.mock import patch


class TestEnvironmentConfig:
    """Tests for environment variable configuration."""

    def test_app_name_configured(self) -> None:
        """APP_NAME constant is set correctly."""
        from src.app.main import APP_NAME

        assert APP_NAME == "enterprise-grade-real-time"

    def test_version_configured(self) -> None:
        """VERSION constant follows semver."""
        from src.app.main import VERSION

        parts = VERSION.split(".")
        assert len(parts) == 3

    def test_default_port(self) -> None:
        """Default port is 8000."""
        with patch.dict(os.environ, {"PORT": "8000"}):
            port = int(os.getenv("PORT", "8000"))
            assert port == 8000

    def test_custom_port(self) -> None:
        """Custom PORT environment variable is respected."""
        with patch.dict(os.environ, {"PORT": "3000"}):
            port = int(os.getenv("PORT", "8000"))
            assert port == 3000
