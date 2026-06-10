set export
set shell := ["bash", "-uc"]
set positional-arguments

default:
    @just --list --unsorted

[group('setup')]
setup:
    @echo "Creating virtual environment..."
    uv venv --allow-existing
    @echo ""
    @echo "Installing dependencies (including dev tools)..."
    uv sync --all-extras
    @echo ""
    @echo "✓ Setup complete! Try: just run -- --help"

[group('setup')]
install:
    uv sync

[group('setup')]
install-dev:
    uv sync --all-extras

[group('test')]
test:
    @echo "Running tests..."
    uv run pytest -v

[group('test')]
test-cov:
    @echo "Running tests with coverage..."
    uv run pytest -v --cov=password_vault --cov-report=term-missing

[group('test')]
lint:
    @echo "=== Ruff ==="
    uv run ruff check src tests
    @echo ""
    @echo "=== Mypy ==="
    uv run mypy src/password_vault
    @echo ""
    @echo "✓ All linters passed"

[group('test')]
format:
    uv run yapf -i -r src tests
    @echo "✓ Code formatted"

[group('test')]
fix:
    uv run ruff check src tests --fix

[group('run')]
[no-exit-message]
run *args:
    #!/usr/bin/env bash
    if [ $# -eq 0 ]; then
        cat <<'EOF'
    Usage: just run -- <command> [args]

    Commands:
      init              Create a new vault
      add <name>        Add an entry
      get <name>        Show an entry
      list              List all entries
      delete <name>     Remove an entry
      change-password   Rotate master password
      gen [length]      Generate a random password
    EOF
        exit 0
    fi
    uv run vault "$@"
