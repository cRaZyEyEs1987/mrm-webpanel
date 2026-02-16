tar -xzf mrm-webpanel-installer-*.tar.gz
# MRM Webpanel — Early Development

MRM Webpanel is an early-stage control panel for hosting containerized web apps. This project is experimental and not production ready — use at your own risk.

Planned features:
- Multi-runtime deployments (Node.js, Python, PHP, WordPress)
- Docker per-site isolation with managed upstream ports
- Nginx reverse proxy with automatic configuration
- MariaDB-backed panel storage
- Optional mail (Postfix/Dovecot) and DNS (Bind9)

Minimal install (developer): Ubuntu 20.04+/Debian 11+, root access, 2GB+ RAM.

Interactive:
```
tar -xzf mrm-webpanel-installer-*.tar.gz
cd installer
sudo bash install.sh
```

Unattended example:
```
sudo bash install.sh --hostname panel.example.com --db-pass "DBPASS" --admin-pass "ADMINPASS" --unattended
```

License: MIT — see `LICENSE`.

Secure your panel with Let's Encrypt:

```bash
# Make sure your domain points to this server first
sudo certbot --nginx -d panel.example.com

# Certbot will automatically configure Nginx for HTTPS
```

### 3. Change Default Password

1. Log in to the panel
2. Navigate to your profile/settings
3. Change the admin password immediately

### 4. Configure Hostname

If you didn't set a proper hostname during installation:

```bash
sudo hostnamectl set-hostname panel.example.com
echo "127.0.0.1 panel.example.com" | sudo tee -a /etc/hosts
```

### 5. Configure DNS (if DNS server installed)

Point your nameservers to this server:

```
ns1.yourdomain.com → [your-server-ip]
ns2.yourdomain.com → [your-server-ip]
```

Then at your domain registrar, set nameservers to:
```
ns1.yourdomain.com
ns2.yourdomain.com
```

## Architecture

### Directory Structure

```
/root/panel/                    # Panel application code
├── app.py                      # Main Flask application
├── auth.py                     # Authentication/authorization
├── db.py                       # Database abstraction
├── engines/docker_engine.py    # Docker orchestration
├── dns/bind9_manager.py        # DNS management
└── sftp/sftp_manager.py        # SFTP account management

/etc/mrm-webpanel/              # Panel configuration
├── templates/                  # Docker Compose & Nginx templates
│   ├── docker-compose.node.tpl
│   ├── docker-compose.python.tpl
│   ├── docker-compose.php.tpl
│   ├── docker-compose.wordpress.tpl
│   └── nginx_vhost.conf.tpl
├── plugins/                    # Plugin directory (future)
└── installer.conf              # Installation configuration

/srv/mrm/sites/                 # Site deployments
├── domain1.com/
│   ├── compose.yml             # Docker Compose file
│   └── data/                   # Application files
└── domain2.com/
    ├── compose.yml
    └── data/

/var/mail/vmail/                # Virtual mailboxes
└── domain.com/
    └── user@domain.com/

/etc/bind/zones/                # DNS zone files
├── domain1.com.zone
└── domain2.com.zone
```

### Network Architecture

```
Internet → Nginx (ports 80, 443)
              ↓
        Panel API (:5000)
              ↓
    Docker Engine → Containers
                    (ports 3001-4000)
```

- **Panel**: Flask app on port 5000 (proxied by Nginx)
- **Containers**: Each site gets a unique port (3000 + site_id)
- **Nginx**: Reverse proxies to container upstreams

### Services Overview

| Service | Port(s) | Purpose |
|---------|---------|---------|
| Nginx | 80, 443 | Web server & reverse proxy |
| MRM Panel | 5000 | Control panel API |
| MariaDB | 3306 | Database (local only) |
| Docker Containers | 3001-4000 | Site applications |
| Postfix | 25, 587 | SMTP mail server |
| Dovecot | 143, 993, 110, 995 | IMAP/POP3 |
| Bind9 | 53 | DNS server |

## Using the Panel

### 1. Create a Domain

1. Log in to the panel
2. Navigate to "Domains"
3. Click "Add Domain"
4. Enter domain name (e.g., `mysite.com`)
5. Choose runtime (Node.js, Python, PHP, or WordPress)

### 2. Deploy Application

