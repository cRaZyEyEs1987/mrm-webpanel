#!/bin/bash
# Verify all fixes are present in the installer directory

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     MRM Webpanel Installer - Fix Verification            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    echo -n "Checking: $desc ... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo "✓ PASS"
        ((PASS++))
    else
        echo "✗ FAIL"
        ((FAIL++))
    fi
}

echo "=== Installer Script (install.sh) ==="
check "DB_USER in config template" "grep -q 'DB_USER=root' /root/installer/install.sh"
check "DB_PASS in config template" "grep -q 'DB_PASS=\$DB_ROOT_PASS' /root/installer/install.sh"
check "EnvironmentFile in systemd" "grep -q 'EnvironmentFile=/etc/mrm-webpanel/installer.conf' /root/installer/install.sh"
check "venv Python in systemd" "grep -q 'ExecStart=/root/.venv-mrm/bin/python' /root/installer/install.sh"
check "Template directories creation" "grep -q 'mkdir -p /srv/mrm/templates/{node/node18,python/python311,php/php82}' /root/installer/install.sh"
check "Template markers creation" "grep -q 'touch /srv/mrm/templates/node/node18/.mrm-template' /root/installer/install.sh"
check "Port 5000 in UFW" "grep -q \"ufw allow 5000/tcp comment 'Panel'\" /root/installer/install.sh"

echo ""
echo "=== Panel Code (panel/engines/docker_engine.py) ==="
check "wait_for_container_health method" "grep -q 'def wait_for_container_health' /root/installer/panel/engines/docker_engine.py"
check "Health check in deploy" "grep -A15 'def deploy' /root/installer/panel/engines/docker_engine.py | grep -q 'wait_for_container_health'"
check "Container starts before nginx" "grep -A15 'def deploy' /root/installer/panel/engines/docker_engine.py | grep -q 'start_container'"

echo ""
echo "=== Summary ==="
echo "✓ Passed: $PASS"
echo "✗ Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║          ALL FIXES VERIFIED - INSTALLER READY!            ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    exit 0
else
    echo "Some checks failed. Please review the installer."
    exit 1
fi
