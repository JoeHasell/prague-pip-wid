#!/bin/bash
# SessionStart hook — prepare a Claude Code *web* container for this repo.
#
# Two things this repo needs that a fresh container does not have, both of them
# load-bearing for verification rather than for the deck itself:
#
#   1. pandas + pyarrow  -> data/scripts/99_verify.py (the 19-check pipeline
#      suite) and every figure script.
#   2. playwright        -> the headless screenshot harness, the only way to see
#      whether a slide overflows the fixed 1280x720 canvas.
#
# Playwright is installed OUTSIDE the repo and reached via NODE_PATH, so the
# deck stays a zero-dependency, no-build project (no package.json in the root).
# Chromium itself is preinstalled at /opt/pw-browsers — never download it.
#
# Idempotent: safe to re-run. Non-fatal: a failed install prints a warning and
# lets the session start anyway, so a network blip never blocks slides work.

set -uo pipefail

# Web sessions only. On a local Mac checkout the environment is Joe's own.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TOOLS_DIR="$HOME/.deck-tools"

# --- 1. Python: the data pipeline ------------------------------------------
if python3 -c 'import pandas, pyarrow' 2>/dev/null; then
  echo "session-start: pandas/pyarrow already present"
else
  echo "session-start: installing Python deps (data/requirements.txt)"
  pip install --quiet --disable-pip-version-check --root-user-action=ignore \
      -r "$PROJECT_DIR/data/requirements.txt" \
    || echo "session-start: WARNING pip install failed — run it by hand before touching data/"
fi

# --- 2. Node: the headless render harness -----------------------------------
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}"
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

if [ -d "$TOOLS_DIR/node_modules/playwright" ]; then
  echo "session-start: playwright already present in $TOOLS_DIR"
else
  echo "session-start: installing playwright into $TOOLS_DIR"
  mkdir -p "$TOOLS_DIR"
  npm install --silent --no-fund --no-audit --prefix "$TOOLS_DIR" playwright \
    || echo "session-start: WARNING playwright install failed — screenshots unavailable"
fi

# --- 3. Persist env for the session ----------------------------------------
# NODE_PATH lets `require('playwright')` resolve from anywhere, incl. a script
# written to the scratchpad. CHROMIUM_PATH is the executablePath to launch with.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export NODE_PATH=\"$TOOLS_DIR/node_modules\${NODE_PATH:+:\$NODE_PATH}\""
    echo 'export PLAYWRIGHT_BROWSERS_PATH="/opt/pw-browsers"'
    echo 'export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1'
    echo 'export CHROMIUM_PATH="/opt/pw-browsers/chromium"'
  } >> "$CLAUDE_ENV_FILE"
fi

echo "session-start: ready — verify with 'python data/scripts/99_verify.py'"
