"""
clipboard.py

Cross-platform clipboard integration.

Copies text to the system clipboard without displaying it on screen.
Supports Linux (xclip/xsel/wl-copy), macOS (pbcopy), and Windows (clip).

The clipboard is automatically cleared after a configurable timeout
(default: 30 seconds) to prevent passwords from lingering.
"""

import platform
import shutil
import subprocess
import threading


class ClipboardError(Exception):
    """Raised when clipboard operations fail."""


def _get_copy_command() -> list[str] | None:
    """Detect the available clipboard command for this platform."""
    system = platform.system()

    if system == "Darwin":
        return ["pbcopy"]

    if system == "Windows":
        return ["clip"]

    # Linux — try tools in order of preference
    # Wayland
    if shutil.which("wl-copy"):
        return ["wl-copy"]

    # X11
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard"]

    if shutil.which("xsel"):
        return ["xsel", "--clipboard", "--input"]

    return None


def copy_to_clipboard(text: str, clear_after: int = 30) -> None:
    """Copy text to the system clipboard.

    Parameters
    ----------
    text : str
        The text to copy.
    clear_after : int
        Seconds before the clipboard is automatically cleared.
        Set to 0 to disable auto-clear. Default: 30 seconds.

    Raises
    ------
    ClipboardError
        If no clipboard tool is available or the copy fails.
    """
    cmd = _get_copy_command()
    if cmd is None:
        raise ClipboardError(
            "No clipboard tool found. Install xclip, xsel, or wl-copy.\n"
            "  Debian/Ubuntu: sudo apt install xclip\n"
            "  Arch: sudo pacman -S xclip\n"
            "  Fedora: sudo dnf install xclip"
        )

    try:
        proc = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=5,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise ClipboardError(f"Clipboard command failed: {stderr}")
    except FileNotFoundError:
        raise ClipboardError(
            f"Clipboard tool '{cmd[0]}' not found. Install it first."
        )
    except subprocess.TimeoutExpired:
        raise ClipboardError("Clipboard command timed out.")

    # Auto-clear after timeout
    if clear_after > 0:
        timer = threading.Timer(clear_after, _clear_clipboard)
        timer.daemon = True
        timer.start()


def _clear_clipboard() -> None:
    """Best-effort clipboard clear after timeout."""
    try:
        cmd = _get_copy_command()
        if cmd:
            subprocess.run(
                cmd,
                input=b"",
                capture_output=True,
                timeout=5,
            )
    except Exception:
        pass  # Best-effort — don't crash on clear failure
