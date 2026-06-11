# Password Vault

Encrypted command-line password manager built in Python.

One master password protects every credential you store. Uses **Argon2id** for key derivation and **AES-256-GCM** for authenticated encryption.

## Features

- **Argon2id key derivation** — OWASP-recommended, memory-hard to defeat GPU brute-force attacks
- **AES-256-GCM authenticated encryption** — confidentiality + tamper detection in one primitive
- **Atomic durable writes** — tmp file → fsync → atomic rename → directory fsync. Never corrupt, even on power loss
- **Advisory file locking** — concurrent `pvt` invocations are serialized via `fcntl`
- **Secure password generator** — `secrets` module with Fisher-Yates shuffle, never `random`
- **Master password rotation** — re-encrypts the entire vault under a fresh salt and key
- **KDF parameters stored in file** — old vaults stay readable when defaults change
- **Clipboard integration** — `pvt get github --copy` copies password to clipboard (auto-clears in 30s)
- **Fuzzy search** — `pvt search git` finds "github", "gitlab"; supports prefix, substring, and subsequence matching
- **Browser extension** — Chrome/Firefox extension with autofill support via local API server
- **QR code export** — `pvt qr` generates a QR code of your encrypted vault for mobile transfer
- **Pipe-friendly output** — `pvt gen 32 | xclip -selection clipboard`

## Quick Start

```bash
# Clone and install
git clone https://github.com/khwaabchawla1502/Password-Vault.git
cd Password-Vault
chmod +x install.sh
./install.sh

# Create a vault
pvt init

# Add credentials
pvt add github
pvt add gitlab -g   # auto-generate password

# Retrieve
pvt get github

# Copy password to clipboard (auto-clears in 30s)
pvt get github --copy

# Fuzzy search
pvt search git      # finds github, gitlab
pvt search hub      # finds github (substring)

# List all entries
pvt list

# Generate a standalone password
pvt gen 32

# Rotate master password
pvt change-password
```

## Commands

| Command | Description |
|---------|-------------|
| `pvt init` | Create a new vault (prompts for master password) |
| `pvt add <name>` | Add a credential entry (`-g` to auto-generate password) |
| `pvt get <name>` | Show all fields for an entry |
| `pvt get <name> --copy` | Copy password to clipboard (auto-clears in 30s) |
| `pvt get <name> --copy-user` | Copy username to clipboard |
| `pvt search <query>` | Fuzzy search entries by name |
| `pvt list` | List all entry names (no passwords shown) |
| `pvt delete <name>` | Remove an entry |
| `pvt change-password` | Rotate master password, re-encrypt vault |
| `pvt gen [length]` | Generate a random password (no vault needed) |
| `pvt qr` | Export encrypted vault as QR code for mobile |
| `pvt serve` | Start local API server for browser extension |

Every command accepts `--vault PATH` to use a custom vault location.

## Clipboard Integration

Copy passwords directly to clipboard without displaying them:

```bash
# Copy password (auto-clears after 30 seconds)
pvt get github --copy

# Copy username
pvt get github --copy-user

# Generate and copy
pvt gen 32 | xclip -selection clipboard
```

Supports: xclip, xsel, wl-copy (Wayland), pbcopy (macOS), clip (Windows).

## Fuzzy Search

Find entries without typing the exact name:

```bash
pvt search git       # Prefix: matches github, gitlab
pvt search hub       # Substring: matches github
pvt search ghb       # Fuzzy: matches github (subsequence)
```

The `get` and `delete` commands also use fuzzy matching — `pvt get git` will find "github".

## Browser Extension

Autofill credentials on any website:

```bash
# 1. Start the local API server
pvt serve

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
pvt qr

# Custom output path
pvt qr --output ~/vault_backup.png
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
Password-Vault/
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

- **Python 3.13+** (auto-installed by `install.sh` if missing)
- **argon2-cffi** — Argon2id key derivation
- **cryptography** — AES-256-GCM encryption
- **typer** — CLI framework
- **rich** — terminal formatting
- **qrcode[pil]** — QR code generation (optional)
- **pytest** — testing

## License

MIT
