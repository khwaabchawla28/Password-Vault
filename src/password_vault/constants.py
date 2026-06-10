"""
constants.py

Central configuration — every magic number, path, and string lives here.
Change a value once and the entire project updates.

Sections:
  1. Argon2id KDF parameters
  2. AES-256-GCM cipher parameters
  3. Vault file format
  4. Password generator settings
  5. CLI prompts and messages
"""

from pathlib import Path
from typing import Final


# =============================================================================
# 1. Argon2id — Key Derivation Function
# =============================================================================
# Argon2id turns a human password into a 32-byte cryptographic key.
# It is deliberately slow and memory-hungry to make brute-force attacks
# impractical. These parameters follow OWASP's Password Storage Cheat Sheet.

# Passes over the memory buffer — more passes = slower = harder to crack
ARGON2_TIME_COST: Final[int] = 3

# Memory per derivation in KiB. 65536 KiB = 64 MiB. This is the main
# knob that defeats GPU/ASIC attackers — they have compute but limited
# fast memory per core.
ARGON2_MEMORY_KIB: Final[int] = 65536

# Parallel threads. 4 is safe on any modern CPU.
ARGON2_PARALLELISM: Final[int] = 4

# Salt = random data mixed into the password before hashing.
# Makes identical passwords produce different keys.
# 16 bytes (128 bits) is the standard recommendation.
SALT_LENGTH_BYTES: Final[int] = 16

# Argon2 algorithmic floors — values below these are nonsensical.
# Used to validate parameters loaded from a vault file on disk.
ARGON2_TIME_COST_MIN: Final[int] = 1
ARGON2_PARALLELISM_MIN: Final[int] = 1
ARGON2_MEMORY_KIB_PER_LANE_MIN: Final[int] = 8


# =============================================================================
# 2. AES-256-GCM — Authenticated Encryption
# =============================================================================
# AES-256-GCM provides confidentiality (encryption) and authenticity
# (tamper detection) in a single primitive. The nonce must NEVER be
# reused with the same key.

# Nonce size in bytes. 12 bytes (96 bits) is the standard for GCM.
NONCE_LENGTH_BYTES: Final[int] = 12

# AES-256 requires a 32-byte (256-bit) key.
KEY_LENGTH_BYTES: Final[int] = 32


# =============================================================================
# 3. Vault File Format
# =============================================================================
# The vault is a JSON file with an outer "envelope" containing KDF params
# and an encrypted blob. The blob, once decrypted, is another JSON dict
# of credential entries.

VAULT_VERSION: Final[int] = 1

# Default vault location
DEFAULT_VAULT_DIR: Final[Path] = Path.home() / ".password-vault"
DEFAULT_VAULT_FILE: Final[str] = "vault.json"
DEFAULT_VAULT_PATH: Final[Path] = DEFAULT_VAULT_DIR / DEFAULT_VAULT_FILE

# File permissions — owner read/write only (0600)
VAULT_FILE_MODE: Final[int] = 0o600

# JSON keys for the outer envelope
KEY_VERSION: Final[str] = "version"
KEY_KDF: Final[str] = "kdf"
KEY_CIPHER: Final[str] = "cipher"

# KDF sub-keys
KEY_KDF_NAME: Final[str] = "name"
KEY_KDF_SALT: Final[str] = "salt"
KEY_KDF_TIME_COST: Final[str] = "time_cost"
KEY_KDF_MEMORY_COST: Final[str] = "memory_cost"
KEY_KDF_PARALLELISM: Final[str] = "parallelism"
KDF_NAME_ARGON2ID: Final[str] = "argon2id"

# Cipher sub-keys
KEY_CIPHER_NAME: Final[str] = "name"
KEY_CIPHER_NONCE: Final[str] = "nonce"
KEY_CIPHERTEXT: Final[str] = "ciphertext"
CIPHER_NAME_AES256GCM: Final[str] = "aes-256-gcm"

# Entry fields
KEY_ENTRIES: Final[str] = "entries"
KEY_USERNAME: Final[str] = "username"
KEY_PASSWORD: Final[str] = "password"
KEY_URL: Final[str] = "url"
KEY_NOTES: Final[str] = "notes"
KEY_CREATED_AT: Final[str] = "created_at"
KEY_UPDATED_AT: Final[str] = "updated_at"


# =============================================================================
# 4. Password Generator
# =============================================================================
LOWERCASE_LETTERS: Final[str] = "abcdefghijklmnopqrstuvwxyz"
UPPERCASE_LETTERS: Final[str] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS: Final[str] = "0123456789"
SAFE_SYMBOLS: Final[str] = "!@#$%^&*()-_=+[]{}|;:,.<>?"

MINIMUM_GENERATED_PASSWORD_LENGTH: Final[int] = 8
DEFAULT_GENERATED_PASSWORD_LENGTH: Final[int] = 20

# Master password minimum length
MINIMUM_MASTER_PASSWORD_LENGTH: Final[int] = 12


# =============================================================================
# 5. CLI Prompts and Messages
# =============================================================================
PROMPT_MASTER_PASSWORD: Final[str] = "Master password: "
PROMPT_MASTER_PASSWORD_CONFIRM: Final[str] = "Confirm master password: "
PROMPT_MASTER_PASSWORD_NEW: Final[str] = "New master password: "
PROMPT_ENTRY_USERNAME: Final[str] = "Username: "
PROMPT_ENTRY_PASSWORD: Final[str] = "Password (hidden): "
PROMPT_ENTRY_URL: Final[str] = "URL (optional, press Enter to skip): "
PROMPT_ENTRY_NOTES: Final[str] = "Notes (optional, press Enter to skip): "

MSG_VAULT_CREATED: Final[str] = "Vault created at {path}"
MSG_VAULT_ALREADY_EXISTS: Final[str] = "Vault already exists at {path}"
MSG_VAULT_NOT_FOUND: Final[str] = (
    "No vault found. Run 'pv init' to create one."
)
MSG_VAULT_EMPTY: Final[str] = "Vault is empty — no entries yet."

MSG_ENTRY_ADDED: Final[str] = "Added entry: {name}"
MSG_ENTRY_DELETED: Final[str] = "Deleted entry: {name}"
MSG_ENTRY_NOT_FOUND: Final[str] = "No entry named '{name}' in vault."
MSG_ENTRY_ALREADY_EXISTS: Final[str] = "Entry '{name}' already exists."

MSG_MASTER_PASSWORD_CHANGED: Final[str] = "Master password changed. Vault re-encrypted."
MSG_MASTER_PASSWORD_EMPTY: Final[str] = "Password cannot be empty."
MSG_MASTER_PASSWORD_TOO_SHORT: Final[str] = (
    "Password must be at least {min} characters."
)
MSG_PASSWORDS_DO_NOT_MATCH: Final[str] = "Passwords do not match."
MSG_WRONG_MASTER_PASSWORD: Final[str] = "Wrong password or corrupted vault."
