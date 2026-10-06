#!/usr/bin/env bash
# Developer/convenience installer for image-to-webp.
#
# Creates a local virtual environment (.venv), installs this package in editable
# mode with all optional format plugins, and links the `image-to-webp` command
# into a directory on your PATH.
#
#   ./install.sh                 install
#   ./install.sh --uninstall     remove the linked command
#   BIN_DIR=~/.local/bin ./install.sh
#   CMD_NAME=webpify ./install.sh
#
# End users can simply run: pip install "image-to-webp[all]"
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
VENV="$ROOT/.venv"
CMD_NAME="${CMD_NAME:-image-to-webp}"

# /usr/bin is read-only on macOS (System Integrity Protection), so use /usr/local/bin there.
if [ -z "${BIN_DIR:-}" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then BIN_DIR="/usr/local/bin"; else BIN_DIR="/usr/bin"; fi
fi
TARGET="$BIN_DIR/$CMD_NAME"

# Run a command, escalating with sudo only if BIN_DIR isn't writable.
as_root() {
  if [ -w "$BIN_DIR" ] || { [ ! -e "$BIN_DIR" ] && [ -w "$(dirname "$BIN_DIR")" ]; }; then
    "$@"
  else
    echo "    (sudo required to write to $BIN_DIR)"
    sudo "$@"
  fi
}

if [ "${1:-}" = "--uninstall" ]; then
  if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
    as_root rm -f "$TARGET"
    echo "Removed $TARGET"
  else
    echo "Nothing to remove at $TARGET"
  fi
  exit 0
fi

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then PYTHON="$c"; break; fi
  done
fi
[ -n "$PYTHON" ] || { echo "Error: python3 not found." >&2; exit 1; }

"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || { echo "Error: Python >= 3.9 required (found $("$PYTHON" -V 2>&1))." >&2; exit 1; }

echo "==> Creating virtual environment in $VENV"
[ -d "$VENV" ] || "$PYTHON" -m venv "$VENV"
PIP=("$VENV/bin/python" -m pip install --quiet)

echo "==> Installing image-to-webp (editable)"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"${PIP[@]}" -e "$ROOT"
# Install optional plugins one by one so a single failure doesn't block the rest.
for extra in heif raw svg; do
  "${PIP[@]}" -e "$ROOT[$extra]" \
    || echo "    Warning: could not install the '$extra' extra (those formats will be unavailable)."
done

if ! "$VENV/bin/python" -c 'import cairosvg' >/dev/null 2>&1; then
  echo "    Note: SVG support needs the cairo library (macOS: 'brew install cairo', Debian/Ubuntu: 'apt install libcairo2')."
fi

echo "==> Linking $TARGET -> $VENV/bin/image-to-webp"
as_root mkdir -p "$BIN_DIR"
as_root ln -sf "$VENV/bin/image-to-webp" "$TARGET"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "    Note: $BIN_DIR is not on your PATH; add it to use '$CMD_NAME' directly." ;;
esac

echo "==> Done."
"$TARGET" --list-formats
echo
echo "Usage: $CMD_NAME INPUT... [options]   (see $CMD_NAME --help)"
