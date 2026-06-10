"""Tests for vault operations — create, unlock, CRUD, atomic writes."""

import json
import stat
from pathlib import Path

import pytest

from password_vault.crypto import WrongPasswordError, generate_salt
from password_vault.vault import (
    Entry,
    EntryAlreadyExistsError,
    EntryNotFoundError,
    UnlockedVault,
    VaultAlreadyExistsError,
    VaultFormatError,
    VaultNotFoundError,
)


# Use fast KDF params for tests (1 pass, 8 KiB, 1 lane)
FAST_PARAMS = dict(time_cost=1, memory_cost=8, parallelism=1)
MASTER_PW = "test-password-1234"


def _create_vault(path: Path, pw: str = MASTER_PW) -> UnlockedVault:
    """Helper to create a vault with fast KDF params for testing."""
    import password_vault.vault as vault_mod
    from password_vault.crypto import KdfParameters

    # Monkey-patch for fast tests
    original = KdfParameters.__init__
    salt = generate_salt()

    vault = UnlockedVault.create(path, pw)
    return vault


class TestCreateVault:
    def test_create_new_vault(self, tmp_vault_path):
        vault = UnlockedVault.create(tmp_vault_path, MASTER_PW)
        assert tmp_vault_path.exists()
        assert vault.is_empty

    def test_create_existing_raises(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)
        with pytest.raises(VaultAlreadyExistsError):
            UnlockedVault.create(tmp_vault_path, MASTER_PW)

    def test_vault_file_is_json(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)
        data = json.loads(tmp_vault_path.read_text())
        assert "version" in data
        assert "kdf" in data
        assert "cipher" in data

    def test_vault_file_permissions(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)
        mode = stat.S_IMODE(tmp_vault_path.stat().st_mode)
        assert mode == 0o600


class TestUnlockVault:
    def test_unlock_with_correct_password(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)
        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            assert v.is_empty

    def test_unlock_wrong_password(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)
        with pytest.raises(WrongPasswordError):
            UnlockedVault.unlock(tmp_vault_path, "wrong-password")

    def test_unlock_nonexistent_raises(self, tmp_vault_path):
        with pytest.raises(VaultNotFoundError):
            UnlockedVault.unlock(tmp_vault_path, MASTER_PW)

    def test_unlock_corrupted_file(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)
        tmp_vault_path.write_bytes(b"not valid json")
        with pytest.raises(VaultFormatError):
            UnlockedVault.unlock(tmp_vault_path, MASTER_PW)


class TestEntryOperations:
    def _vault_with_entry(self, tmp_vault_path) -> UnlockedVault:
        """Create a vault with one entry."""
        UnlockedVault.create(tmp_vault_path, MASTER_PW)
        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            entry = Entry(username="alice", password="s3cret", url="https://example.com")
            v.add_entry("test", entry)
            v.save()
        return UnlockedVault.unlock(tmp_vault_path, MASTER_PW)

    def test_add_entry(self, tmp_vault_path):
        with self._vault_with_entry(tmp_vault_path) as v:
            assert not v.is_empty
            entry = v.get_entry("test")
            assert entry.username == "alice"
            assert entry.password == "s3cret"

    def test_add_duplicate_raises(self, tmp_vault_path):
        with self._vault_with_entry(tmp_vault_path) as v:
            with pytest.raises(EntryAlreadyExistsError):
                v.add_entry("test", Entry(username="bob", password="pw"))

    def test_get_nonexistent_raises(self, tmp_vault_path):
        with self._vault_with_entry(tmp_vault_path) as v:
            with pytest.raises(EntryNotFoundError):
                v.get_entry("does-not-exist")

    def test_list_entries(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)
        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            v.add_entry("alpha", Entry(username="a", password="p1"))
            v.add_entry("beta", Entry(username="b", password="p2"))
            v.add_entry("gamma", Entry(username="c", password="p3"))
            v.save()

        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            names = v.list_entries()
            assert names == ["alpha", "beta", "gamma"]

    def test_delete_entry(self, tmp_vault_path):
        with self._vault_with_entry(tmp_vault_path) as v:
            v.delete_entry("test")
            v.save()
            assert v.is_empty

    def test_delete_nonexistent_raises(self, tmp_vault_path):
        with self._vault_with_entry(tmp_vault_path) as v:
            with pytest.raises(EntryNotFoundError):
                v.delete_entry("nope")


class TestPersistence:
    """Test that entries survive close/reopen cycles."""

    def test_roundtrip(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)

        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            v.add_entry("github", Entry(username="alice", password="gh_pw"))
            v.add_entry("gitlab", Entry(username="bob", password="gl_pw"))
            v.save()

        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            assert v.list_entries() == ["github", "gitlab"]
            gh = v.get_entry("github")
            assert gh.username == "alice"
            assert gh.password == "gh_pw"

    def test_modify_and_reopen(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)

        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            v.add_entry("test", Entry(username="u", password="p"))
            v.save()

        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            v.delete_entry("test")
            v.save()

        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            assert v.is_empty


class TestChangePassword:
    def test_change_password_works(self, tmp_vault_path):
        UnlockedVault.create(tmp_vault_path, MASTER_PW)

        with UnlockedVault.unlock(tmp_vault_path, MASTER_PW) as v:
            v.add_entry("test", Entry(username="u", password="p"))
            v.change_password("new-master-password-5678")
            v.save()

        # Old password should fail
        with pytest.raises(WrongPasswordError):
            UnlockedVault.unlock(tmp_vault_path, MASTER_PW)

        # New password should work
        with UnlockedVault.unlock(tmp_vault_path, "new-master-password-5678") as v:
            assert v.get_entry("test").username == "u"
