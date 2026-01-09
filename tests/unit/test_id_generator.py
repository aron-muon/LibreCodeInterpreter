"""Unit tests for the ID generator utilities."""

import string

import pytest

from src.utils.id_generator import (
    generate_execution_id,
    generate_file_id,
    generate_nanoid,
    generate_session_id,
)

ALPHANUMERIC = string.ascii_letters + string.digits
FULL_ALPHABET = ALPHANUMERIC + "_-"


class TestGenerateNanoid:
    """Tests for the generate_nanoid function."""

    def test_default_length_is_21(self):
        """Test that default length is 21 characters."""
        result = generate_nanoid()
        assert len(result) == 21

    def test_custom_length(self):
        """Test that custom length is respected."""
        for length in [5, 10, 50, 100]:
            result = generate_nanoid(length)
            assert len(result) == length

    def test_first_char_is_alphanumeric(self):
        """Test that first character is always alphanumeric for Kubernetes compatibility."""
        for _ in range(100):
            result = generate_nanoid()
            assert result[0] in ALPHANUMERIC, f"First char '{result[0]}' not alphanumeric in '{result}'"

    def test_last_char_is_alphanumeric(self):
        """Test that last character is always alphanumeric for Kubernetes compatibility."""
        for _ in range(100):
            result = generate_nanoid()
            assert result[-1] in ALPHANUMERIC, f"Last char '{result[-1]}' not alphanumeric in '{result}'"

    def test_all_chars_valid(self):
        """Test that all characters are from the valid alphabet."""
        for _ in range(100):
            result = generate_nanoid()
            for char in result:
                assert char in FULL_ALPHABET, f"Invalid char '{char}' in '{result}'"

    def test_length_one(self):
        """Test edge case of length 1."""
        result = generate_nanoid(1)
        assert len(result) == 1
        assert result in ALPHANUMERIC

    def test_length_two(self):
        """Test edge case of length 2."""
        result = generate_nanoid(2)
        assert len(result) == 2
        assert result[0] in ALPHANUMERIC
        assert result[1] in ALPHANUMERIC

    def test_uniqueness(self):
        """Test that generated IDs are unique."""
        ids = [generate_nanoid() for _ in range(1000)]
        assert len(set(ids)) == 1000

    def test_matches_librechat_pattern(self):
        """Test that IDs match LibreChat's validation pattern."""
        import re

        pattern = re.compile(r"^[A-Za-z0-9_-]{21}$")
        for _ in range(100):
            result = generate_nanoid()
            assert pattern.match(result), f"'{result}' doesn't match LibreChat pattern"

    def test_valid_kubernetes_label(self):
        """Test that IDs are valid Kubernetes label values."""
        import re

        # Kubernetes label regex: (([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?
        pattern = re.compile(r"^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?$")
        for _ in range(100):
            result = generate_nanoid()
            assert pattern.match(result), f"'{result}' is not a valid Kubernetes label"


class TestConvenienceFunctions:
    """Tests for the convenience ID generation functions."""

    def test_generate_session_id_length(self):
        """Test that session IDs are 21 characters."""
        result = generate_session_id()
        assert len(result) == 21

    def test_generate_file_id_length(self):
        """Test that file IDs are 21 characters."""
        result = generate_file_id()
        assert len(result) == 21

    def test_generate_execution_id_length(self):
        """Test that execution IDs are 21 characters."""
        result = generate_execution_id()
        assert len(result) == 21

    def test_all_convenience_functions_kubernetes_compatible(self):
        """Test that all convenience functions produce Kubernetes-compatible IDs."""
        for func in [generate_session_id, generate_file_id, generate_execution_id]:
            result = func()
            assert result[0] in ALPHANUMERIC
            assert result[-1] in ALPHANUMERIC
