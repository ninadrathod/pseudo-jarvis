#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="${PROJECT_ROOT}/setup-variables"
MDS_RULE="${PROJECT_ROOT}/.cursor/rules/voice-input-confirmation.mds"
VENV_DIR="${PROJECT_ROOT}/.venv"

mkdir -p "${SETUP_DIR}"

printf '%s\n' "${MDS_RULE}" > "${SETUP_DIR}/mds-path.txt"
printf '%s/\n' "${PROJECT_ROOT}" > "${SETUP_DIR}/subscribed-projects.txt"

python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
pip install -r "${PROJECT_ROOT}/requirements.txt"
deactivate

echo "Setup complete."
