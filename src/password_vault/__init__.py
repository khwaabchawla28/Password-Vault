"""
password_vault — Encrypted CLI password manager.

Argon2id key derivation + AES-256-GCM authenticated encryption.
One master password protects every credential you trust to it.
"""

from password_vault.crypto import (
    CryptoError,
    KdfParameters,
    WrongPasswordError,
)
from password_vault.vault import (
    Entry,
    EntryAlreadyExistsError,
    EntryNotFoundError,
    UnlockedVault,
    VaultAlreadyExistsError,
    VaultError,
    VaultFormatError,
    VaultNotFoundError,
)

__version__ = "1.0.0"

__all__ = [
    "CryptoError",
    "Entry",
    "EntryAlreadyExistsError",
    "EntryNotFoundError",
    "KdfParameters",
    "UnlockedVault",
    "VaultAlreadyExistsError",
    "VaultError",
    "VaultFormatError",
    "VaultNotFoundError",
    "WrongPasswordError",
]
