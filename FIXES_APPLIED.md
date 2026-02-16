# MRM Webpanel Installer - Fixes Applied

## Date: 2026-02-15

### Issues Fixed

#### 1. Missing Python Virtual Environment Configuration
**Problem**: Panel failed to start because Flask and dependencies weren't installed
**Fix**: 
- Systemd service now uses `/root/.venv-mrm/bin/python` instead of system Python
- Virtual environment is created and dependencies installed during installation

#### 2. Missing Database Credentials in Environment
**Problem**: Panel couldn't connect to MariaDB (Access denied error)
**Fix**:
- Added `DB_USER=root` and `DB_PASS=$DB_ROOT_PASS` to installer.conf
- Systemd service loads `EnvironmentFile=/etc/mrm-webpanel/installer.conf`

#### 3. Missing Template Version Detection
**Problem**: No runtime versions appeared in domain creation dropdown
**Fix**:
- Installer creates template marker directories:
  - `/srv/mrm/templates/node/node18/.mrm-template`
  - `/srv/mrm/templates/python/python311/.mrm-template`
  - `/srv/mrm/templates/php/php82/.mrm-template`

#### 4. Port 5000 Not Accessible
**Problem**: Panel port 5000 blocked by UFW firewall
**Fix**: 
- Added `ufw allow 5000/tcp` to installer

#### 5. 502 Bad Gateway on First Deployment
**Problem**: Nginx tried to proxy before container was ready
**Fix**:
- Added `wait_for_container_health()` method to DockerEngine
- Deploy sequence now:
  1. Start container
  2. Wait for container health (polls port for 60s)
  3. Generate nginx config
  4. Reload nginx

### Files Modified

- `/root/installer/install.sh` - Main installer script
- `/root/installer/panel/engines/docker_engine.py` - Container health checks

### Verification

Run a clean install and:
1. Panel should start without errors
2. Access http://SERVER_IP:5000/
3. Login with username `root` and admin password
4. Create domain with runtime selection (node18/python311/php82 visible)
5. Deploy - should work on first try without 502 error

### Clean Install Command

```bash
cd /root/installer
bash install.sh --unattended
```

Or interactive:
```bash
cd /root/installer
bash install.sh
```
