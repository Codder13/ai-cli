#!/usr/bin/env bash
set -e

# Target binary path
INSTALL_DIR="${HOME}/.local/bin"
TARGET="${INSTALL_DIR}/ai"

echo "⚡ Installing ai-cli to ${TARGET}..."

mkdir -p "${INSTALL_DIR}"

# 1. Check Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required to run ai-cli." >&2
    exit 1
fi

# 2. Download executable
if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://raw.githubusercontent.com/Codder13/ai-cli/main/src/ai_cli/main.py -o "${TARGET}"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "${TARGET}" https://raw.githubusercontent.com/Codder13/ai-cli/main/src/ai_cli/main.py
else
    echo "Error: curl or wget is required." >&2
    exit 1
fi

chmod +x "${TARGET}"

# 3. Check for rich dependency
if ! python3 -c 'import rich' >/dev/null 2>&1; then
    echo "📦 Installing 'rich' for terminal markdown rendering..."
    if command -v pip3 >/dev/null 2>&1; then
        pip3 install --user -q rich || pip3 install -q rich || true
    elif command -v pip >/dev/null 2>&1; then
        pip install --user -q rich || pip install -q rich || true
    fi
fi

echo "✅ Successfully installed ai-cli to ${TARGET}!"
echo ""
echo "Try running:"
echo "  ai what is the biggest thing on the moon"
echo "  git diff | ai summarize changes"
