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
- **Pipe-friendly output** — `pv gen 32 | xclip -selection clipboard`

## Quick Start

```bash
# Install
./install.sh

# Or manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Create a vault
pv init

# Add credentials
pv add github
pv add gitlab -g   # auto-generate password

# Retrieve
pv get github

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
| `pv list` | List all entry names (no passwords shown) |
| `pv delete <name>` | Remove an entry |
| `pv change-password` | Rotate master password, re-encrypt vault |
| `pv gen [length]` | Generate a random password (no vault needed) |

Every command accepts `--vault PATH` to use a custom vault location.

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

## Project Structure

```
password-vault/
├── pyproject.toml
├── justfile
├── install.sh
├── src/
│   └── password_vault/
│       ├── __init__.py
│       ├── __main__.py
│       ├── constants.py      # All config in one place
│       ├── crypto.py         # Argon2id + AES-256-GCM
│       ├── generator.py      # Secure password generation
│       ├── vault.py          # Encrypted storage + atomic writes
│       └── main.py           # CLI (Typer)
└── tests/
    ├── conftest.py
    ├── test_crypto.py
    ├── test_generator.py
    └── test_vault.py
```

## Development

```bash
just test       # Run test suite
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
- **pytest** — testing

## License

MIT
