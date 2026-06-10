"""
vault.py

The encrypted vault — storage layer for credential entries.

On-disk format: JSON envelope wrapping an encrypted JSON blob.

  Outer envelope (plaintext, always readable):
    {
      "version": 1,
      "kdf": {"name": "argon2id", "salt": "...", ...},
      "cipher": {"name": "aes-256-gcm", "nonce": "...", "ciphertext": "..."}
    }

  Inner payload (encrypted, only readable with the master password):
    {
      "github": {
        "username": "alice",
        "password": "hunter2",
        "url": "https://github.com",
        "notes": "",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00"
      }
    }

Atomic + durable writes:
  tmp file → fsync → atomic rename → parent dir fsync
  At any instant, readers see either the OLD complete file or the NEW
  complete file — never half of either.

File locking:
  Advisory fcntl.LOCK_EX on a sidecar .lock file serializes concurrent
  pv invocations so two processes cannot overwrite each other.
"""

from __future__ import annotations

import base64
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from password_vault.constants import (
    CIPHER_NAME_AES256GCM,
    DEFAULT_VAULT_PATH,
    KEY_CIPHER,
    KEY_CIPHER_NAME,
    KEY_CIPHERTEXT,
    KEY_CREATED_AT,
    KEY_ENTRIES,
    KEY_KDF,
    KEY_KDF_MEMORY_COST,
    KEY_KDF_NAME,
    KEY_KDF_PARALLELISM,
    KEY_KDF_SALT,
    KEY_KDF_TIME_COST,
    KEY_NOTES,
    KEY_PASSWORD,
    KEY_URL,
    KEY_USERNAME,
    KEY_UPDATED_AT,
    KEY_VERSION,
    KDF_NAME_ARGON2ID,
    VAULT_FILE_MODE,
    VAULT_VERSION,
)
from password_vault.crypto import (
    KdfParameters,
    WrongPasswordError,
    decrypt,
    derive_key,
    encrypt,
    generate_salt,
)


# =============================================================================
# Exceptions
# =============================================================================


class VaultError(Exception):
    """Base exception for vault operations."""


class VaultNotFoundError(VaultError):
    """The vault file does not exist."""


class VaultAlreadyExistsError(VaultError):
    """Tried to create a vault that already exists."""


class VaultFormatError(VaultError):
    """The vault file is malformed or contains invalid parameters."""


class EntryNotFoundError(VaultError):
    """No entry with the given name exists in the vault."""


class EntryAlreadyExistsError(VaultError):
    """An entry with that name already exists."""


# =============================================================================
# Data model
# =============================================================================


@dataclass
class Entry:
    """One credential row stored in the vault."""

    username: str
    password: str
    url: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            KEY_USERNAME: self.username,
            KEY_PASSWORD: self.password,
            KEY_URL: self.url,
            KEY_NOTES: self.notes,
            KEY_CREATED_AT: self.created_at,
            KEY_UPDATED_AT: self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entry:
        return cls(
            username=data.get(KEY_USERNAME, ""),
            password=data.get(KEY_PASSWORD, ""),
            url=data.get(KEY_URL, ""),
            notes=data.get(KEY_NOTES, ""),
            created_at=data.get(KEY_CREATED_AT, ""),
            updated_at=data.get(KEY_UPDATED_AT, ""),
        )


# =============================================================================
# UnlockedVault — the main interface
# =============================================================================


