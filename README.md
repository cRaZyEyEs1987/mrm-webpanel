# MRM Webpanel — Features & Installation

MRM Webpanel is an early-stage, experimental control panel for hosting containerized web applications.
This README focuses on features and installation instructions only. Use at your own risk.

---

## Quick summary

- Purpose: deploy and manage web applications in isolated Docker containers
- Target runtimes: Node.js, Python, PHP, WordPress
- Core idea: one container per site, Nginx reverse proxy automatically configured
- Status: early development — features and APIs will change

---

## Planned features (high level)

- Multi-runtime deployments: Node.js, Python, PHP, WordPress
- Docker-based per-site isolation and resource separation
- Automatic upstream port allocation and Nginx vhost templating
- Panel application (Flask) providing a web dashboard and REST API
- MariaDB for panel storage and per-site database provisioning
- Optional mail stack: Postfix, Dovecot, DKIM (OpenDKIM)
- Optional authoritative DNS via Bind9 and automated zone generation
- SFTP account provisioning per site for file access
- Basic security integrations: UFW firewall, Fail2ban
- Site lifecycle management: start, stop, restart, deploy, logs
- Templates for Docker Compose per runtime (node, python, php, wordpress)
- Verification scripts to perform basic health checks after install

> Many items are work-in-progress. Expect breaking changes until a stable release.

---

## System requirements (minimum)

- OS: Ubuntu 20.04+ or Debian 11+
- RAM: 2GB (4GB recommended)
- Disk: 20GB (SSD recommended)
- CPU: 1 core (2+ recommended)
- Root or sudo access is required to run the installer
- Public IP and DNS name recommended for TLS/Let's Encrypt

---

## Quick interactive install

1. Upload the installer package to your server.
2. Extract and run the installer:

```bash
tar -xzf mrm-webpanel-installer-*.tar.gz
cd installer
sudo bash install.sh
```

3. During interactive install you will be prompted for:

- Hostname / FQDN for the panel
- MariaDB root password (or a generated value)
- Panel admin password
- Whether to install mail components
- Whether to install DNS components

The installer will show progress and output. Save any generated credentials.

---

## Unattended install example

Use unattended mode for automation or testing. Replace placeholder values.

```bash
sudo bash install.sh \
	--hostname panel.example.com \
	--db-pass "YourDBPassHere" \
	--admin-pass "YourAdminPass" \
	--unattended
```

Optional flags:

- `--skip-mail` — skip mail server installation
- `--skip-dns` — skip DNS server installation
- `--no-firewall` — (not recommended) do not alter UFW rules

---

## Basic post-install checks

Run these on the server after installation finishes:

```bash
sudo systemctl status mrm-webpanel
curl -fsS http://127.0.0.1:5000/ || echo "panel not responding"
mariadb -u root -p -e "SHOW DATABASES;" || echo "db error"
```

Check logs:

```bash
sudo journalctl -u mrm-webpanel -f
tail -n 200 /var/log/mrm-installer.log
```

---

## Directory layout (created by installer)

- `/root/panel/` — panel application code
- `/etc/mrm-webpanel/` — templates and configuration
- `/srv/mrm/sites/` — per-site compose files and site data
- `/var/mail/vmail/` — virtual mailboxes (if mail installed)
- `/etc/bind/zones/` — DNS zone files (if DNS installed)

---

## How the panel serves sites

1. For each site a Docker Compose file is created under `/srv/mrm/sites/<domain>/`.
2. The panel assigns an upstream port (e.g. 3001, 3002...) and writes an Nginx vhost using templates.
3. Nginx proxies incoming traffic for the domain to the site's container port.
4. SSL/TLS can be enabled via Let's Encrypt (manual or automated by the installer in future).

---

## Planned runtimes & templates

- Node.js: `node:18-alpine` with `npm install` and `npm start`
- Python: `python:3.11-alpine`, expects an app listening on `PORT`
- PHP: `php:8.2-fpm-alpine` + Nginx/Php-FPM
- WordPress: official WordPress image with MySQL integration

Template variables include: `{{DOMAIN}}`, `{{SITE_DIR}}`, `{{UPSTREAM_PORT}}`, `{{CONTAINER_PORT}}`, `{{DOCKER_IMAGE}}`.

---

## Mail and DNS (optional components)

- Mail: Postfix for SMTP, Dovecot for IMAP/POP3, OpenDKIM for signing. Virtual mailbox storage under `/var/mail/vmail/`.
- DNS: Bind9 runs authoritative zones for hosted domains and writes zone files into `/etc/bind/zones/`.

These components require careful network and DNS configuration; they are optional and can be skipped.

---

## Security notes

- This software is experimental. Do not run on production systems without auditing and backups.
- Use strong passwords and rotate credentials regularly.
- Limit remote access (SSH) and prefer key-based authentication.
- Review firewall rules after install: `sudo ufw status verbose`.

---

## License

MRM Webpanel is offered under the MIT License. See `LICENSE` for details.



