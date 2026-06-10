"""Tests for the clipboard module."""

import pytest
from unittest.mock import patch, MagicMock
import subprocess

from password_vault.clipboard import (
    ClipboardError,
    _get_copy_command,
    copy_to_clipboard,
)


class TestGetCopyCommand:
    @patch("password_vault.clipboard.platform.system", return_value="Darwin")
    def test_darwin_uses_pbcopy(self, mock_system):
        cmd = _get_copy_command()
        assert cmd == ["pbcopy"]

    @patch("password_vault.clipboard.platform.system", return_value="Windows")
    def test_windows_uses_clip(self, mock_system):
        cmd = _get_copy_command()
        assert cmd == ["clip"]

    @patch("password_vault.clipboard.shutil.which")
    @patch("password_vault.clipboard.platform.system", return_value="Linux")
    def test_linux_prefers_wl_copy(self, mock_system, mock_which):
        mock_which.side_effect = lambda x: "/usr/bin/wl-copy" if x == "wl-copy" else None
        cmd = _get_copy_command()
        assert cmd == ["wl-copy"]

    @patch("password_vault.clipboard.shutil.which")
    @patch("password_vault.clipboard.platform.system", return_value="Linux")
    def test_linux_falls_back_to_xclip(self, mock_system, mock_which):
        mock_which.side_effect = lambda x: "/usr/bin/xclip" if x == "xclip" else None
        cmd = _get_copy_command()
        assert cmd == ["xclip", "-selection", "clipboard"]

    @patch("password_vault.clipboard.shutil.which")
    @patch("password_vault.clipboard.platform.system", return_value="Linux")
    def test_linux_no_clipboard_returns_none(self, mock_system, mock_which):
        mock_which.return_value = None
        cmd = _get_copy_command()
        assert cmd is None


class TestCopyToClipboard:
    @patch("password_vault.clipboard._get_copy_command")
    def test_no_tool_raises(self, mock_cmd):
        mock_cmd.return_value = None
        with pytest.raises(ClipboardError, match="No clipboard tool"):
            copy_to_clipboard("test")

    @patch("password_vault.clipboard.subprocess.run")
    @patch("password_vault.clipboard._get_copy_command")
    def test_successful_copy(self, mock_cmd, mock_run):
        mock_cmd.return_value = ["xclip"]
        mock_run.return_value = MagicMock(returncode=0)
        # Should not raise
        copy_to_clipboard("test password", clear_after=0)

    @patch("password_vault.clipboard.subprocess.run")
    @patch("password_vault.clipboard._get_copy_command")
    def test_failed_copy_raises(self, mock_cmd, mock_run):
        mock_cmd.return_value = ["xclip"]
        mock_run.return_value = MagicMock(returncode=1, stderr=b"error")
        with pytest.raises(ClipboardError, match="failed"):
            copy_to_clipboard("test")

    @patch("password_vault.clipboard.subprocess.run")
    @patch("password_vault.clipboard._get_copy_command")
    def test_timeout_raises(self, mock_cmd, mock_run):
        mock_cmd.return_value = ["xclip"]
        mock_run.side_effect = subprocess.TimeoutExpired("xclip", 5)
        with pytest.raises(ClipboardError, match="timed out"):
            copy_to_clipboard("test")
