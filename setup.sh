#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="${PROJECT_ROOT}/setup-variables"
MDS_RULE="${PROJECT_ROOT}/.cursor/rules/voice-input-confirmation.mds"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [[ ! -f "${MDS_RULE}" ]]; then
  echo "error: missing voice rule: ${MDS_RULE}" >&2
  exit 1
fi

mkdir -p "${SETUP_DIR}"

printf '%s\n' "${MDS_RULE}" > "${SETUP_DIR}/mds-path.txt"
printf '%s/\n' "${PROJECT_ROOT}" > "${SETUP_DIR}/subscribed-projects.txt"

echo "Wrote ${SETUP_DIR}/mds-path.txt"
echo "Wrote ${SETUP_DIR}/subscribed-projects.txt"

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
  echo "Created ${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
pip install -r "${PROJECT_ROOT}/requirements.txt"
deactivate

echo ""
echo "Setup complete."
echo "  Activate venv:  source .venv/bin/activate"
echo "  Run GUI:        python gui_app.py"
