#!/usr/bin/env bash
# install.sh — One-shot setup for password-vault
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }

# Step 1 — Check Python 3.13+
check_python() {
    info "Checking for Python 3.13+..."
    if ! command -v python3 &>/dev/null; then
        error "python3 not found. Install Python 3.13+ first."
        exit 1
    fi
    local version
    version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local major minor
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)
    if (( major < 3 )) || { (( major == 3 )) && (( minor < 13 )); }; then
        error "Python 3.13+ required, found Python $version"
        exit 1
    fi
    success "Python $version detected"
}

# Step 2 — Install uv if missing
install_uv() {
    if command -v uv &>/dev/null; then
        success "uv already installed ($(uv --version))"
        return 0
    fi
    info "Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        error "uv install failed. Add uv to PATH and retry."
        exit 1
    fi
    success "uv installed"
}

# Step 3 — Install just if missing
install_just() {
    if command -v just &>/dev/null; then
        success "just already installed ($(just --version))"
        return 0
    fi
    info "Installing just (command runner)..."
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v just &>/dev/null; then
        error "just install failed. Add ~/.local/bin to PATH and retry."
        exit 1
    fi
    success "just installed"
}

# Step 4 — Create venv and install deps
setup_project() {
    info "Setting up project..."
    just setup
    success "Project setup complete"
}

# Run everything
check_python
install_uv
install_just
setup_project

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  password-vault is ready!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Try it out:"
echo "    just run -- init          Create a vault"
echo "    just run -- add github    Add an entry"
echo "    just run -- get github    Retrieve it"
echo "    just run -- gen 32        Generate a password"
echo ""
echo "  Run tests:"
echo "    just test"
echo ""
