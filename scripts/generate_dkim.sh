#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root to create DKIM keys."; exit 2
fi
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 example.com [selector]"; exit 1
fi
DOMAIN="$1"
SEL=${2:-default}
KEYDIR="/etc/opendkim/keys/${DOMAIN}"
mkdir -p "$KEYDIR"
if command -v opendkim-genkey &>/dev/null; then
  opendkim-genkey -D "$KEYDIR" -d "$DOMAIN" -s "$SEL"
  chown -R opendkim:opendkim "$KEYDIR" || true
  echo "DKIM keys created in $KEYDIR. Public TXT (copy to DNS):"
  cat "$KEYDIR/${SEL}.txt"
else
  echo "opendkim-genkey not found. Install opendkim-tools first."
  exit 1
fi
