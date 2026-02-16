#!/bin/bash
#
# MRM Webpanel Installer
# Complete installation script for MRM hosting panel
#
# Usage: sudo bash install.sh [options]
# Options:
#   --hostname FQDN        Set server hostname
#   --db-pass PASSWORD     Set MariaDB root password
#   --admin-pass PASSWORD  Set panel admin password
#   --skip-mail           Skip mail server installation
#   --skip-dns            Skip DNS server installation
#   --unattended          Run without prompts (use defaults)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="/var/log/mrm-installer.log"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default configuration
HOSTNAME="${HOSTNAME:-panel.example.com}"
DB_ROOT_PASS="${DB_ROOT_PASS:-root}"
DB_PANEL_USER="mrm"
DB_PANEL_PASS="${DB_PANEL_PASS:-mrm_password}"
DB_NAME="mrm_panel"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"
INSTALL_MAIL="${INSTALL_MAIL:-yes}"
INSTALL_DNS="${INSTALL_DNS:-yes}"
UNATTENDED="${UNATTENDED:-no}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --hostname)
            HOSTNAME="$2"
            shift 2
            ;;
        --db-pass)
            DB_ROOT_PASS="$2"
            shift 2
            ;;
        --admin-pass)
            ADMIN_PASSWORD="$2"
            shift 2
            ;;
        --skip-mail)
            INSTALL_MAIL="no"
            shift
            ;;
        --skip-dns)
            INSTALL_DNS="no"
            shift
            ;;
        --unattended)
            UNATTENDED="yes"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root"
   exit 1
fi

# Print banner
clear
cat <<'EOF'
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║            MRM WEBPANEL INSTALLER                         ║
║                                                           ║
║     Docker-Based Hosting Control Panel                   ║
║     with Nginx, Mail & DNS Server Support                ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

EOF

log "Starting MRM Webpanel installation..."
log "Installation directory: $INSTALL_DIR"
log "Log file: $LOG_FILE"

# Interactive prompts (unless unattended)
if [[ "$UNATTENDED" != "yes" ]]; then
    echo ""
    log_info "=== Configuration ==="
    echo ""
    
    read -p "Enter server hostname/FQDN [$HOSTNAME]: " input
    HOSTNAME="${input:-$HOSTNAME}"
    
    read -sp "Enter MariaDB root password [$DB_ROOT_PASS]: " input
    echo ""
    DB_ROOT_PASS="${input:-$DB_ROOT_PASS}"
    
    read -sp "Enter panel admin password [$ADMIN_PASSWORD]: " input
    echo ""
    ADMIN_PASSWORD="${input:-$ADMIN_PASSWORD}"
    
    read -p "Install mail server (Postfix/Dovecot)? [Y/n]: " input
    if [[ "$input" =~ ^[Nn] ]]; then
        INSTALL_MAIL="no"
    fi
    
    read -p "Install DNS server (Bind9)? [Y/n]: " input
    if [[ "$input" =~ ^[Nn] ]]; then
        INSTALL_DNS="no"
    fi
    
    echo ""
    log_info "=== Review Configuration ==="
    echo "Hostname: $HOSTNAME"
    echo "Database root password: [hidden]"
    echo "Panel admin password: [hidden]"
    echo "Install mail server: $INSTALL_MAIL"
    echo "Install DNS server: $INSTALL_DNS"
    echo ""
    read -p "Continue with installation? [Y/n]: " confirm
    if [[ "$confirm" =~ ^[Nn] ]]; then
        log "Installation cancelled by user"
        exit 0
    fi
fi

# Save configuration
mkdir -p /etc/mrm-webpanel
cat > /etc/mrm-webpanel/installer.conf <<EOF
HOSTNAME=$HOSTNAME
DB_ROOT_PASS=$DB_ROOT_PASS
DB_PANEL_USER=$DB_PANEL_USER
DB_PANEL_PASS=$DB_PANEL_PASS
DB_NAME=$DB_NAME
DB_USER=root
DB_PASS=$DB_ROOT_PASS
DB_USER=root
DB_PASS=$DB_ROOT_PASS
INSTALL_MAIL=$INSTALL_MAIL
INSTALL_DNS=$INSTALL_DNS
INSTALL_DATE=$(date +'%Y-%m-%d %H:%M:%S')
EOF
chmod 600 /etc/mrm-webpanel/installer.conf

