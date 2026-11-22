#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${AGENTOPS_PYTHON:-}" && -z "${CONDA_PREFIX:-}" ]]; then
    echo 'Activate agent-dev or set AGENTOPS_PYTHON to its interpreter.' >&2
    exit 1
fi
PYTHON="${AGENTOPS_PYTHON:-${CONDA_PREFIX:-}/bin/python}"
cd "$ROOT"
exec "$PYTHON" "$ROOT/scripts/manage.py" "$@"
