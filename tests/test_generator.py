"""Tests for the password generator."""

import pytest

from password_vault.generator import (
    PasswordTooShortError,
    generate_password,
)
from password_vault.constants import (
    DIGITS,
    LOWERCASE_LETTERS,
    MINIMUM_GENERATED_PASSWORD_LENGTH,
    SAFE_SYMBOLS,
    UPPERCASE_LETTERS,
)


class TestGeneratePassword:
    def test_default_length(self):
        pw = generate_password()
        assert len(pw) == 20

    def test_custom_length(self):
        pw = generate_password(32)
        assert len(pw) == 32

    def test_minimum_length(self):
        pw = generate_password(MINIMUM_GENERATED_PASSWORD_LENGTH)
        assert len(pw) == MINIMUM_GENERATED_PASSWORD_LENGTH

    def test_too_short_raises(self):
        with pytest.raises(PasswordTooShortError):
            generate_password(3)

    def test_contains_lowercase(self):
        pw = generate_password(100)
        assert any(c in LOWERCASE_LETTERS for c in pw)

    def test_contains_uppercase(self):
        pw = generate_password(100)
        assert any(c in UPPERCASE_LETTERS for c in pw)

    def test_contains_digits(self):
        pw = generate_password(100)
        assert any(c in DIGITS for c in pw)

    def test_contains_symbols(self):
        pw = generate_password(100)
        assert any(c in SAFE_SYMBOLS for c in pw)

    def test_no_symbols(self):
        pw = generate_password(100, use_symbols=False)
        assert all(c not in SAFE_SYMBOLS for c in pw)

    def test_no_digits(self):
        pw = generate_password(100, use_digits=False)
        assert all(c not in DIGITS for c in pw)

    def test_lowercase_only(self):
        pw = generate_password(100, use_uppercase=False, use_digits=False, use_symbols=False)
        assert all(c in LOWERCASE_LETTERS for c in pw)

    def test_all_false_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            generate_password(
                20,
                use_lowercase=False,
                use_uppercase=False,
                use_digits=False,
                use_symbols=False,
            )

    def test_randomness(self):
        """10 runs should produce 10 different passwords."""
        passwords = {generate_password(20) for _ in range(10)}
        assert len(passwords) == 10

    def test_length_too_short_for_pools(self):
        """Length must be >= number of enabled pools."""
        with pytest.raises(PasswordTooShortError, match="must be >="):
            generate_password(2, use_lowercase=True, use_uppercase=True, use_digits=True)
