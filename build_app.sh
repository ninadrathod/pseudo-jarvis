#!/usr/bin/env bash
# Build pseudo-jarvis.app for macOS Applications folder (PyInstaller).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"

if [[ ! -d "${VENV}" ]]; then
  echo "Run ./setup.sh first to create .venv and install requirements."
  exit 1
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

pip install -q pyinstaller

pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "pseudo-jarvis" \
  --hidden-import=pynput.keyboard \
  --hidden-import=pynput.mouse \
  --collect-submodules speech_recognition \
  --add-data "${ROOT}/.cursor/rules/sync-root-docs.mds:.cursor/rules" \
  --add-data "${ROOT}/.cursor/rules/voice-input-confirmation.mds:.cursor/rules" \
  "${ROOT}/gui_app.py"

APP_PATH="${ROOT}/dist/pseudo-jarvis.app"

echo ""
echo "Built: ${APP_PATH}"
echo ""
echo "Install to Applications (optional):"
echo "  cp -R \"${APP_PATH}\" /Applications/"
echo ""
echo "Grant Microphone and Accessibility for pseudo-jarvis in"
echo "System Settings → Privacy & Security (required for dictation)."
