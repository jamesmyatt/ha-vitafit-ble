#!/usr/bin/env bash
# Run Home Assistant's hassfest validator against this integration.
# Requires the project venv (.venv) to be set up first; see CLAUDE.md.
set -euo pipefail

HA_TAG="${HA_TAG:-2026.10.0b0}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone -q --depth 1 --branch "$HA_TAG" --filter=blob:none --sparse \
  https://github.com/home-assistant/core.git "$WORK/core"
git -C "$WORK/core" sparse-checkout set script
# Run outside the core tree so the installed homeassistant package is used.
cp -r "$WORK/core/script" "$WORK/"
VIRTUAL_ENV="$REPO/.venv" uv pip install -q --prerelease=allow infrared-protocols

cd "$WORK"
"$REPO/.venv/bin/python" -m script.hassfest --action validate \
  --integration-path "$REPO/custom_components/vitafit_ble"
