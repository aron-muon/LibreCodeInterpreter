"""Unit tests for Settings validators.

Tests that our Settings class validates configuration values correctly.
"""

import pytest
from pydantic import ValidationError

from src.config import Settings


class TestSeccompProfileTypeValidator:
    """Tests for seccomp profile type validation."""

    def test_accepts_runtime_default(self):
        """Test that RuntimeDefault is accepted."""
        settings = Settings(k8s_seccomp_profile_type="RuntimeDefault")
        assert settings.k8s_seccomp_profile_type == "RuntimeDefault"

    def test_accepts_unconfined(self):
        """Test that Unconfined is accepted."""
        settings = Settings(k8s_seccomp_profile_type="Unconfined")
        assert settings.k8s_seccomp_profile_type == "Unconfined"

    def test_rejects_localhost(self):
        """Test that Localhost is rejected (requires localhostProfile path)."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(k8s_seccomp_profile_type="Localhost")

        errors = exc_info.value.errors()
        assert any("seccomp_profile_type" in str(e) for e in errors)

    def test_rejects_invalid_type(self):
        """Test that arbitrary invalid types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(k8s_seccomp_profile_type="InvalidType")

        errors = exc_info.value.errors()
        assert any("seccomp_profile_type" in str(e) for e in errors)

    def test_default_is_runtime_default(self):
        """Test that the default seccomp profile type is RuntimeDefault."""
        settings = Settings()
        assert settings.k8s_seccomp_profile_type == "RuntimeDefault"
