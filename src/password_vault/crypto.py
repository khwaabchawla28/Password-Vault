"""
crypto.py

All cryptographic operations — key derivation and authenticated encryption.

Two jobs:
  1. Key Derivation (Argon2id)
     Takes a master password + random salt, runs them through a deliberately
     slow memory-hard algorithm, produces a 32-byte AES key. The slowness
     is the point — legitimate users pay it once per session, attackers pay
     it for every guess.

  2. Authenticated Encryption (AES-256-GCM)
     Encrypts data with confidentiality (nobody can read it) AND authenticity
     (nobody can tamper with it). If even one byte of the ciphertext is
     modified, decryption fails.

Security invariant:
  WrongPasswordError is raised for BOTH wrong password AND tampered file.
  We never distinguish the two — leaking which one it was helps attackers.
"""

import secrets
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from password_vault.constants import (
    ARGON2_MEMORY_KIB,
    ARGON2_MEMORY_KIB_PER_LANE_MIN,
    ARGON2_PARALLELISM,
    ARGON2_PARALLELISM_MIN,
    ARGON2_TIME_COST,
    ARGON2_TIME_COST_MIN,
    KEY_LENGTH_BYTES,
    NONCE_LENGTH_BYTES,
    SALT_LENGTH_BYTES,
)


class CryptoError(Exception):
    """Base exception for all cryptographic errors."""


class WrongPasswordError(CryptoError):
    """Raised when decryption fails — wrong password OR tampered file."""


@dataclass(frozen=True)
class KdfParameters:
    """Stored KDF parameters — read from the vault file on disk.

    Frozen (immutable) so nobody can accidentally mutate them mid-derivation.
    Storing parameters in the file means:
      - Old vaults stay readable when defaults change
      - Rotation can upgrade parameters transparently
    """

    salt: bytes
    time_cost: int = ARGON2_TIME_COST
    memory_cost: int = ARGON2_MEMORY_KIB
    parallelism: int = ARGON2_PARALLELISM

    def validate(self) -> None:
        """Check parameters are within Argon2's algorithmic floors.

        A corrupted or hand-edited vault file could contain nonsensical
        values that would crash the Argon2 library. Better to catch it
        here with a clean VaultFormatError.
        """
        if self.time_cost < ARGON2_TIME_COST_MIN:
            raise ValueError(
                f"time_cost must be >= {ARGON2_TIME_COST_MIN}, "
                f"got {self.time_cost}"
            )
        if self.parallelism < ARGON2_PARALLELISM_MIN:
            raise ValueError(
                f"parallelism must be >= {ARGON2_PARALLELISM_MIN}, "
                f"got {self.parallelism}"
            )
        min_memory = ARGON2_MEMORY_KIB_PER_LANE_MIN * self.parallelism
        if self.memory_cost < min_memory:
            raise ValueError(
                f"memory_cost must be >= {min_memory} "
                f"(8 KiB * {self.parallelism} lanes), "
                f"got {self.memory_cost}"
            )


def generate_salt() -> bytes:
    """Return a cryptographically random salt."""
    return secrets.token_bytes(SALT_LENGTH_BYTES)


def generate_nonce() -> bytes:
    """Return a cryptographically random nonce for AES-GCM."""
    return secrets.token_bytes(NONCE_LENGTH_BYTES)


def derive_key(password: str, params: KdfParameters) -> bytes:
    """Derive a 32-byte AES key from a master password using Argon2id.

    Argon2id is the winner of the 2015 Password Hashing Competition and
    OWASP's recommended KDF. It is memory-hard (defeats GPUs/ASICs) and
    has a hybrid data-access pattern (defeats side-channel attacks).

    Parameters
    ----------
    password : str
        The master password typed by the user.
    params : KdfParameters
        Salt and tuning knobs loaded from the vault file.

    Returns
    -------
    bytes
        Exactly 32 bytes suitable for use as an AES-256 key.
    """
    params.validate()
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=params.salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_cost,
        parallelism=params.parallelism,
        hash_len=KEY_LENGTH_BYTES,
        type=Type.ID,
    )


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt plaintext with AES-256-GCM.

    A fresh random nonce is generated for every encryption and prepended
    to the ciphertext. The nonce is not secret — it just must never be
    reused with the same key.

    Returns
    -------
    bytes
        nonce (12 bytes) || ciphertext || GCM tag (16 bytes)
    """
    nonce = generate_nonce()
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt(data: bytes, key: bytes) -> bytes:
    """Decrypt data produced by encrypt().

    Raises
    ------
    WrongPasswordError
        If the key is wrong OR the ciphertext was tampered with.
        We intentionally do not distinguish the two cases.
    """
    if len(data) < NONCE_LENGTH_BYTES:
        raise WrongPasswordError("Ciphertext too short — corrupted vault.")

    nonce = data[:NONCE_LENGTH_BYTES]
    ciphertext = data[NONCE_LENGTH_BYTES:]

    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise WrongPasswordError(
            "Decryption failed — wrong password or tampered file."
        )
