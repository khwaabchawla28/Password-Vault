"""Shared test fixtures."""

import pytest
from pathlib import Path

from password_vault.crypto import KdfParameters, derive_key, generate_salt


@pytest.fixture
def tmp_vault_path(tmp_path: Path) -> Path:
    """Return a path for a temporary vault file."""
    return tmp_path / "test-vault.json"


@pytest.fixture
def master_password() -> str:
    """A test master password."""
    return "test-master-password-1234"


@pytest.fixture
def kdf_params() -> KdfParameters:
    """KDF parameters with test-friendly (fast) settings."""
    return KdfParameters(
        salt=generate_salt(),
        time_cost=1,
        memory_cost=8 * 4,  # minimum allowed
        parallelism=1,
    )


@pytest.fixture
def derived_key(master_password: str, kdf_params: KdfParameters) -> bytes:
    """A derived key for testing."""
    return derive_key(master_password, kdf_params)
