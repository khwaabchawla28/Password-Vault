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

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 1 — Check Python 3.13+ (install via uv if missing)
check_python() {
    info "Checking for Python 3.13+..."

    # First check if system python3 is already 3.13+
    if command -v python3 &>/dev/null; then
        local version major minor
        version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if (( major > 3 )) || { (( major == 3 )) && (( minor >= 13 )); }; then
            success "Python $version detected"
            return 0
        fi
        warn "Found Python $version — need 3.13+"
    else
        warn "python3 not found"
    fi

    # Python 3.13+ not available — install it via uv
    info "Installing Python 3.13 via uv..."
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    # Make sure uv is available (install_uv runs after this, but we need it now)
    if ! command -v uv &>/dev/null; then
        info "Installing uv first..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        if ! command -v uv &>/dev/null; then
            error "uv install failed. Install Python 3.13+ manually and retry."
            exit 1
        fi
    fi

    uv python install 3.13
    success "Python 3.13 installed via uv"
}

# Step 2 — Install uv if missing (may already be installed by check_python)
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
    cd "$PROJECT_DIR"
    just setup
    success "Project setup complete"
}

# Step 5 — Create global 'pvt' command
install_pvt_command() {
    info "Installing 'pvt' command globally..."

    mkdir -p ~/.local/bin

    cat > ~/.local/bin/pvt << WRAPPER
#!/usr/bin/env bash
cd "$PROJECT_DIR" && source .venv/bin/activate && pvt "\$@"
WRAPPER
    chmod +x ~/.local/bin/pvt

    # Make sure ~/.local/bin is in PATH
    if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
        # Add to .bashrc if not already there
        if ! grep -q '.local/bin' ~/.bashrc 2>/dev/null; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
            info "Added ~/.local/bin to PATH in ~/.bashrc"
        fi
        export PATH="$HOME/.local/bin:$PATH"
    fi

    success "'pvt' command installed"
}

# Run everything
check_python
install_uv
install_just
setup_project
install_pvt_command

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  password-vault is ready!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Open a NEW terminal and try:"
echo "    pvt init              Create a vault"
echo "    pvt add github        Add an entry"
echo "    pvt get github        Retrieve it"
echo "    pvt gen 32            Generate a password"
echo ""
echo "  Or use 'just run' in this terminal:"
echo "    just run -- init"
echo "    just run -- add github"
echo "    just run -- get github"
echo ""
echo "  Run tests:"
echo "    just test"
echo ""
