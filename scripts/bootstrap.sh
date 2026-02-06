#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v python3.13 >/dev/null 2>&1; then
  PY=python3.13
else
  PY=python3
fi

V="$($PY -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')"
if [[ "$V" == "3.9" || "$V" == "3.8" || "$V" == "3.7" || "$V" == "3.6" ]]; then
  echo "ERROR: нужен Python >= 3.10 (aiogram 3.x). Сейчас: $($PY -V)" >&2
  echo "Поставь python@3.13: brew install python@3.13" >&2
  exit 1
fi

$PY -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "OK: venv created in .venv and deps installed."
