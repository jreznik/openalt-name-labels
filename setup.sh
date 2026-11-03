#!/usr/bin/env bash
# One-step setup for openalt-name-labels on macOS and Linux:
#   1. creates .venv and installs the tool
#   2. finds the Bixolon printer on USB and creates the CUPS queue "XD5"
#
# Usage: ./setup.sh [--no-printer] [--queue NAME] [--uri usb://...]
set -euo pipefail

cd "$(dirname "$0")"
QUEUE="XD5"
URI=""
SETUP_PRINTER=1

while [ $# -gt 0 ]; do
  case "$1" in
    --no-printer) SETUP_PRINTER=0 ;;
    --queue) QUEUE="$2"; shift ;;
    --uri) URI="$2"; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

say()  { printf '\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }


# --- 1. Python environment -------------------------------------------------
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || fail "python3 not found. macOS: 'brew install python' / Linux: 'sudo apt install python3 python3-venv' or 'sudo dnf install python3'"
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || fail "Python 3.10+ required (found $("$PY" -V))"

say "Creating .venv and installing openalt-name-labels"
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv || fail "venv failed. On Debian/Ubuntu: sudo apt install python3-venv"
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -e .
.venv/bin/openalt-name-labels --help >/dev/null
say "Installed: $(pwd)/.venv/bin/openalt-name-labels"

[ "$SETUP_PRINTER" = 1 ] || { say "Skipping printer setup (--no-printer)"; exit 0; }

# --- 2. CUPS queue ----------------------------------------------------------
command -v lpadmin >/dev/null || fail "CUPS not found. Linux: 'sudo apt install cups' or 'sudo dnf install cups', then 'sudo systemctl enable --now cups'"

if [ -z "$URI" ]; then
  say "Looking for the Bixolon printer on USB (make sure it is plugged in and on)"
  URI="$( (lpinfo -v 2>/dev/null || sudo lpinfo -v) | awk '/usb:\/\/BIXOLON/ {print $2; exit}')"
  [ -n "$URI" ] || fail "No usb://BIXOLON/... device found. Check the cable/power, or pass --uri (see 'lpinfo -v')."
fi
say "Printer: $URI"

say "Creating CUPS queue '$QUEUE' (raw ZPL passthrough)"
LPADMIN=(lpadmin -p "$QUEUE" -E -v "$URI" -P cups/xd5-raw.ppd -D "Bixolon XD5 (raw ZPL)")
# macOS admins can run lpadmin directly; Linux usually needs root or the lpadmin group.
if ! "${LPADMIN[@]}" 2>/dev/null; then
  echo "    (needs administrator rights, asking for sudo)"
  sudo "${LPADMIN[@]}"
fi
cupsenable "$QUEUE" 2>/dev/null || sudo cupsenable "$QUEUE" 2>/dev/null || true
cupsaccept "$QUEUE" 2>/dev/null || sudo cupsaccept "$QUEUE" 2>/dev/null || true

lpstat -p "$QUEUE" >/dev/null 2>&1 || fail "Queue '$QUEUE' was not created"
say "Done. Queue '$QUEUE' is ready."
cat <<EOF

Next steps:
  .venv/bin/openalt-name-labels --grid                 # optional: print a ruler to check the label position
  .venv/bin/openalt-name-labels "Jane Doe" --preview out/   # preview PNG, prints nothing
  .venv/bin/openalt-name-labels "Jane Doe"             # print one test label
EOF
[ "$QUEUE" = "XD5" ] || echo "  (use -P $QUEUE or export BADGE_PRINTER=$QUEUE, since the queue isn't named XD5)"
