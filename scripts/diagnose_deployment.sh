#!/bin/bash

# Quick diagnostic script to check deployment issues

echo "=== MRM Deployment Diagnostic ==="
echo ""

echo "1. Recent site deployments from database:"
mysql -u root -proot mrm_panel -e "SELECT s.id, s.name, s.status, s.runtime, d.domain, s.created_at FROM sites s JOIN domains d ON s.domain_id = d.id ORDER BY s.id DESC LIMIT 5;" 2>/dev/null || echo "Could not query database"

echo ""
echo "2. Running Docker containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "3. Recent service logs (last 30 lines):"
journalctl -u mrm-webpanel -n 30 --no-pager 2>/dev/null || echo "Could not get service logs"

echo ""
echo "4. Check if templates exist:"
ls -lh /etc/mrm-webpanel/templates/*.tpl 2>/dev/null || echo "Templates not found in /etc/mrm-webpanel/templates/"

echo ""
echo "5. Most recent site directory:"
RECENT_SITE=$(ls -td /srv/mrm/sites/*/ 2>/dev/null | head -1)
if [ -n "$RECENT_SITE" ]; then
    echo "Site: $RECENT_SITE"
    echo "Contents:"
    ls -la "$RECENT_SITE" 2>/dev/null
    echo ""
    echo "Docker compose file:"
    cat "${RECENT_SITE}docker-compose.yml" 2>/dev/null || echo "No compose file found"
else
    echo "No sites found in /srv/mrm/sites/"
fi

echo ""
echo "=== Diagnostic Complete ==="
