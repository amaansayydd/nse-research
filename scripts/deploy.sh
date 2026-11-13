#!/bin/zsh
# Deploy a committed version of the code to the copy the scheduled job runs.
#
#   scripts/deploy.sh            deploy HEAD
#   scripts/deploy.sh <commit>   deploy (or roll back to) that commit
#
# The job never runs the working folder. It runs ~/nse_production/app/current, a copy of one
# commit, with its own Python environment, and writes its records back into this project.
# Uncommitted edits are never deployed. The tests must pass on the copy before it goes live.
set -e
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
PROD="$HOME/nse_production"
SHA="$(git -C "$PROJ" rev-parse --short "${1:-HEAD}")"
REL="$PROD/app/releases/$SHA"
PY="$PROD/venv/bin/python"

if [ ! -x "$PY" ]; then
  uv venv --python 3.12 "$PROD/venv"
fi
uv pip install -q --python "$PY" -r <(git -C "$PROJ" show "$SHA:scripts/requirements-prod.txt")

rm -rf "$REL"
mkdir -p "$REL"
git -C "$PROJ" archive "$SHA" src models tests pyproject.toml | tar -x -C "$REL"
echo "$SHA" > "$REL/RELEASE"
( cd "$REL" && env -u NSR_PROJECT -u NSR_PRODUCTION PYTHONPATH="$REL/src" "$PY" -m pytest -q -p no:cacheprovider tests )
ln -sfn "$REL" "$PROD/app/current"
echo "$(date '+%Y-%m-%d %H:%M') $SHA" >> "$PROD/app/deploys.log"
echo "deployed $SHA -> $PROD/app/current"
