#!/bin/bash
#
# MRM Webpanel Verification Script
# Verifies that all components are properly installed and running
#

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Load configuration if exists
if [[ -f /etc/mrm-webpanel/installer.conf ]]; then
    source /etc/mrm-webpanel/installer.conf
fi

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

echo ""
echo "======================================"
echo "  MRM WEBPANEL VERIFICATION"
echo "======================================"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script should be run as root${NC}"
   exit 1
fi

# 1. Check system services
echo "Checking system services..."
echo ""

for service in mariadb docker nginx fail2ban mrm-webpanel; do
    if systemctl is-active --quiet "$service"; then
        check_pass "$service is running"
    else
        check_fail "$service is NOT running"
    fi
done

# Check mail services if installed
if [[ "${INSTALL_MAIL:-yes}" == "yes" ]]; then
    for service in postfix dovecot opendkim; do
        if systemctl is-active --quiet "$service"; then
            check_pass "$service is running"
        else
            check_fail "$service is NOT running"
        fi
    done
fi

# Check DNS service if installed
if [[ "${INSTALL_DNS:-yes}" == "yes" ]]; then
    if systemctl is-active --quiet bind9; then
        check_pass "bind9 is running"
    else
        check_fail "bind9 is NOT running"
    fi
fi

echo ""
echo "Checking database connectivity..."
echo ""

# 2. Test database
DB_USER="${DB_PANEL_USER:-mrm}"
DB_PASS="${DB_PANEL_PASS:-mrm_password}"
DB_NAME="${DB_NAME:-mrm_panel}"

if mariadb -u "$DB_USER" -p"$DB_PASS" -e "USE $DB_NAME; SELECT COUNT(*) FROM users;" &>/dev/null; then
    check_pass "Database connection successful"
    
    # Check table count
    TABLE_COUNT=$(mariadb -u "$DB_USER" -p"$DB_PASS" -D "$DB_NAME" -e "SHOW TABLES;" 2>/dev/null | wc -l)
    if [[ $TABLE_COUNT -gt 5 ]]; then
        check_pass "Database schema loaded ($((TABLE_COUNT - 1)) tables)"
    else
        check_fail "Database schema incomplete ($((TABLE_COUNT - 1)) tables)"
    fi
else
    check_fail "Cannot connect to database"
fi

echo ""
echo "Checking panel application..."
echo ""

# 3. Check panel API
if curl -sf http://localhost:5000/ > /dev/null; then
    check_pass "Panel API is responding on port 5000"
else
    check_fail "Panel API is NOT responding"
fi

# Check if panel process is running
if pgrep -f "python3.*app.py" > /dev/null; then
    check_pass "Panel process is running"
else
    check_fail "Panel process is NOT running"
fi

echo ""
echo "Checking directory structure..."
echo ""

