#!/usr/bin/env bash
set -euo pipefail

# Creates a WordPress boilerplate under /srv/mrm/templates/php/php82/wordpress
# This script downloads WordPress from wordpress.org and extracts it into the template directory.

TEMPLATE_ROOT="/srv/mrm/templates/php/php82"
TARGET_DIR="${TEMPLATE_ROOT}/wordpress"

mkdir -p "$TARGET_DIR"

tmpdir="$(mktemp -d)"
cleanup() { rm -rf "$tmpdir"; }
trap cleanup EXIT

archive="$tmpdir/wordpress.tar.gz"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "https://wordpress.org/latest.tar.gz" -o "$archive"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$archive" "https://wordpress.org/latest.tar.gz"
else
  echo "ERROR: need curl or wget to download WordPress" >&2
  exit 1
fi

tar -xzf "$archive" -C "$tmpdir"

# The tarball extracts to a 'wordpress' directory
if [ ! -d "$tmpdir/wordpress" ]; then
  echo "ERROR: unexpected archive layout" >&2
  exit 1
fi

# Copy into the template dir
rsync -a --delete "$tmpdir/wordpress/" "$TARGET_DIR/"

# Ensure a default php.ini exists in the template (copied to sites on deploy)
if [ ! -f "$TARGET_DIR/php.ini" ]; then
  cat > "$TARGET_DIR/php.ini" <<'EOF'
; MRM per-domain PHP overrides
; Place only directives you want to override.
; Changes apply after container restart.
EOF
fi

echo "OK: WordPress template created at $TARGET_DIR"