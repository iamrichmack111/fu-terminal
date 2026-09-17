#!/usr/bin/env bash
set -euo pipefail
APP_NAME="fu-terminal"
INSTALL_DIR="${FU_INSTALL_DIR:-$HOME/.local/share/$APP_NAME}"
BIN_DIR="${FU_BIN_DIR:-$HOME/.local/bin}"
WORKSPACE="${FU_WORKSPACE:-$HOME/Desktop/FU-Workspace}"
MODEL="${FU_MODEL:-qwen2.5-coder:3b}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "◆ FU TERMINAL INSTALLER"
printf '  Install: %s\n  Workspace: %s\n  Model: %s\n' "$INSTALL_DIR" "$WORKSPACE" "$MODEL"
mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$WORKSPACE"/{projects,generated,backups,logs,sessions}
rsync -a --delete --exclude '.git' --exclude '.venv' --exclude 'node_modules' "$ROOT/" "$INSTALL_DIR/"
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
cat > "$BIN_DIR/fu" <<EOF
#!/usr/bin/env bash
export FU_CALLER_CWD="\$PWD"
export FU_WORKSPACE="${WORKSPACE}"
export FU_MODEL="${MODEL}"
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/agent.py" "\$@"
EOF
chmod +x "$BIN_DIR/fu"

# Ollama is optional for deterministic FU features, but required for model fallback.
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Installing from the official installer..."
  if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl is required to install Ollama." >&2; exit 1
  fi
  curl -fsSL https://ollama.com/install.sh | sh
fi

if ! curl -fsS "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1; then
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl enable --now ollama 2>/dev/null || true
  fi
fi

if curl -fsS "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1; then
  echo "Pulling FU fallback model: $MODEL"
  ollama pull "$MODEL"
else
  echo "WARNING: Ollama is installed but not reachable. Start it, then run: ollama pull $MODEL"
fi

# User man page
mkdir -p "$HOME/.local/share/man/man1"
install -m 0644 "$INSTALL_DIR/packaging/fu.1" "$HOME/.local/share/man/man1/fu.1"
command -v mandb >/dev/null 2>&1 && mandb -q "$HOME/.local/share/man" 2>/dev/null || true

echo
echo "Running FU regression suite..."
PATH="$BIN_DIR:$PATH" fu selftest
cat <<EOF

✓ FU Terminal installed.
Add this to PATH if needed:
  export PATH="\$HOME/.local/bin:\$PATH"

Try:
  fu --auto "disk usage"
  fu investigate disk
  fu evidence
  fu learn kubectl
  man fu
EOF