# 4. Check directories
REQUIRED_DIRS=(
    "/etc/mrm-webpanel"
    "/etc/mrm-webpanel/templates"
    "/srv/mrm/sites"
    "/var/log/mrm-webpanel"
    "/root/panel"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        check_pass "Directory exists: $dir"
    else
        check_fail "Directory missing: $dir"
    fi
done

# Check vmail directory if mail installed
if [[ "${INSTALL_MAIL:-yes}" == "yes" ]]; then
    if [[ -d /var/mail/vmail ]]; then
        check_pass "Directory exists: /var/mail/vmail"
        
        # Check ownership
        OWNER=$(stat -c '%U:%G' /var/mail/vmail)
        if [[ "$OWNER" == "vmail:vmail" ]]; then
            check_pass "vmail directory ownership correct"
        else
            check_fail "vmail directory ownership incorrect (got: $OWNER, expected: vmail:vmail)"
        fi
    else
        check_fail "Directory missing: /var/mail/vmail"
    fi
fi

echo ""
echo "Checking templates..."
echo ""

# 5. Check templates
TEMPLATE_COUNT=$(find /etc/mrm-webpanel/templates/ -name "*.tpl" 2>/dev/null | wc -l)
if [[ $TEMPLATE_COUNT -ge 5 ]]; then
    check_pass "Templates installed ($TEMPLATE_COUNT .tpl files)"
else
    check_warn "Only $TEMPLATE_COUNT template files found (expected 5+)"
fi

# Check specific templates
TEMPLATES=(
    "docker-compose.node.tpl"
    "docker-compose.python.tpl"
    "docker-compose.php.tpl"
    "docker-compose.wordpress.tpl"
    "nginx_vhost.conf.tpl"
)

for tpl in "${TEMPLATES[@]}"; do
    if [[ -f "/etc/mrm-webpanel/templates/$tpl" ]]; then
        SIZE=$(stat -c%s "/etc/mrm-webpanel/templates/$tpl")
        if [[ $SIZE -gt 100 ]]; then
            check_pass "Template OK: $tpl"
        else
            check_warn "Template may be empty: $tpl (${SIZE} bytes)"
        fi
    else
        check_fail "Template missing: $tpl"
    fi
done

echo ""
echo "Checking Docker..."
echo ""

# 6. Check Docker
if docker ps &>/dev/null; then
    check_pass "Docker is operational"
    
    # Check docker compose
    if docker compose version &>/dev/null; then
        VERSION=$(docker compose version --short 2>/dev/null || echo "unknown")
        check_pass "Docker Compose available (v$VERSION)"
    else
        check_fail "Docker Compose not available"
    fi
else
    check_fail "Docker is not operational"
fi

echo ""
echo "Checking Nginx..."
echo ""

# 7. Check Nginx configuration
if nginx -t &>/dev/null; then
    check_pass "Nginx configuration is valid"
else
    check_fail "Nginx configuration has errors"
fi

# Check panel proxy config
if [[ -f /etc/nginx/sites-available/mrm-panel.conf ]]; then
    check_pass "Panel nginx config exists"
    
    if [[ -L /etc/nginx/sites-enabled/mrm-panel.conf ]]; then
        check_pass "Panel nginx config is enabled"
    else
        check_fail "Panel nginx config is NOT enabled"
    fi
else
    check_fail "Panel nginx config missing"
fi

echo ""
echo "Checking firewall..."
echo ""

# 8. Check UFW
if systemctl is-active --quiet ufw; then
    check_pass "UFW firewall is active"
    
    # Check if ports are allowed
    if ufw status | grep -q "80/tcp"; then
        check_pass "HTTP port (80) is allowed"
    else
        check_warn "HTTP port (80) may not be allowed"
    fi
    
    if ufw status | grep -q "443/tcp"; then
        check_pass "HTTPS port (443) is allowed"
    else
        check_warn "HTTPS port (443) may not be allowed"
    fi
else
    check_warn "UFW firewall is not active"
fi

echo ""
echo "Checking Python environment..."
echo ""

# 9. Check Python dependencies
if [[ -f /root/panel/requirements.txt ]]; then
    check_pass "requirements.txt exists"
    
    if [[ -d /root/.venv-mrm ]]; then
        check_pass "Python virtual environment exists"
        
        # Activate and check packages
        source /root/.venv-mrm/bin/activate
        if python3 -c "import flask; import pymysql; import bcrypt" &>/dev/null; then
            check_pass "Required Python packages are installed"
        else
            check_fail "Some Python packages are missing"
        fi
        deactivate
    else
        check_fail "Python virtual environment missing"
    fi
else
    check_fail "requirements.txt missing"
fi

# 10. Check DNS configuration (if installed)
if [[ "${INSTALL_DNS:-yes}" == "yes" ]]; then
    echo ""
    echo "Checking Bind9 DNS..."
    echo ""
    
    if named-checkconf &>/dev/null; then
        check_pass "Bind9 configuration is valid"
    else
        check_fail "Bind9 configuration has errors"
    fi
    
    if [[ -f /etc/bind/mrm-zones.conf ]]; then
        check_pass "MRM zones config file exists"
    else
        check_fail "MRM zones config file missing"
    fi
    
    if [[ -d /etc/bind/zones ]]; then
        check_pass "DNS zones directory exists"
    else
        check_fail "DNS zones directory missing"
    fi
fi

# 11. Check mail configuration (if installed)
if [[ "${INSTALL_MAIL:-yes}" == "yes" ]]; then
    echo ""
    echo "Checking mail server..."
    echo ""
    
    if postfix check &>/dev/null; then
        check_pass "Postfix configuration is valid"
    else
        check_warn "Postfix configuration may have warnings"
    fi
    
    # Check MySQL config files
    MYSQL_CONFIGS=(
        "/etc/postfix/mysql-virtual-mailbox-domains.cf"
        "/etc/postfix/mysql-virtual-mailbox-maps.cf"
        "/etc/postfix/mysql-virtual-alias-maps.cf"
    )
    
    for config in "${MYSQL_CONFIGS[@]}"; do
        if [[ -f "$config" ]]; then
            check_pass "Postfix MySQL config exists: $(basename $config)"
        else
            check_fail "Postfix MySQL config missing: $(basename $config)"
        fi
    done
    
    # Check Dovecot
    if [[ -f /etc/dovecot/dovecot-sql.conf.ext ]]; then
        check_pass "Dovecot SQL config exists"
    else
        check_fail "Dovecot SQL config missing"
    fi
    
    # Check OpenDKIM
    if [[ -d /etc/opendkim/keys ]]; then
        check_pass "OpenDKIM keys directory exists"
    else
        check_fail "OpenDKIM keys directory missing"
    fi
fi

# 12. Check system users
echo ""
echo "Checking system users..."
echo ""

if id vmail &>/dev/null; then
    VMAIL_UID=$(id -u vmail)
    VMAIL_GID=$(id -g vmail)
    if [[ "$VMAIL_UID" == "5000" && "$VMAIL_GID" == "5000" ]]; then
        check_pass "vmail user exists with correct UID:GID (5000:5000)"
    else
        check_warn "vmail user exists but UID:GID is $VMAIL_UID:$VMAIL_GID (expected 5000:5000)"
    fi
else
    check_fail "vmail user does not exist"
fi

if getent group sftpusers &>/dev/null; then
    check_pass "sftpusers group exists"
else
    check_fail "sftpusers group does not exist"
fi

# Summary
echo ""
echo "======================================"
echo "  VERIFICATION SUMMARY"
echo "======================================"
echo ""
echo -e "${GREEN}Passed:${NC}   $PASSED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo -e "${RED}Failed:${NC}   $FAILED"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    
    # Show access information
    if [[ -f /etc/mrm-webpanel/installer.conf ]]; then
        source /etc/mrm-webpanel/installer.conf
        SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
        
        echo "Panel Access:"
        echo "  URL: http://$SERVER_IP:5000"
        if [[ -n "$HOSTNAME" ]]; then
            echo "  or:  http://$HOSTNAME:5000"
        fi
        echo ""
        echo "  Default credentials:"
        echo "    Username: root"
        echo "    Password: [set during installation]"
        echo ""
    fi
    
    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}Note: $WARNINGS warning(s) detected. Review above for details.${NC}"
        echo ""
    fi
    
    exit 0
else
    echo -e "${RED}✗ Installation verification failed!${NC}"
    echo ""
    echo "Please check the errors above and review:"
    echo "  - Service logs: journalctl -u mrm-webpanel"
    echo "  - Installation log: /var/log/mrm-installer.log"
    echo ""
    exit 1
fi
