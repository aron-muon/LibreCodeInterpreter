"""Tests for sidecar network isolation functionality.

These tests verify that the network isolation overrides are correctly applied
to environment variables for languages that require network access (e.g., Go).
"""

import pytest


def apply_network_isolation_overrides(env: dict[str, str], language: str, network_isolated: bool) -> dict[str, str]:
    """Replicate the network isolation logic from sidecar for testing.

    This mirrors apply_network_isolation_overrides() from docker/sidecar/main.py
    """
    if not network_isolated:
        return env

    # Go: Disable module proxy and checksum database for offline operation
    if language in ("go",):
        env["GOPROXY"] = "off"
        env["GOSUMDB"] = "off"

    return env


class TestNetworkIsolationOverrides:
    """Tests for apply_network_isolation_overrides function."""

    def test_no_override_when_not_isolated(self):
        """Environment should not be modified when network isolation is disabled."""
        env = {
            "PATH": "/usr/local/go/bin:/usr/bin",
            "GOPROXY": "https://proxy.golang.org,direct",
            "GOSUMDB": "sum.golang.org",
        }
        original_goproxy = env["GOPROXY"]
        original_gosumdb = env["GOSUMDB"]

        result = apply_network_isolation_overrides(env, "go", network_isolated=False)

        assert result["GOPROXY"] == original_goproxy
        assert result["GOSUMDB"] == original_gosumdb

    def test_go_override_when_isolated(self):
        """Go environment variables should be set to 'off' when isolated."""
        env = {
            "PATH": "/usr/local/go/bin:/usr/bin",
            "GOPROXY": "https://proxy.golang.org,direct",
            "GOSUMDB": "sum.golang.org",
            "GOCACHE": "/mnt/data/go-build",
        }

        result = apply_network_isolation_overrides(env, "go", network_isolated=True)

        assert result["GOPROXY"] == "off"
        assert result["GOSUMDB"] == "off"
        # Other env vars should be preserved
        assert result["GOCACHE"] == "/mnt/data/go-build"
        assert result["PATH"] == "/usr/local/go/bin:/usr/bin"

    def test_python_not_affected(self):
        """Python environment should not be affected by network isolation."""
        env = {
            "PATH": "/usr/local/bin:/usr/bin",
            "PYTHONPATH": "/app",
        }
        original_env = env.copy()

        result = apply_network_isolation_overrides(env, "python", network_isolated=True)

        assert result == original_env

    def test_javascript_not_affected(self):
        """JavaScript environment should not be affected by network isolation."""
        env = {
            "PATH": "/usr/local/bin:/usr/bin",
            "NODE_ENV": "production",
        }
        original_env = env.copy()

        result = apply_network_isolation_overrides(env, "js", network_isolated=True)

        assert result == original_env

    def test_go_env_created_if_missing(self):
        """Go proxy vars should be set even if not present in original env."""
        env = {
            "PATH": "/usr/local/go/bin:/usr/bin",
        }

        result = apply_network_isolation_overrides(env, "go", network_isolated=True)

        assert result["GOPROXY"] == "off"
        assert result["GOSUMDB"] == "off"

    def test_preserves_other_go_env_vars(self):
        """Other Go environment variables should be preserved."""
        env = {
            "PATH": "/usr/local/go/bin:/usr/bin",
            "GOPROXY": "https://proxy.golang.org,direct",
            "GOSUMDB": "sum.golang.org",
            "GO111MODULE": "on",
            "GOCACHE": "/mnt/data/go-build",
            "GOMODCACHE": "/go/pkg/mod",
        }

        result = apply_network_isolation_overrides(env, "go", network_isolated=True)

        assert result["GOPROXY"] == "off"
        assert result["GOSUMDB"] == "off"
        assert result["GO111MODULE"] == "on"
        assert result["GOCACHE"] == "/mnt/data/go-build"
        assert result["GOMODCACHE"] == "/go/pkg/mod"


class TestNetworkIsolationEnvParsing:
    """Tests for NETWORK_ISOLATED environment variable parsing."""

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("Yes", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("", False),
            ("invalid", False),
        ],
    )
    def test_network_isolated_parsing(self, env_value: str, expected: bool):
        """Test various string values for NETWORK_ISOLATED env var parsing."""
        # Replicate the parsing logic from sidecar
        parsed = env_value.lower() in ("true", "1", "yes")
        assert parsed == expected


class TestLanguageSpecificBehavior:
    """Tests for language-specific network isolation behavior."""

    def test_all_supported_languages(self):
        """Test network isolation behavior for all supported languages."""
        base_env = {"PATH": "/usr/bin"}
        languages_affected = ["go"]
        languages_not_affected = [
            "python",
            "py",
            "javascript",
            "js",
            "typescript",
            "ts",
            "rust",
            "rs",
            "java",
            "c",
            "cpp",
            "php",
            "r",
            "fortran",
            "f90",
            "d",
            "dlang",
        ]

        for lang in languages_affected:
            env = base_env.copy()
            result = apply_network_isolation_overrides(env, lang, network_isolated=True)
            assert "GOPROXY" in result, f"{lang} should have GOPROXY set"
            assert result["GOPROXY"] == "off", f"{lang} should have GOPROXY=off"

        for lang in languages_not_affected:
            env = base_env.copy()
            result = apply_network_isolation_overrides(env, lang, network_isolated=True)
            assert "GOPROXY" not in result, f"{lang} should not have GOPROXY set"
