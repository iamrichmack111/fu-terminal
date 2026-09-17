#!/usr/bin/env bash
set -e
rm -f "$HOME/.local/bin/fu" "$HOME/.local/share/man/man1/fu.1"
rm -rf "${FU_INSTALL_DIR:-$HOME/.local/share/fu-terminal}"
echo "FU Terminal removed. Workspace data was left intact." 