class UnlockedVault:
    """An opened, in-memory vault that holds the AES key.

    Use as a context manager so the key and plaintext are dropped
    when the block exits:

        with UnlockedVault.unlock(path, password) as v:
            entry = v.get_entry("github")

    The key is zeroed on exit (best-effort — Python doesn't guarantee
    memory wiping, but it's better than leaving it around).
    """

    def __init__(
        self,
        path: Path,
        key: bytes,
        kdf_params: KdfParameters,
        entries: dict[str, Entry],
    ) -> None:
        self._path = path
        self._key = key
        self._kdf_params = kdf_params
        self._entries = entries
        self._dirty = False

    def __enter__(self) -> UnlockedVault:
        return self

    def __exit__(self, *exc: object) -> None:
        self._key = b"\x00" * len(self._key)

    # -------------------------------------------------------------------------
    # Class methods — create and open vaults
    # -------------------------------------------------------------------------

    @classmethod
    def create(cls, path: Path, master_password: str) -> UnlockedVault:
        """Create a new empty vault at `path`.

        Raises VaultAlreadyExistsError if the file already exists.
        """
        if path.exists():
            raise VaultAlreadyExistsError(
                f"Vault already exists at {path}"
            )

        salt = generate_salt()
        params = KdfParameters(salt=salt)
        key = derive_key(master_password, params)
        entries: dict[str, Entry] = {}

        vault = cls(path=path, key=key, kdf_params=params, entries=entries)
        vault._save_to_disk()
        return vault

    @classmethod
    def unlock(cls, path: Path, master_password: str) -> UnlockedVault:
        """Open an existing vault.

        Raises VaultNotFoundError if the file doesn't exist.
        Raises WrongPasswordError if the password is wrong or the
        file is corrupted.
        Raises VaultFormatError if the file structure is invalid.
        """
        if not path.exists():
            raise VaultNotFoundError(f"No vault at {path}")

        envelope = cls._read_envelope(path)
        params = cls._parse_kdf(envelope)
        key = derive_key(master_password, params)

        cipher_block = envelope.get(KEY_CIPHER, {})
        ciphertext_b64 = cipher_block.get(KEY_CIPHERTEXT, "")
        if not ciphertext_b64:
            raise VaultFormatError("Missing ciphertext in vault file.")

        ciphertext = base64.b64decode(ciphertext_b64)
        plaintext = decrypt(ciphertext, key)
        entries_dict = json.loads(plaintext.decode("utf-8"))

        entries = {
            name: Entry.from_dict(data)
            for name, data in entries_dict.items()
        }

        return cls(path=path, key=key, kdf_params=params, entries=entries)

    # -------------------------------------------------------------------------
    # Entry operations
    # -------------------------------------------------------------------------

    def add_entry(self, name: str, entry: Entry) -> None:
        """Add a new entry. Raises EntryAlreadyExistsError if name taken."""
        if name in self._entries:
            raise EntryAlreadyExistsError(
                f"Entry '{name}' already exists."
            )
        now = datetime.now(timezone.utc).isoformat()
        entry.created_at = now
        entry.updated_at = now
        self._entries[name] = entry
        self._dirty = True

    def get_entry(self, name: str) -> Entry:
        """Get an entry by name. Raises EntryNotFoundError."""
        if name not in self._entries:
            raise EntryNotFoundError(f"No entry named '{name}'.")
        return self._entries[name]

    def delete_entry(self, name: str) -> None:
        """Delete an entry by name. Raises EntryNotFoundError."""
        if name not in self._entries:
            raise EntryNotFoundError(f"No entry named '{name}'.")
        del self._entries[name]
        self._dirty = True

    def list_entries(self) -> list[str]:
        """Return sorted list of entry names."""
        return sorted(self._entries.keys())

    @property
    def is_empty(self) -> bool:
        return len(self._entries) == 0

    # -------------------------------------------------------------------------
    # Save / persist
    # -------------------------------------------------------------------------

    def save(self) -> None:
        """Encrypt and write the vault to disk (atomic + durable)."""
        self._save_to_disk()
        self._dirty = False

    def change_password(self, new_password: str) -> None:
        """Re-encrypt the vault under a new password with a fresh salt."""
        new_salt = generate_salt()
        new_params = KdfParameters(
            salt=new_salt,
            time_cost=self._kdf_params.time_cost,
            memory_cost=self._kdf_params.memory_cost,
            parallelism=self._kdf_params.parallelism,
        )
        new_key = derive_key(new_password, new_params)

        self._kdf_params = new_params
        self._key = new_key
        self._dirty = True
        self._save_to_disk()

    # -------------------------------------------------------------------------
    # Internal — serialization and I/O
    # -------------------------------------------------------------------------

    def _build_envelope(self) -> dict[str, Any]:
        """Encrypt entries and build the outer JSON envelope."""
        entries_dict = {
            name: entry.to_dict()
            for name, entry in self._entries.items()
        }
        plaintext = json.dumps(entries_dict, indent=2).encode("utf-8")
        ciphertext = encrypt(plaintext, self._key)

        return {
            KEY_VERSION: VAULT_VERSION,
            KEY_KDF: {
                KEY_KDF_NAME: KDF_NAME_ARGON2ID,
                KEY_KDF_SALT: base64.b64encode(
                    self._kdf_params.salt
                ).decode("ascii"),
                KEY_KDF_TIME_COST: self._kdf_params.time_cost,
                KEY_KDF_MEMORY_COST: self._kdf_params.memory_cost,
                KEY_KDF_PARALLELISM: self._kdf_params.parallelism,
            },
            KEY_CIPHER: {
                KEY_CIPHER_NAME: CIPHER_NAME_AES256GCM,
                KEY_CIPHERTEXT: base64.b64encode(ciphertext).decode("ascii"),
            },
        }

    def _save_to_disk(self) -> None:
        """Atomic + durable write with advisory file locking.

        Pattern:
          1. Acquire exclusive lock on sidecar .lock file
          2. Open tmp file with mode 0600 (never world-readable)
          3. Write encrypted JSON
          4. fsync the file (flush kernel page cache to disk)
          5. os.replace(tmp, vault) — atomic rename
          6. fsync the parent directory
          7. Release lock
        """
        envelope = self._build_envelope()
        data = json.dumps(envelope, indent=2).encode("utf-8")

        vault_dir = self._path.parent
        vault_dir.mkdir(parents=True, exist_ok=True)

        lock_path = self._path.with_suffix(".lock")
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, VAULT_FILE_MODE)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)

            # Write to temp file with restricted permissions
            fd, tmp_path = tempfile.mkstemp(
                dir=str(vault_dir),
                prefix=".vault-",
                suffix=".tmp",
            )
            try:
                os.fchmod(fd, VAULT_FILE_MODE)
                os.write(fd, data)
                os.fsync(fd)
                os.close(fd)

                # Atomic rename
                os.replace(tmp_path, str(self._path))

                # Fsync parent directory to persist the rename
                dir_fd = os.open(str(vault_dir), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except BaseException:
                # Clean up temp file on any failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    @staticmethod
    def _read_envelope(path: Path) -> dict[str, Any]:
        """Read and parse the outer JSON envelope from disk."""
        try:
            raw = path.read_bytes()
        except OSError as e:
            raise VaultNotFoundError(f"Cannot read vault: {e}")

        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as e:
            raise VaultFormatError(f"Vault is not valid JSON: {e}")

        if not isinstance(envelope, dict):
            raise VaultFormatError("Vault root must be a JSON object.")

        version = envelope.get(KEY_VERSION)
        if version != VAULT_VERSION:
            raise VaultFormatError(
                f"Unsupported vault version: {version}. "
                f"Expected {VAULT_VERSION}."
            )

        return envelope

    @staticmethod
    def _parse_kdf(envelope: dict[str, Any]) -> KdfParameters:
        """Extract and validate KDF parameters from the envelope."""
        kdf_block = envelope.get(KEY_KDF)
        if not isinstance(kdf_block, dict):
            raise VaultFormatError("Missing or invalid 'kdf' block.")

        name = kdf_block.get(KEY_KDF_NAME)
        if name != KDF_NAME_ARGON2ID:
            raise VaultFormatError(f"Unsupported KDF: {name}")

        salt_b64 = kdf_block.get(KEY_KDF_SALT)
        if not salt_b64:
            raise VaultFormatError("Missing KDF salt.")

        try:
            salt = base64.b64decode(salt_b64)
        except Exception as e:
            raise VaultFormatError(f"Invalid base64 salt: {e}")

        params = KdfParameters(
            salt=salt,
            time_cost=kdf_block.get(KEY_KDF_TIME_COST, 3),
            memory_cost=kdf_block.get(KEY_KDF_MEMORY_COST, 65536),
            parallelism=kdf_block.get(KEY_KDF_PARALLELISM, 4),
        )

        try:
            params.validate()
        except ValueError as e:
            raise VaultFormatError(f"Invalid KDF parameters: {e}")

        return params