log "Configuration saved to /etc/mrm-webpanel/installer.conf"

# Pre-flight checks
log_info "Running pre-flight checks..."

# Check OS
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        log_warn "This installer is designed for Ubuntu/Debian. Your OS: $ID"
        read -p "Continue anyway? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[Yy] ]]; then
            exit 1
        fi
    fi
    log "Detected OS: $PRETTY_NAME"
else
    log_warn "Cannot detect OS version"
fi

# Check internet connectivity
if ! ping -c 1 8.8.8.8 &> /dev/null; then
    log_error "No internet connectivity detected"
    exit 1
fi
log "Internet connectivity: OK"

# Fix APT sources - remove CD-ROM entries that block updates
log_info "Checking APT sources configuration..."
if grep -q "^deb cdrom:" /etc/apt/sources.list 2>/dev/null; then
    log "Found CD-ROM entries in sources.list, removing them..."
    cp /etc/apt/sources.list /etc/apt/sources.list.bak
    sed -i '/^deb cdrom:/s/^/# /' /etc/apt/sources.list
    log "CD-ROM entries commented out, backup saved to sources.list.bak"
fi

# Ensure we have online Debian repositories
if ! grep -q "^deb.*debian.org" /etc/apt/sources.list 2>/dev/null; then
    log "Adding Debian online repositories..."
    cat >> /etc/apt/sources.list <<'EOF'

# Debian online repositories (added by MRM installer)
deb http://deb.debian.org/debian/ trixie main contrib non-free non-free-firmware
deb http://deb.debian.org/debian/ trixie-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware
EOF
    log "Debian online repositories added"
fi

# Update system packages
log_info "Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update >> "$LOG_FILE" 2>&1 || {
    log_error "Failed to update package lists"
    exit 1
}
log "Package lists updated"

# Install core system packages
log_info "Installing core system packages (this may take several minutes)..."

CORE_PACKAGES=(
    "nginx"
    "docker.io"
    "docker-compose"
    "mariadb-server"
    "mariadb-client"
    "python3"
    "python3-full"
    "python3-venv"
    "python3-pip"
    "curl"
    "wget"
    "git"
    "gnupg"
    "jq"
    "certbot"
    "python3-certbot-nginx"
    "fail2ban"
    "ufw"
)

apt-get install -y "${CORE_PACKAGES[@]}" >> "$LOG_FILE" 2>&1 || {
    log_error "Failed to install core packages"
    exit 1
}
log "Core packages installed successfully"

# Install mail server packages
if [[ "$INSTALL_MAIL" == "yes" ]]; then
    log_info "Installing mail server packages..."
    
    MAIL_PACKAGES=(
        "postfix"
        "postfix-mysql"
        "dovecot-core"
        "dovecot-imapd"
        "dovecot-pop3d"
        "dovecot-mysql"
        "opendkim"
        "opendkim-tools"
    )
    
    # Pre-configure Postfix for non-interactive install
    echo "postfix postfix/main_mailer_type select Internet Site" | debconf-set-selections
    echo "postfix postfix/mailname string $HOSTNAME" | debconf-set-selections
    
    apt-get install -y "${MAIL_PACKAGES[@]}" >> "$LOG_FILE" 2>&1 || {
        log_error "Failed to install mail packages"
        exit 1
    }
    log "Mail server packages installed successfully"
fi

# Install DNS server packages
if [[ "$INSTALL_DNS" == "yes" ]]; then
    log_info "Installing DNS server packages..."
    
    DNS_PACKAGES=(
        "bind9"
        "bind9-utils"
        "dnsutils"
    )
    
    apt-get install -y "${DNS_PACKAGES[@]}" >> "$LOG_FILE" 2>&1 || {
        log_error "Failed to install DNS packages"
        exit 1
    }
    log "DNS server packages installed successfully"
