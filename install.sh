#!/usr/bin/env bash
set -e

# Target binary path
INSTALL_DIR="${HOME}/.local/bin"
TARGET="${INSTALL_DIR}/ai"

echo "⚡ Installing ai-cli to ${TARGET}..."

mkdir -p "${INSTALL_DIR}"

if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://raw.githubusercontent.com/Codder13/ai-cli/main/src/ai_cli/main.py -o "${TARGET}"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "${TARGET}" https://raw.githubusercontent.com/Codder13/ai-cli/main/src/ai_cli/main.py
else
    echo "Error: curl or wget is required." >&2
    exit 1
fi

chmod +x "${TARGET}"

echo "✅ Successfully installed ai-cli!"
echo ""
echo "Try running:"
echo "  ai what is the biggest thing on the moon"
echo "  git diff | ai summarize changes"
