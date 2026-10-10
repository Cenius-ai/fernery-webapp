#!/usr/bin/env bash
# Fernery setup.
#
# Fernery itself has no third-party dependencies: it is one file that uses the
# Python 3.9+ standard library. This script therefore only
#   1. refreshes the pip tooling,
#   2. links the optional `fernery` console command into the current environment
#      (editable install of this project, never anything else), and
#   3. proves the module imports on the interpreter it installed against.
#
# It installs nothing system-wide, needs no network once pip can resolve, and
# exits - it never starts a program that keeps running.

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "fernery: error: $PYTHON was not found on PATH (Fernery needs Python 3.9 or newer)" >&2
    exit 1
fi

echo "1/3  Refreshing pip, setuptools and wheel ..."
"$PYTHON" -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || \
    echo "     note: could not refresh the pip tooling (offline?); continuing with what is installed."

echo "2/3  Linking the 'fernery' command into this environment ..."
if ! "$PYTHON" -m pip install --no-build-isolation -e . >/dev/null 2>&1; then
    if ! "$PYTHON" -m pip install --no-build-isolation --user -e . >/dev/null 2>&1; then
        echo "     note: could not link the 'fernery' command (no write access to this environment)." >&2
        echo "     note: Fernery still runs as: $PYTHON fernery.py --help" >&2
    fi
fi

echo "3/3  Checking that fernery imports ..."
"$PYTHON" -c "import fernery; assert fernery.STAGES and fernery.COLORS"

echo
echo "Setup complete."
echo "  Run it   : $PYTHON fernery.py --help      (or: fernery --help)"
echo "  Watch it : bash demo.sh"
echo "  Test it  : $PYTHON -m unittest discover -s tests"
