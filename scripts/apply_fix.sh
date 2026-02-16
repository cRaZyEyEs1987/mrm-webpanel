#!/bin/bash

# Fix applied: Updated boilerplate code to read PORT from environment
# Node.js now uses: const port = process.env.PORT || 3000;
# Python now uses: port = int(os.environ.get('PORT', 3000))

echo "=== Restarting MRM Webpanel Service ==="
echo ""
echo "Changes applied:"
echo "  ✓ Node.js boilerplate now reads PORT from environment"
echo "  ✓ Python boilerplate now reads PORT from environment"  
echo "  ✓ PHP already uses Apache on port 80"
echo ""

echo "Restarting service..."
systemctl restart mrm-webpanel

echo "Waiting for service to start..."
sleep 3

echo ""
echo "Service status:"
systemctl status mrm-webpanel --no-pager -l | head -15

echo ""
echo "=== IMPORTANT ==="
echo ""
echo "Existing deployments still have OLD code with hardcoded ports!"
echo ""
echo "To fix 502 errors, you need to:"
echo "  1. DELETE the existing deployment"
echo "  2. CREATE a new deployment (this will use the new boilerplate code)"
echo ""
echo "Or run the automated test script:"
echo "  bash /root/scripts/test_all_deployments.sh"
echo ""
echo "To manually test a specific domain:"
echo "  1. Go to dashboard: http://localhost:5000/dashboard"
echo "  2. Delete the failing site/domain"
echo "  3. Create new domain with same runtime"
echo "  4. Deploy with blank or wordpress option"
echo "  5. Wait 15-20 seconds for container to install dependencies"
echo "  6. Check if site loads without 502 error"
echo ""