fi

# Create system users
log_info "Creating system users..."

# Create vmail user for virtual mail
if ! id -u vmail &>/dev/null; then
    groupadd -g 5000 vmail 2>/dev/null || true
    useradd -r -u 5000 -g vmail -s /usr/sbin/nologin -d /var/mail/vmail -m vmail
    log "Created vmail user (uid:gid 5000:5000)"
fi

# Create SFTP users group
if ! getent group sftpusers &>/dev/null; then
    groupadd sftpusers
    log "Created sftpusers group"
fi

# Create directory structure
log_info "Creating directory structure..."

mkdir -p /etc/mrm-webpanel/{templates,plugins}
mkdir -p /srv/mrm/sites
mkdir -p /var/log/mrm-webpanel
mkdir -p /var/www/certbot
mkdir -p /var/mail/vmail
mkdir -p /etc/nginx/sites-{available,enabled}
mkdir -p /srv/mrm/templates/{node/node18,python/python311,php/php82}
mkdir -p /srv/mrm/templates/{node/node18,python/python311,php/php82}

if [[ "$INSTALL_DNS" == "yes" ]]; then
    mkdir -p /etc/bind/zones
    chown root:bind /etc/bind/zones
    chmod 755 /etc/bind/zones
fi

if [[ "$INSTALL_MAIL" == "yes" ]]; then
    mkdir -p /etc/opendkim/keys
    chown -R opendkim:opendkim /etc/opendkim/keys
    chmod 700 /etc/opendkim/keys
fi

chown vmail:vmail /var/mail/vmail
chmod 770 /var/mail/vmail

# Create template markers for runtime auto-detection
touch /srv/mrm/templates/node/node18/.mrm-template
touch /srv/mrm/templates/python/python311/.mrm-template
touch /srv/mrm/templates/php/php82/.mrm-template

# Create template markers for runtime auto-detection
touch /srv/mrm/templates/node/node18/.mrm-template
touch /srv/mrm/templates/python/python311/.mrm-template
touch /srv/mrm/templates/php/php82/.mrm-template

log "Directory structure created"

# Configure MariaDB
log_info "Configuring MariaDB..."

# Start MariaDB if not running
systemctl start mariadb

# Set root password (works for both first-time and existing)
mariadb -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$DB_ROOT_PASS'; FLUSH PRIVILEGES;" 2>/dev/null || \
    mariadb -u root -p"$DB_ROOT_PASS" -e "SELECT 1" &>/dev/null || {
    log_error "Failed to set MariaDB root password"
    exit 1
}

# Create panel database
mariadb -u root -p"$DB_ROOT_PASS" -e "CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" || {
    log_error "Failed to create database"
    exit 1
}

# Import schema
if [[ -f "$INSTALL_DIR/sql/init.sql" ]]; then
    mariadb -u root -p"$DB_ROOT_PASS" "$DB_NAME" < "$INSTALL_DIR/sql/init.sql" || {
        log_error "Failed to import database schema"
        exit 1
    }
    log "Database schema imported"
else
    log_error "SQL schema file not found: $INSTALL_DIR/sql/init.sql"
    exit 1
fi

# Create panel database user
mariadb -u root -p"$DB_ROOT_PASS" -e "CREATE USER IF NOT EXISTS '$DB_PANEL_USER'@'localhost' IDENTIFIED BY '$DB_PANEL_PASS';" || true
mariadb -u root -p"$DB_ROOT_PASS" -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_PANEL_USER'@'localhost'; FLUSH PRIVILEGES;" || {
    log_error "Failed to create database user"
    exit 1
}

log "MariaDB configured successfully"

