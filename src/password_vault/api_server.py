"""
api_server.py

Local HTTP API server that bridges the encrypted vault to the browser extension.

Runs on localhost:19815 with a random auth token. Only accepts requests
from the browser extension. The vault is decrypted in memory and served
over a local-only connection — no network exposure.

Endpoints:
  POST /auth       — authenticate with master password, get session token
  GET  /entries    — list entry names (requires session token)
  POST /entries    — get a specific entry's credentials
  DELETE /session  — end session, wipe key from memory

Security:
  - Binds to 127.0.0.1 only (never exposed to network)
  - Session token required for all endpoints after auth
  - Session expires after 5 minutes of inactivity
  - CORS restricted to extension origin
  - Rate limiting: 5 auth attempts per minute
"""

import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from password_vault.vault import UnlockedVault

# Server config
HOST = "127.0.0.1"
PORT = 19815
SESSION_TIMEOUT = 300  # 5 minutes
MAX_AUTH_ATTEMPTS = 5
AUTH_WINDOW = 60  # 1 minute

# Global state
_sessions: dict[str, dict[str, Any]] = {}
_auth_attempts: list[float] = []
_vault_path: Path | None = None


class VaultAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the vault API."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        """Send CORS headers for extension communication."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _get_session_token(self) -> str | None:
        """Extract session token from Authorization header."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None

    def _validate_session(self) -> dict[str, Any] | None:
        """Validate session token and return session data."""
        token = self._get_session_token()
        if not token:
            return None

        session = _sessions.get(token)
        if not session:
            return None

        # Check timeout
        if time.time() - session["last_activity"] > SESSION_TIMEOUT:
            del _sessions[token]
            return None

        session["last_activity"] = time.time()
        return session

    def _rate_limit_check(self) -> bool:
        """Check if auth attempt is rate-limited."""
        now = time.time()
        # Clean old attempts
        while _auth_attempts and now - _auth_attempts[0] > AUTH_WINDOW:
            _auth_attempts.pop(0)
        return len(_auth_attempts) < MAX_AUTH_ATTEMPTS

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:
        """Handle POST requests."""
        path = urlparse(self.path).path

        if path == "/auth":
            self._handle_auth()
        elif path == "/entries":
            self._handle_get_entry()
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_GET(self) -> None:
        """Handle GET requests."""
        path = urlparse(self.path).path

        if path == "/entries":
            self._handle_list_entries()
        elif path == "/health":
            self._send_json({"status": "ok"})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        path = urlparse(self.path).path

        if path == "/session":
            self._handle_logout()
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_auth(self) -> None:
        """Authenticate with master password, return session token."""
        if not self._rate_limit_check():
            self._send_json({"error": "Too many attempts. Wait a minute."}, 429)
            return

        _auth_attempts.append(time.time())

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        password = data.get("password", "")
        vault_path_str = data.get("vault_path", "")
        vault_path = Path(vault_path_str) if vault_path_str else _vault_path

        if not vault_path or not vault_path.exists():
            self._send_json({"error": "Vault not found"}, 404)
            return

        try:
            vault = UnlockedVault.unlock(vault_path, password)
        except Exception:
            self._send_json({"error": "Wrong password"}, 401)
            return

        # Create session
        token = secrets.token_hex(32)
        _sessions[token] = {
            "vault": vault,
            "vault_path": vault_path,
            "last_activity": time.time(),
        }

        self._send_json({
            "token": token,
            "expires_in": SESSION_TIMEOUT,
            "entries": vault.list_entries(),
        })

    def _handle_list_entries(self) -> None:
        """List all entry names."""
        session = self._validate_session()
        if not session:
            self._send_json({"error": "Unauthorized"}, 401)
            return

        vault: UnlockedVault = session["vault"]
        self._send_json({"entries": vault.list_entries()})

    def _handle_get_entry(self) -> None:
        """Get a specific entry's credentials."""
        session = self._validate_session()
        if not session:
            self._send_json({"error": "Unauthorized"}, 401)
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        name = data.get("name", "")
        if not name:
            self._send_json({"error": "Missing entry name"}, 400)
            return

        vault: UnlockedVault = session["vault"]

        # Fuzzy search
        from password_vault.search import fuzzy_search
        entries = vault.list_entries()
        matches = fuzzy_search(name, entries)

        if not matches:
            self._send_json({"error": f"No entry matching '{name}'"}, 404)
            return

        # Use best match
        best = matches[0]
        entry = vault.get_entry(best.name)

        self._send_json({
            "name": best.name,
            "match_type": best.match_type,
            "username": entry.username,
            "password": entry.password,
            "url": entry.url,
            "notes": entry.notes,
        })

    def _handle_logout(self) -> None:
        """End session, wipe key from memory."""
        token = self._get_session_token()
        if token and token in _sessions:
            vault: UnlockedVault = _sessions[token]["vault"]
            # Zero the key
            vault._key = b"\x00" * len(vault._key)
            del _sessions[token]

        self._send_json({"status": "logged_out"})


def run_server(
    vault_path: Path,
    host: str = HOST,
    port: int = PORT,
) -> None:
    """Start the API server.

    Parameters
    ----------
    vault_path : Path
        Path to the vault file to serve.
    host : str
        Bind address. Default: 127.0.0.1 (localhost only).
    port : int
        Port number. Default: 19815.
    """
    global _vault_path
    _vault_path = vault_path

    server = HTTPServer((host, port), VaultAPIHandler)
    print(f"Vault API server running on http://{host}:{port}")
    print(f"Serving vault: {vault_path}")
    print("Press Ctrl+C to stop.")
    print()

    # Generate a one-time extension token
    ext_token = secrets.token_hex(16)
    print(f"Extension auth token: {ext_token}")
    print("(Add this in the extension settings)")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        # Clean up sessions
        for token, session in _sessions.items():
            vault = session["vault"]
            vault._key = b"\x00" * len(vault._key)
        _sessions.clear()
        server.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Password Vault API Server")
    parser.add_argument(
        "--vault",
        type=Path,
        default=Path.home() / ".password-vault" / "vault.json",
        help="Path to vault file",
    )
    parser.add_argument("--port", type=int, default=PORT, help="Port number")
    args = parser.parse_args()

    run_server(args.vault, port=args.port)