**For Node.js:**
- Upload your code to `/srv/mrm/sites/mysite.com/data/`
- Ensure `package.json` exists
- Create `server.js` or specify entry point
- Container will run `npm install && npm start`
- Your app should listen on `process.env.PORT`

**For Python:**
- Upload code to site directory
- Ensure `requirements.txt` exists (if needed)
- Create `app.py` with your Flask/FastAPI/etc app
- Your app should listen on `os.getenv('PORT')`

**For PHP:**
- Upload PHP files to site directory
- Use `index.php` as entry point
- PHP-FPM will serve files automatically

**For WordPress:**
- Container starts with WordPress pre-installed
- Configure database through panel (future feature)
- Access site to complete WordPress setup

### 3. Configure Nginx & SSL

The panel automatically:
- Creates Nginx virtual host configuration
- Sets up reverse proxy to container
- Configures upstream port

For SSL, run manually:
```bash
sudo certbot --nginx -d mysite.com -d www.mysite.com
```

### 4. Manage Services

Through the panel API or dashboard:
- Start/Stop containers
- View logs
- Restart services
- Update deployments

## API Usage

The panel provides a REST API for automation.

### Authentication

```bash
# Login to get JWT token
curl -X POST http://panel.example.com:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"root","password":"your-password"}'

# Response: {"token": "eyJ0eXAi..."}
```

### Example API Calls

**Create a domain:**
```bash
curl -X POST http://panel.example.com:5000/api/domains \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domain":"newsite.com","runtime":"node18"}'
```

**List domains:**
```bash
curl http://panel.example.com:5000/api/domains \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Deploy site:**
```bash
curl -X POST http://panel.example.com:5000/api/sites \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domain_id":1,"runtime":"node18","version":"node:18-alpine"}'
```

See `API_REFERENCE.md` in the main project for full API documentation.

## Troubleshooting

### Panel Not Accessible

**Check service status:**
```bash
sudo systemctl status mrm-webpanel
```

**View logs:**
```bash
sudo journalctl -u mrm-webpanel -f
```

**Restart panel:**
```bash
sudo systemctl restart mrm-webpanel
```

### Database Connection Errors

**Test database:**
```bash
mariadb -u mrm -p -e "USE mrm_panel; SHOW TABLES;"
# Password: mrm_password (or what you set)
```

**Check credentials in:**
```bash
cat /etc/mrm-webpanel/installer.conf
```

### Container Won't Start

**Check Docker logs:**
```bash
cd /srv/mrm/sites/domain.com/
sudo docker compose logs -f
```

**Verify compose file:**
```bash
cat /srv/mrm/sites/domain.com/compose.yml
```

**Restart container:**
```bash
cd /srv/mrm/sites/domain.com/
sudo docker compose down
sudo docker compose up -d
```

### Nginx 502 Bad Gateway

**Causes:**
1. Container not running
2. Wrong upstream port
3. Application not listening on correct port

**Debug:**
```bash
# Check container status
sudo docker ps | grep domain.com

# Check nginx config
cat /etc/nginx/sites-available/domain.com.conf

