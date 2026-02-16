#!/bin/bash

# Debug Node.js and WordPress deployment issues

echo "=== Comprehensive Deployment Debug ==="
echo ""

echo "1. All site deployments:"
mysql -u root -proot mrm_panel -e "SELECT s.id, s.name, s.status, s.runtime, d.domain, d.runtime as domain_runtime, d.version FROM sites s JOIN domains d ON s.domain_id = d.id ORDER BY s.id DESC LIMIT 10;" 2>/dev/null

echo ""
echo "2. All running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}"

echo ""
echo "3. All containers (including stopped):"
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"

echo ""
echo "=== Node.js Deployment Details ==="
NODE_SITE=$(mysql -u root -proot mrm_panel -e "SELECT d.domain FROM sites s JOIN domains d ON s.domain_id = d.id WHERE d.runtime='node' ORDER BY s.id DESC LIMIT 1;" -sN 2>/dev/null)

if [ -n "$NODE_SITE" ]; then
    echo "Domain: $NODE_SITE"
    SITE_ID=$(mysql -u root -proot mrm_panel -e "SELECT s.id FROM sites s JOIN domains d ON s.domain_id = d.id WHERE d.domain='$NODE_SITE' LIMIT 1;" -sN 2>/dev/null)
    UPSTREAM_PORT=$((3000 + SITE_ID))
    echo "Site ID: $SITE_ID"
    echo "Expected Port: $UPSTREAM_PORT"
    echo ""
    
    echo "Directory structure:"
    ls -la "/srv/mrm/sites/$NODE_SITE/" 2>/dev/null || echo "Site directory not found"
    echo ""
    
    echo "Data directory files:"
    ls -la "/srv/mrm/sites/$NODE_SITE/data/" 2>/dev/null || echo "Data directory not found"
    echo ""
    
    if [ -f "/srv/mrm/sites/$NODE_SITE/data/package.json" ]; then
        echo "package.json:"
        cat "/srv/mrm/sites/$NODE_SITE/data/package.json"
        echo ""
    fi
    
    if [ -f "/srv/mrm/sites/$NODE_SITE/data/server.js" ]; then
        echo "server.js (first 40 lines):"
        head -40 "/srv/mrm/sites/$NODE_SITE/data/server.js"
        echo ""
        
        echo "Checking server.js for 0.0.0.0 binding:"
        grep -n "app.listen" "/srv/mrm/sites/$NODE_SITE/data/server.js"
        echo ""
    fi
    
    if [ -f "/srv/mrm/sites/$NODE_SITE/compose.yml" ]; then
        echo "compose.yml:"
        cat "/srv/mrm/sites/$NODE_SITE/compose.yml"
        echo ""
    fi
    
    CONTAINER_NAME="${NODE_SITE}-app"
    echo "Container status:"
    docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Status}}"
    echo ""
    
    echo "Container logs (last 100 lines):"
    docker logs "$CONTAINER_NAME" 2>&1 | tail -100 || echo "Container not found or no logs"
    echo ""
    
    echo "Testing port $UPSTREAM_PORT:"
    curl -v -m 3 "http://localhost:$UPSTREAM_PORT" 2>&1 | head -30 || echo "Connection failed"
    echo ""
    
    echo "Nginx config:"
    cat "/etc/nginx/sites-available/${NODE_SITE}.conf" 2>/dev/null || echo "No nginx config"
else
    echo "No Node.js deployments found"
fi

echo ""
echo "=== Recent Service Errors ==
"
journalctl -u mrm-webpanel -n 50 --no-pager 2>/dev/null | tail -50
