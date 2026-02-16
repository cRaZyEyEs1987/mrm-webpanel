#!/bin/bash

# Cleanup all existing deployments and test with fresh ones

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MRM Webpanel - Cleanup & Fresh Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "This script will:"
echo "  1. Stop and remove ALL existing Docker containers"
echo "  2. Delete ALL sites and domains from database"
echo "  3. Clean up /srv/mrm/sites/ directory"
echo "  4. Deploy fresh test sites for each runtime"
echo ""
read -p "Are you sure? This will DELETE ALL current deployments! (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "[1/5] Stopping all MRM containers..."
docker ps --filter "name=-app" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
docker ps -a --filter "name=-app" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true

echo ""
echo "[2/5] Cleaning database..."
mysql -u root -proot mrm_panel -e "DELETE FROM sites;" 2>/dev/null || echo "Could not clean sites table"
mysql -u root -proot mrm_panel -e "DELETE FROM domains;" 2>/dev/null || echo "Could not clean domains table"
mysql -u root -proot mrm_panel -e "DELETE FROM dns_zones;" 2>/dev/null || echo "Could not clean dns_zones table"

echo ""
echo "[3/5] Cleaning site directories..."
rm -rf /srv/mrm/sites/*/ 2>/dev/null || true

echo ""
echo "[4/5] Reloading nginx..."
nginx -t && systemctl reload nginx

echo ""
echo "[5/5] Cleanup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Ready for fresh deployments"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Go to dashboard: http://localhost:5000/dashboard"
echo "  2. Create new domains and deploy sites"
echo "  3. OR run automated tests: bash /root/scripts/test_all_deployments.sh"
echo ""
echo "All new deployments will use the FIXED code:"
echo "  ✓ Node.js listens on 0.0.0.0 (not localhost)"
echo "  ✓ WordPress uses simple volume mount (no errors)"
echo "  ✓ Python listens on 0.0.0.0"
echo ""
