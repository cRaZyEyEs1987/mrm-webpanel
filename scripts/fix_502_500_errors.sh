#!/bin/bash

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deployment Fix & Debug - Node.js 502 & Container Restart Issues"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Step 1: Restarting MRM Webpanel service..."
systemctl restart mrm-webpanel
sleep 3

echo ""
echo "Step 2: Checking service status..."
systemctl status mrm-webpanel --no-pager -l | head -15

echo ""
echo "Step 3: Running comprehensive diagnostics..."
echo ""
bash /root/scripts/debug_deployments.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Diagnostic complete - Review output above"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Common issues and fixes:"
echo ""
echo "1. Container shows 'Exited' status:"
echo "   → Check container logs above for errors"
echo "   → Likely: npm install failed or server.js has errors"
echo ""
echo "2. Container logs show 'npm ERR!' or 'Cannot find module':"
echo "   → Delete and recreate the deployment via dashboard"
echo "   → Wait 30-60 seconds for npm install to complete"
echo ""
echo "3. Container not found:"
echo "   → Try the migration endpoint:"
echo "   → curl -X POST http://localhost:5000/admin/migrate-deployments \\"
echo "        -H 'Authorization: Bearer YOUR_TOKEN'"
echo ""
echo "4. 502/503 errors persist:"
echo "   → Check if port is actually listening: netstat -tlnp | grep PORT"
echo "   → Check nginx config for correct upstream port"
echo ""
