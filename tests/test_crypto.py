"""Tests for the cryptographic primitives."""

import pytest

from password_vault.crypto import (
    KdfParameters,
    WrongPasswordError,
    decrypt,
    derive_key,
    encrypt,
    generate_nonce,
    generate_salt,
)


class TestSalt:
    def test_salt_length(self):
        salt = generate_salt()
        assert len(salt) == 16

    def test_salts_are_unique(self):
        salts = {generate_salt() for _ in range(100)}
        assert len(salts) == 100


class TestNonce:
    def test_nonce_length(self):
        nonce = generate_nonce()
        assert len(nonce) == 12

    def test_nonces_are_unique(self):
        nonces = {generate_nonce() for _ in range(100)}
        assert len(nonces) == 100


class TestKeyDerivation:
    def test_derive_key_length(self, master_password, kdf_params):
        key = derive_key(master_password, kdf_params)
        assert len(key) == 32

    def test_derive_key_deterministic(self, master_password, kdf_params):
        key1 = derive_key(master_password, kdf_params)
        key2 = derive_key(master_password, kdf_params)
        assert key1 == key2

    def test_different_passwords_different_keys(self, kdf_params):
        key1 = derive_key("password-one", kdf_params)
        key2 = derive_key("password-two", kdf_params)
        assert key1 != key2

    def test_different_salts_different_keys(self, master_password):
        params1 = KdfParameters(salt=generate_salt())
        params2 = KdfParameters(salt=generate_salt())
        key1 = derive_key(master_password, params1)
        key2 = derive_key(master_password, params2)
        assert key1 != key2

    def test_invalid_time_cost_raises(self):
        params = KdfParameters(salt=generate_salt(), time_cost=0)
        with pytest.raises(ValueError, match="time_cost"):
            derive_key("password", params)

    def test_invalid_parallelism_raises(self):
        params = KdfParameters(salt=generate_salt(), parallelism=0)
        with pytest.raises(ValueError, match="parallelism"):
            derive_key("password", params)

    def test_invalid_memory_raises(self):
        params = KdfParameters(salt=generate_salt(), memory_cost=1, parallelism=4)
        with pytest.raises(ValueError, match="memory_cost"):
            derive_key("password", params)


class TestEncryptDecrypt:
    def test_roundtrip(self, derived_key):
        plaintext = b"Hello, this is a secret message!"
        ciphertext = encrypt(plaintext, derived_key)
        result = decrypt(ciphertext, derived_key)
        assert result == plaintext

    def test_ciphertext_differs_from_plaintext(self, derived_key):
        plaintext = b"secret data"
        ciphertext = encrypt(plaintext, derived_key)
        assert ciphertext != plaintext

    def test_different_encryptions_differ(self, derived_key):
        """Each encryption uses a fresh nonce, so outputs differ."""
        plaintext = b"same input"
        ct1 = encrypt(plaintext, derived_key)
        ct2 = encrypt(plaintext, derived_key)
        assert ct1 != ct2

    def test_wrong_key_raises(self, derived_key):
        plaintext = b"secret"
        ciphertext = encrypt(plaintext, derived_key)
        wrong_key = b"\x00" * 32
        with pytest.raises(WrongPasswordError):
            decrypt(ciphertext, wrong_key)

    def test_tampered_ciphertext_raises(self, derived_key):
        plaintext = b"secret"
        ciphertext = encrypt(plaintext, derived_key)
        # Flip a byte in the ciphertext portion
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF
        with pytest.raises(WrongPasswordError):
            decrypt(bytes(tampered), derived_key)

    def test_too_short_ciphertext_raises(self, derived_key):
        with pytest.raises(WrongPasswordError, match="too short"):
            decrypt(b"\x00" * 5, derived_key)