# Copy templates
log_info "Installing templates..."
if [[ -d "$INSTALL_DIR/templates" ]]; then
    cp -r "$INSTALL_DIR/templates/"* /etc/mrm-webpanel/templates/
    chmod 644 /etc/mrm-webpanel/templates/*
    log "Templates installed to /etc/mrm-webpanel/templates/"
else
    log_error "Templates directory not found: $INSTALL_DIR/templates"
    exit 1
fi

# Copy panel application
log_info "Installing panel application..."
if [[ -d "$INSTALL_DIR/panel" ]]; then
    # Remove existing panel directory if present
    rm -rf /root/panel
    cp -r "$INSTALL_DIR/panel" /root/panel
    log "Panel application installed to /root/panel/"
else
    log_error "Panel directory not found: $INSTALL_DIR/panel"
    exit 1
fi

# Install Python dependencies
log_info "Installing Python dependencies..."
if [[ -f /root/panel/requirements.txt ]]; then
    cd /root/panel
    python3 -m venv /root/.venv-mrm >> "$LOG_FILE" 2>&1 || {
        log_error "Failed to create Python virtual environment"
        exit 1
    }
    source /root/.venv-mrm/bin/activate
    pip install --upgrade pip >> "$LOG_FILE" 2>&1
    pip install -r requirements.txt >> "$LOG_FILE" 2>&1 || {
        log_error "Failed to install Python dependencies"
        exit 1
    }
    deactivate
    log "Python dependencies installed"
else
    log_error "requirements.txt not found"
    exit 1
fi

# Create systemd service
log_info "Creating systemd service..."
cat > /etc/systemd/system/mrm-webpanel.service <<'EOFS'
[Unit]
Description=MRM Webpanel - Hosting Control Center
After=network.target mariadb.service docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/panel
EnvironmentFile=/etc/mrm-webpanel/installer.conf
ExecStart=/root/.venv-mrm/bin/python -u /root/panel/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFS

systemctl daemon-reload
log "Systemd service created"

# Configure Nginx
log_info "Configuring Nginx..."

# Create panel reverse proxy config
cat > /etc/nginx/sites-available/mrm-panel.conf <<'EOFN'
upstream mrm_panel {
    server 127.0.0.1:5000;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    
    # Disable default access logging for panel
    access_log /var/log/nginx/mrm-panel-access.log;
    error_log /var/log/nginx/mrm-panel-error.log;
    
    location / {
        proxy_pass http://mrm_panel;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Let's Encrypt challenge directory
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
}
EOFN

# Enable panel config
ln -sf /etc/nginx/sites-available/mrm-panel.conf /etc/nginx/sites-enabled/

# Remove default nginx site
rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
nginx -t >> "$LOG_FILE" 2>&1 || {
    log_error "Nginx configuration test failed"
    exit 1
}

log "Nginx configured successfully"

# Configure Docker
log_info "Configuring Docker..."
systemctl enable docker >> "$LOG_FILE" 2>&1
systemctl start docker
log "Docker enabled and started"

# Configure Postfix (if mail enabled)
if [[ "$INSTALL_MAIL" == "yes" ]]; then
    log_info "Configuring Postfix..."
    
    # Configure Postfix main settings
    postconf -e "myhostname = $HOSTNAME"
    postconf -e "mydomain = $HOSTNAME"
    postconf -e "mydestination = localhost"
    postconf -e "mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128"
    postconf -e "virtual_mailbox_domains = mysql:/etc/postfix/mysql-virtual-mailbox-domains.cf"
    postconf -e "virtual_mailbox_maps = mysql:/etc/postfix/mysql-virtual-mailbox-maps.cf"
    postconf -e "virtual_alias_maps = mysql:/etc/postfix/mysql-virtual-alias-maps.cf"
    postconf -e "virtual_mailbox_base = /var/mail/vmail"
    postconf -e "virtual_uid_maps = static:5000"
    postconf -e "virtual_gid_maps = static:5000"
    postconf -e "smtpd_milters = inet:127.0.0.1:12301"
    postconf -e "non_smtpd_milters = inet:127.0.0.1:12301"
    postconf -e "milter_default_action = accept"
    postconf -e "smtpd_recipient_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination"
    
    # Create MySQL lookup files
    cat > /etc/postfix/mysql-virtual-mailbox-domains.cf <<EOF
user = $DB_PANEL_USER
password = $DB_PANEL_PASS
hosts = 127.0.0.1
dbname = $DB_NAME
query = SELECT 1 FROM mail_domains WHERE domain='%s' AND active=1
EOF
    
    cat > /etc/postfix/mysql-virtual-mailbox-maps.cf <<EOF
user = $DB_PANEL_USER
password = $DB_PANEL_PASS
hosts = 127.0.0.1
dbname = $DB_NAME
query = SELECT CONCAT(domain, '/', email) FROM mail_users WHERE email='%s' AND active=1
EOF
    
    cat > /etc/postfix/mysql-virtual-alias-maps.cf <<EOF
user = $DB_PANEL_USER
password = $DB_PANEL_PASS
hosts = 127.0.0.1
dbname = $DB_NAME
query = SELECT destination FROM mail_aliases WHERE source='%s'
EOF
    
    chmod 640 /etc/postfix/mysql-*.cf
    chown root:postfix /etc/postfix/mysql-*.cf
    
    log "Postfix configured successfully"
    
    # Configure Dovecot
    log_info "Configuring Dovecot..."
    
    cat > /etc/dovecot/conf.d/99-mrm-mysql.conf <<EOF
# MySQL authentication
passdb {
  driver = sql
  args = /etc/dovecot/dovecot-sql.conf.ext
}

userdb {
  driver = static
  args = uid=vmail gid=vmail home=/var/mail/vmail/%d/%n
}

# Mailbox location
mail_location = maildir:/var/mail/vmail/%d/%n

# SASL for Postfix
service auth {
  unix_listener /var/spool/postfix/private/auth {
    mode = 0666
    user = postfix
    group = postfix
  }
}
EOF
    
    cat > /etc/dovecot/dovecot-sql.conf.ext <<EOF
driver = mysql
connect = host=127.0.0.1 dbname=$DB_NAME user=$DB_PANEL_USER password=$DB_PANEL_PASS
default_pass_scheme = SHA512-CRYPT
password_query = SELECT email as user, password FROM mail_users WHERE email='%u' AND active=1
EOF
    
    chmod 600 /etc/dovecot/dovecot-sql.conf.ext
    chown dovecot:dovecot /etc/dovecot/dovecot-sql.conf.ext
    
    log "Dovecot configured successfully"
    
    # Configure OpenDKIM
    log_info "Configuring OpenDKIM..."
    
    cat > /etc/opendkim.conf <<EOF
# Basic settings
Syslog yes
LogWhy yes
UMask 002

# Signing and verification
Domain *
Selector default
KeyFile /etc/opendkim/keys/%domain/default.private
AutoRestart yes
AutoRestartRate 10/1h

# Socket for Postfix
Socket inet:12301@127.0.0.1

# User
UserID opendkim:opendkim

# Additional settings
Canonicalization relaxed/simple
Mode sv
SubDomains yes
EOF
    
    log "OpenDKIM configured successfully"
fi

# Configure Bind9 (if DNS enabled)
if [[ "$INSTALL_DNS" == "yes" ]]; then
    log_info "Configuring Bind9..."
    
    # Create mrm-zones.conf include file
    touch /etc/bind/mrm-zones.conf
    chown root:bind /etc/bind/mrm-zones.conf
    chmod 644 /etc/bind/mrm-zones.conf
    
    # Add include to named.conf.local if not present
    if ! grep -q "mrm-zones.conf" /etc/bind/named.conf.local; then
        echo 'include "/etc/bind/mrm-zones.conf";' >> /etc/bind/named.conf.local
    fi
    
    # Test configuration
    named-checkconf || {
        log_error "Bind9 configuration test failed"
        exit 1
    }
    
    log "Bind9 configured successfully"
fi

# Configure UFW firewall
log_info "Configuring firewall..."

# Enable UFW
ufw --force enable >> "$LOG_FILE" 2>&1

# Set defaults
ufw default deny incoming >> "$LOG_FILE" 2>&1
ufw default allow outgoing >> "$LOG_FILE" 2>&1

# Allow SSH
ufw allow 22/tcp comment 'SSH' >> "$LOG_FILE" 2>&1

# Allow HTTP/HTTPS
ufw allow 80/tcp comment 'HTTP' >> "$LOG_FILE" 2>&1
ufw allow 443/tcp comment 'HTTPS' >> "$LOG_FILE" 2>&1
ufw allow 5000/tcp comment 'Panel' >> "$LOG_FILE" 2>&1
ufw allow 5000/tcp comment 'Panel' >> "$LOG_FILE" 2>&1

# Allow DNS if enabled
if [[ "$INSTALL_DNS" == "yes" ]]; then
    ufw allow 53/tcp comment 'DNS TCP' >> "$LOG_FILE" 2>&1
    ufw allow 53/udp comment 'DNS UDP' >> "$LOG_FILE" 2>&1
fi

# Allow mail ports if enabled
if [[ "$INSTALL_MAIL" == "yes" ]]; then
    ufw allow 25/tcp comment 'SMTP' >> "$LOG_FILE" 2>&1
    ufw allow 587/tcp comment 'Submission' >> "$LOG_FILE" 2>&1
    ufw allow 143/tcp comment 'IMAP' >> "$LOG_FILE" 2>&1
    ufw allow 993/tcp comment 'IMAPS' >> "$LOG_FILE" 2>&1
    ufw allow 110/tcp comment 'POP3' >> "$LOG_FILE" 2>&1
    ufw allow 995/tcp comment 'POP3S' >> "$LOG_FILE" 2>&1
fi

log "Firewall configured successfully"

# Configure Fail2ban
log_info "Configuring Fail2ban..."

cat > /etc/fail2ban/jail.local <<'EOFF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
destemail = root@localhost
sendername = Fail2ban

[sshd]
enabled = true
port = 22
logpath = /var/log/auth.log

[recidive]
enabled = true
logpath = /var/log/fail2ban.log
bantime = 86400
findtime = 86400
maxretry = 3
EOFF

# Add mail jails if enabled
if [[ "$INSTALL_MAIL" == "yes" ]]; then
    cat >> /etc/fail2ban/jail.local <<'EOFF'

[postfix-sasl]
enabled = true
port = smtp,submission
logpath = /var/log/mail.log

[dovecot]
enabled = true
port = pop3,pop3s,imap,imaps
logpath = /var/log/mail.log
EOFF
fi

log "Fail2ban configured successfully"

# Set hostname
log_info "Setting hostname..."
hostnamectl set-hostname "$HOSTNAME"
echo "127.0.0.1 $HOSTNAME" >> /etc/hosts
log "Hostname set to $HOSTNAME"

# Enable and start services
log_info "Enabling and starting services..."

systemctl enable mariadb >> "$LOG_FILE" 2>&1
systemctl start mariadb

systemctl enable docker >> "$LOG_FILE" 2>&1
systemctl start docker

systemctl enable nginx >> "$LOG_FILE" 2>&1
systemctl start nginx

systemctl enable fail2ban >> "$LOG_FILE" 2>&1
systemctl start fail2ban

if [[ "$INSTALL_MAIL" == "yes" ]]; then
    systemctl enable postfix >> "$LOG_FILE" 2>&1
    systemctl start postfix
    
    systemctl enable dovecot >> "$LOG_FILE" 2>&1
    systemctl start dovecot
    
    systemctl enable opendkim >> "$LOG_FILE" 2>&1
    systemctl start opendkim
fi

if [[ "$INSTALL_DNS" == "yes" ]]; then
    # Try to enable bind9, but don't fail if it's a linked unit file
    systemctl enable bind9 >> "$LOG_FILE" 2>&1 || {
        log_warn "Could not enable bind9 (may be a linked unit), checking if already enabled..."
        systemctl is-enabled bind9 &>/dev/null && log "bind9 is already enabled" || log_warn "bind9 enable skipped (service will still start)"
    }
    systemctl restart bind9 || {
        log_error "Failed to restart bind9"
        exit 1
    }
fi

log "System services enabled and started"

# Create root superadmin user
log_info "Creating panel admin user..."
cd /root/panel
source /root/.venv-mrm/bin/activate

# Export database credentials for the panel to use
export DB_USER=root
export DB_PASS="$DB_ROOT_PASS"
export DB_NAME="$DB_NAME"

python3 <<EOPY
import sys
sys.path.insert(0, '/root/panel')
from auth import create_root_superadmin
create_root_superadmin('$ADMIN_PASSWORD')
print("Root superadmin created successfully")
EOPY

if [ $? -ne 0 ]; then
    log_error "Failed to create admin user"
    deactivate
    exit 1
fi

deactivate
log "Panel admin user created"

# Start MRM webpanel service
log_info "Starting MRM webpanel service..."
systemctl enable mrm-webpanel >> "$LOG_FILE" 2>&1
systemctl start mrm-webpanel

# Wait for service to start
sleep 3

if systemctl is-active --quiet mrm-webpanel; then
    log "MRM webpanel service started successfully"
else
    log_error "MRM webpanel service failed to start"
    journalctl -u mrm-webpanel -n 20 | tee -a "$LOG_FILE"
    exit 1
fi

# Final verification
log_info "Running final verification..."

FAILED=0

# Check services
for service in mariadb docker nginx fail2ban mrm-webpanel; do
    if systemctl is-active --quiet "$service"; then
        log "✓ $service is running"
    else
        log_error "✗ $service is NOT running"
        FAILED=1
    fi
done

if [[ "$INSTALL_MAIL" == "yes" ]]; then
    for service in postfix dovecot opendkim; do
        if systemctl is-active --quiet "$service"; then
            log "✓ $service is running"
        else
            log_error "✗ $service is NOT running"
            FAILED=1
        fi
    done
fi

if [[ "$INSTALL_DNS" == "yes" ]]; then
    if systemctl is-active --quiet bind9; then
        log "✓ bind9 is running"
    else
        log_error "✗ bind9 is NOT running"
        FAILED=1
    fi
fi

# Test panel API
if curl -sf http://localhost:5000/ > /dev/null; then
    log "✓ Panel API is responding"
else
    log_error "✗ Panel API is NOT responding"
    FAILED=1
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "[server-ip]")

# Installation complete
echo ""
echo ""
cat <<EOF
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          INSTALLATION COMPLETED SUCCESSFULLY!             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Panel Access:
  URL: http://$SERVER_IP:5000
  or   http://$HOSTNAME:5000
  
  Username: root
  Password: $ADMIN_PASSWORD

Next Steps:
  1. Access the panel at the URL above
  2. Configure SSL with certbot (recommended):
     certbot --nginx -d $HOSTNAME
  3. Change the default admin password in the panel
  4. Create your first domain and deployment
  5. Review the logs: $LOG_FILE

Documentation:
  - See installer/README.md for detailed documentation
  - Run: bash installer/verify.sh to verify installation

Services Status:
  - MRM Panel: http://$HOSTNAME:5000
  - MariaDB: localhost:3306
  - Nginx: ports 80, 443
EOF

if [[ "$INSTALL_MAIL" == "yes" ]]; then
    echo "  - Mail: SMTP(25,587) IMAP(143,993) POP3(110,995)"
fi

if [[ "$INSTALL_DNS" == "yes" ]]; then
    echo "  - DNS: port 53 (TCP/UDP)"
fi

echo ""
log "Installation log saved to: $LOG_FILE"
log "Configuration saved to: /etc/mrm-webpanel/installer.conf"

if [[ $FAILED -eq 1 ]]; then
    echo ""
    log_warn "Some services failed verification. Check the log file for details."
    exit 1
fi

echo ""
log "Thank you for using MRM Webpanel!"
echo ""

exit 0
