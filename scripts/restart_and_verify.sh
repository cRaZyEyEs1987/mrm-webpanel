#!/bin/bash

# Restart MRM Webpanel service and verify configuration

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MRM Webpanel - Service Restart & Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "[1/4] Verifying templates exist in /etc/mrm-webpanel/templates/..."
TEMPLATES_FOUND=0
for TPL in docker-compose.node.tpl docker-compose.python.tpl docker-compose.php.tpl docker-compose.wordpress.tpl nginx_vhost.conf.tpl; do
    if [[ -f "/etc/mrm-webpanel/templates/$TPL" ]]; then
        SIZE=$(stat -f%z "/etc/mrm-webpanel/templates/$TPL" 2>/dev/null || stat -c%s "/etc/mrm-webpanel/templates/$TPL" 2>/dev/null)
        if [[ $SIZE -gt 0 ]]; then
            echo "  ✓ $TPL (${SIZE} bytes)"
            TEMPLATES_FOUND=$((TEMPLATES_FOUND + 1))
        else
            echo "  ✗ $TPL is empty!"
        fi
    else
        echo "  ✗ $TPL not found!"
    fi
done

if [[ $TEMPLATES_FOUND -lt 5 ]]; then
    echo ""
    echo "ERROR: Not all templates found. Expected 5, found $TEMPLATES_FOUND"
    exit 1
fi

echo ""
echo "[2/4] Restarting mrm-webpanel service..."
systemctl restart mrm-webpanel

echo ""
echo "[3/4] Waiting for service to start..."
sleep 3

echo ""
echo "[4/4] Checking service status..."
systemctl status mrm-webpanel --no-pager -l | head -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Service restarted successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Run automated tests: bash /root/scripts/test_all_deployments.sh"
echo "  2. Check dashboard: http://localhost:5000/dashboard"
echo "  3. View logs: journalctl -u mrm-webpanel -f"
echo ""