# Test upstream port
curl http://localhost:3001  # or whatever port
```

### Firewall Blocking Connections

**Check UFW status:**
```bash
sudo ufw status verbose
```

**Allow additional ports:**
```bash
sudo ufw allow 8080/tcp
```

### Mail Not Working

**Check Postfix:**
```bash
sudo postfix check
sudo systemctl status postfix
```

**Test mail sending:**
```bash
echo "Test" | mail -s "Test Subject" user@example.com
tail -f /var/log/mail.log
```

**Check Dovecot:**
```bash
sudo systemctl status dovecot
sudo doveadm auth test user@domain.com password
```

### DNS Not Resolving

**Check Bind9:**
```bash
sudo named-checkconf
sudo systemctl status bind9
```

**Test DNS query:**
```bash
dig @localhost domain.com
dig @[your-server-ip] domain.com
```

## Maintenance

### Backup

**Database:**
```bash
mysqldump -u root -p mrm_panel > mrm_panel_backup.sql
```

**Sites:**
```bash
tar -czf sites_backup.tar.gz /srv/mrm/sites/
```

**Configuration:**
```bash
tar -czf config_backup.tar.gz /etc/mrm-webpanel/ /root/panel/
```

### Updates

**Update system packages:**
```bash
sudo apt update && sudo apt upgrade -y
```

**Update panel code:**
```bash
cd /root/panel/
git pull  # if using git
sudo systemctl restart mrm-webpanel
```

**Update Docker images:**
```bash
# For each site
cd /srv/mrm/sites/domain.com/
sudo docker compose pull
sudo docker compose up -d
```

### Logs

| Component | Log Location |
|-----------|-------------|
| Installation | `/var/log/mrm-installer.log` |
| Panel | `journalctl -u mrm-webpanel` |
| Nginx | `/var/log/nginx/` |
| Mail | `/var/log/mail.log` |
| Bind9 | `journalctl -u bind9` |
| Docker | `docker compose logs` (per site) |

## Upgrading

To upgrade an existing installation:

1. **Backup everything** (see Maintenance section)
2. Extract new installer package
3. Copy updated files:
   ```bash
   cp -r installer/panel/* /root/panel/
   cp -r installer/templates/* /etc/mrm-webpanel/templates/
   ```
4. Update Python dependencies:
   ```bash
   source /root/.venv-mrm/bin/activate
   pip install -r /root/panel/requirements.txt
   deactivate
   ```
5. Restart panel:
   ```bash
   sudo systemctl restart mrm-webpanel
   ```

## Uninstall

To completely remove MRM Webpanel:

```bash
# Stop and disable services
sudo systemctl stop mrm-webpanel
sudo systemctl disable mrm-webpanel
sudo rm /etc/systemd/system/mrm-webpanel.service

# Remove panel files
sudo rm -rf /root/panel
sudo rm -rf /etc/mrm-webpanel
sudo rm -rf /srv/mrm

# Remove databases
sudo mariadb -u root -p -e "DROP DATABASE mrm_panel;"

# Optionally remove system packages
sudo apt remove --purge nginx docker.io mariadb-server postfix dovecot bind9
sudo apt autoremove -y

# Clean up
sudo rm -rf /var/mail/vmail
sudo userdel -r vmail
```

## Security Best Practices

1. **Change default passwords immediately**
2. **Use SSL/TLS** with Let's Encrypt
3. **Keep system updated**: `apt update && apt upgrade`
4. **Use strong passwords** for database and admin accounts
5. **Configure fail2ban** properly (already done by installer)
6. **Limit SSH access** to key-based authentication
7. **Regular backups** of database and sites
8. **Monitor logs** for suspicious activity
9. **Use DKIM/SPF/DMARC** for email sending
10. **Firewall rules**: Only open necessary ports

## Support & Documentation

- **Installation Issues**: Check `/var/log/mrm-installer.log`
- **Panel Issues**: Run `sudo journalctl -u mrm-webpanel -f`
- **Verification**: Run `sudo bash verify.sh`
- **API Reference**: See `API_REFERENCE.md` in project root
- **Project Status**: See `PROJECT_STATUS.txt` for current state

## Technical Details

### Database Schema

The panel uses MariaDB with the following main tables:
- `users` - Panel users and roles
- `domains` - Customer domains
- `sites` - Application deployments
- `mail_domains`, `mail_users`, `mail_aliases` - Virtual mail
- `dns_zones`, `dns_records` - DNS management
- `databases`, `database_users` - Per-site databases
- `sftp_accounts` - SFTP access control

### Runtime Versions

| Runtime | Version | Docker Image |
|---------|---------|--------------|
| Node.js | 18 | `node:18-alpine` |
| Python | 3.11 | `python:3.11-alpine` |
| PHP | 8.2 | `php:8.2-fpm-alpine` |
| WordPress | Latest | `wordpress:php8.2-apache` |

### Port Allocation

- **Panel**: 5000 (fixed)
- **Sites**: 3001-4000 (dynamic, calculated as 3000 + site_id)
- Each site gets a unique upstream port for Nginx proxy

### Template System

Templates use placeholder substitution:
- `{{DOMAIN}}` - Site domain name
- `{{SITE_DIR}}` - Full path to site data directory
- `{{DOCKER_IMAGE}}` - Docker image to use
- `{{UPSTREAM_PORT}}` - Nginx upstream port (3000+site_id)
- `{{CONTAINER_PORT}}` - Port container listens on internally

## License

MIT

---

**Installation Date**: Check `/etc/mrm-webpanel/installer.conf`  
**Installer Version**: 1.0.0  
**Last Updated**: February 2026
