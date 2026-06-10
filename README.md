# Password Vault

Encrypted command-line password manager built in Python.

One master password protects every credential you store. Uses **Argon2id** for key derivation and **AES-256-GCM** for authenticated encryption.

## Features

- **Argon2id key derivation** — OWASP-recommended, memory-hard to defeat GPU brute-force attacks
- **AES-256-GCM authenticated encryption** — confidentiality + tamper detection in one primitive
- **Atomic durable writes** — tmp file → fsync → atomic rename → directory fsync. Never corrupt, even on power loss
- **Advisory file locking** — concurrent `pv` invocations are serialized via `fcntl`
- **Secure password generator** — `secrets` module with Fisher-Yates shuffle, never `random`
- **Master password rotation** — re-encrypts the entire vault under a fresh salt and key
- **KDF parameters stored in file** — old vaults stay readable when defaults change
- **Clipboard integration** — `pv get github --copy` copies password to clipboard (auto-clears in 30s)
- **Fuzzy search** — `pv search git` finds "github", "gitlab"; supports prefix, substring, and subsequence matching
- **Browser extension** — Chrome/Firefox extension with autofill support via local API server
- **QR code export** — `pv qr` generates a QR code of your encrypted vault for mobile transfer
- **Pipe-friendly output** — `pv gen 32 | xclip -selection clipboard`

## Quick Start

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/password-vault.git
cd password-vault
chmod +x install.sh
./install.sh

# Create a vault
pv init

# Add credentials
pv add github
pv add gitlab -g   # auto-generate password

# Retrieve
pv get github

# Copy password to clipboard (auto-clears in 30s)
pv get github --copy

# Fuzzy search
pv search git      # finds github, gitlab
pv search hub      # finds github (substring)

# List all entries
pv list

# Generate a standalone password
pv gen 32

# Rotate master password
pv change-password
```

## Commands

| Command | Description |
|---------|-------------|
| `pv init` | Create a new vault (prompts for master password) |
| `pv add <name>` | Add a credential entry (`-g` to auto-generate password) |
| `pv get <name>` | Show all fields for an entry |
| `pv get <name> --copy` | Copy password to clipboard (auto-clears in 30s) |
| `pv get <name> --copy-user` | Copy username to clipboard |
| `pv search <query>` | Fuzzy search entries by name |
| `pv list` | List all entry names (no passwords shown) |
| `pv delete <name>` | Remove an entry |
| `pv change-password` | Rotate master password, re-encrypt vault |
| `pv gen [length]` | Generate a random password (no vault needed) |
| `pv qr` | Export encrypted vault as QR code for mobile |
| `pv serve` | Start local API server for browser extension |

Every command accepts `--vault PATH` to use a custom vault location.

## Clipboard Integration

Copy passwords directly to clipboard without displaying them:

```bash
# Copy password (auto-clears after 30 seconds)
pv get github --copy

# Copy username
pv get github --copy-user

# Generate and copy
pv gen 32 | xclip -selection clipboard
```

Supports: xclip, xsel, wl-copy (Wayland), pbcopy (macOS), clip (Windows).

## Fuzzy Search

Find entries without typing the exact name:

```bash
pv search git       # Prefix: matches github, gitlab
pv search hub       # Substring: matches github
pv search ghb       # Fuzzy: matches github (subsequence)
```

The `get` and `delete` commands also use fuzzy matching — `pv get git` will find "github".

## Browser Extension

Autofill credentials on any website:

```bash
# 1. Start the local API server
pv serve

# 2. Load the extension in Chrome:
#    - Go to chrome://extensions
#    - Enable "Developer mode"
#    - Click "Load unpacked"
#    - Select the browser-extension/ folder

# 3. Click the extension icon, enter your master password
# 4. Navigate to any login page, click "Autofill"
```

The server runs on `localhost:19815` only — no network exposure.

## QR Code Export

Transfer your vault to a mobile device:

```bash
# Export full vault as QR code
pv qr

# Custom output path
pv qr --output ~/vault_backup.png
```

The QR contains your encrypted vault — still protected by the master password.

## Security Design

| Threat | Mitigation |
|--------|-----------|
| Vault file stolen | Argon2id with 64 MiB / 3 passes / 4 lanes — each guess takes ~0.5s |
| Vault file tampered | AES-GCM authentication tag rejects decryption |
| Power loss mid-save | Atomic write: tmp → fsync → rename → dir fsync |
| Two processes racing | Advisory `fcntl.LOCK_EX` on sidecar `.lock` file |
| Vault temp file exposed | `os.open` with mode `0600` at the first syscall |
| Predictable passwords | `secrets` module everywhere, never `random` |
| Aging KDF parameters | Stored in file; `change-password` can upgrade transparently |
| Clipboard leaks | Auto-clears after 30 seconds |
| Browser extension attacks | Localhost-only API, session tokens, rate limiting |

## Project Structure

```
password-vault/
├── pyproject.toml
├── justfile
├── install.sh
├── browser-extension/          # Chrome/Firefox extension
│   ├── manifest.json
│   ├── popup.html/js           # Extension popup UI
│   ├── content.js/css          # Autofill on web pages
│   ├── background.js           # Service worker
│   └── icons/
├── src/
│   └── password_vault/
│       ├── __init__.py
│       ├── __main__.py
│       ├── constants.py        # All config in one place
│       ├── crypto.py           # Argon2id + AES-256-GCM
│       ├── generator.py        # Secure password generation
│       ├── vault.py            # Encrypted storage + atomic writes
│       ├── clipboard.py        # Cross-platform clipboard
│       ├── search.py           # Fuzzy entry search
│       ├── qr_export.py        # QR code generation
│       ├── api_server.py       # Local REST API for extension
│       └── main.py             # CLI (Typer)
└── tests/
    ├── conftest.py
    ├── test_crypto.py
    ├── test_generator.py
    ├── test_vault.py
    ├── test_search.py
    └── test_clipboard.py
```

## Development

```bash
just test       # Run test suite (67 tests)
just test-cov   # Tests + coverage report
just lint       # Ruff + mypy
just format     # Auto-format with yapf
```

## Tech Stack

- **Python 3.13+**
- **argon2-cffi** — Argon2id key derivation
- **cryptography** — AES-256-GCM encryption
- **typer** — CLI framework
- **rich** — terminal formatting
- **qrcode[pil]** — QR code generation (optional)
- **pytest** — testing

## License

MIT
