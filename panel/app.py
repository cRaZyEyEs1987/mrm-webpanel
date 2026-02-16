from flask import Flask, request, jsonify, render_template_string
import os
import json
import logging
from datetime import datetime
from functools import wraps
import re

# Import panel modules
from db import fetch_one, fetch_all, insert, update, delete, execute_query
from auth import (
    hash_password, verify_password, create_jwt_token, verify_jwt_token,
    token_required, admin_required, superadmin_required, authenticate_user, create_root_superadmin
)
from rbac import RBAC
import threading

# Phase 3: Docker engine
try:
    from engines.docker_engine import DockerEngine
except ImportError:
    DockerEngine = None

# Phase 4: Bind9 DNS
try:
    from dns.bind9_manager import Bind9Manager
except ImportError:
    Bind9Manager = None

# SFTP management
try:
    from sftp.sftp_manager import SFTPManager
except ImportError:
    SFTPManager = None

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SITES_DIR = os.environ.get('SITES_DIR', '/srv/mrm/sites')

# Global storage for active deployment engines (for log streaming)
active_deployments = {}

DEFAULT_VERSIONS = {
    'node': 'node18',
    'python': 'python311',
    'php': 'php82',
}

# ============== Database Migrations ==============
def ensure_database_schema():
    """Ensure all required columns exist in database tables."""
    try:
        # Check if version column exists in domains table
        result = fetch_one(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='domains' AND COLUMN_NAME='version'"
        )
        if not result:
            logger.info("Adding 'version' column to domains table...")
            execute_query("ALTER TABLE domains ADD COLUMN version VARCHAR(50) DEFAULT 'node18'")
            logger.info("Successfully added 'version' column to domains table")
    except Exception as e:
        logger.warning(f"Could not add version column (may already exist): {e}")

    # Ensure settings JSON column exists in domains table
    try:
        result = fetch_one(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='domains' AND COLUMN_NAME='settings_json'"
        )
        if not result:
            logger.info("Adding 'settings_json' column to domains table...")
            execute_query("ALTER TABLE domains ADD COLUMN settings_json TEXT NULL")
            logger.info("Successfully added 'settings_json' column to domains table")
    except Exception as e:
        logger.warning(f"Could not add settings_json column (may already exist): {e}")
    
    # Ensure SFTP columns exist in domains table
    try:
        result = fetch_one(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='domains' AND COLUMN_NAME='sftp_username'"
        )
        if not result:
            logger.info("Adding SFTP columns to domains table...")
            execute_query("ALTER TABLE domains ADD COLUMN sftp_username VARCHAR(255) DEFAULT NULL")
            execute_query("ALTER TABLE domains ADD COLUMN sftp_password VARCHAR(255) DEFAULT NULL")
            logger.info("Successfully added SFTP columns to domains table")
    except Exception as e:
        logger.warning(f"Could not add SFTP columns (may already exist): {e}")
    
    # Ensure sites table has deploy_error column and supports additional statuses
    try:
        result = fetch_one(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='sites' AND COLUMN_NAME='deploy_error'"
        )
        if not result:
            logger.info("Adding 'deploy_error' column to sites table...")
            execute_query("ALTER TABLE sites ADD COLUMN deploy_error TEXT NULL")
            logger.info("Added 'deploy_error' column to sites table")
    except Exception as e:
        logger.warning(f"Could not add deploy_error column: {e}")

    # Ensure sites.status enum contains deploying and failed values
    try:
        # Modify the enum to include deploying and failed; safe if already present
        execute_query("ALTER TABLE sites MODIFY status ENUM('active','stopped','error','deploying','failed') DEFAULT 'active'")
        logger.info("Ensured sites.status enum includes deploying and failed")
    except Exception as e:
        logger.warning(f"Could not modify sites.status enum: {e}")

# ============== HTML Templates ==============

HOME_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MRM Webpanel - Hosting Control Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 10px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 600px;
            width: 100%;
            padding: 40px;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 32px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }
        .features {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
        }
        .features h3 {
            color: #333;
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 15px;
        }
        .feature-list {
            list-style: none;
        }
        .feature-list li {
            color: #555;
            padding: 8px 0;
            font-size: 14px;
            display: flex;
            align-items: center;
        }
        .feature-list li:before {
            content: "✓";
            color: #667eea;
            font-weight: bold;
            margin-right: 10px;
            font-size: 18px;
        }
        .button-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        button, a.btn {
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s;
            font-weight: 600;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
            border: 1px solid #ddd;
        }
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        .status {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            font-size: 14px;
            color: #2e7d32;
        }
        .code {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            overflow-x: auto;
            margin: 10px 0;
            border-left: 3px solid #667eea;
        }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 MRM Webpanel</h1>
        <p class="subtitle">Modern Hosting Control Panel for Debian 13</p>
        
        <div class="status">
            ✅ API Server Running • Version 1.0.0 • MariaDB Connected
        </div>
        
        <div class="features">
            <h3>Features</h3>
            <ul class="feature-list">
                <li>Per-domain Docker runtimes (PHP | Python | Node)</li>
                <li>Authoritative DNS with DKIM/SPF/DMARC</li>
                <li>Virtual mail users (Postfix + Dovecot)</li>
                <li>SFTP chroot for secure file uploads</li>
                <li>Role-based access control (RBAC)</li>
                <li>Let's Encrypt SSL/TLS automation</li>
            </ul>
        </div>
        
        <div class="button-group">
            <button class="btn-primary" onclick="showLogin()">📝 Login</button>
            <a href="/docs" class="btn-secondary">📚 Documentation</a>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: #fafafa; border-radius: 5px; display: none;" id="loginForm">
            <h3 style="margin-bottom: 15px; color: #333;">Login</h3>
            <input type="text" id="username" placeholder="Username" style="width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px;">
            <input type="password" id="password" placeholder="Password" style="width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px;">
            <button onclick="login()" class="btn-primary" style="width: 100%;">Login</button>
            <p id="loginResult" style="margin-top: 10px; font-size: 12px; color: #666;"></p>
        </div>
        
        <div class="footer">
            <p>MRM Webpanel • API Docs at <code style="background: #f0f0f0; padding: 2px 4px; border-radius: 2px;">/docs</code> • Source on GitHub</p>
        </div>
    </div>
    
    <script>
        function showLogin() {
            document.getElementById('loginForm').style.display = 'block';
            document.getElementById('username').focus();
        }
        
        function login() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const resultEl = document.getElementById('loginResult');
            
            if (!username || !password) {
                resultEl.textContent = '❌ Please enter username and password';
                resultEl.style.color = '#d32f2f';
                return;
            }
            
            fetch('/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username, password})
            })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    resultEl.textContent = '✅ Login successful! Redirecting to dashboard...';
                    resultEl.style.color = '#4caf50';
                    localStorage.setItem('token', data.token);
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 500);
                } else {
                    resultEl.textContent = '❌ ' + (data.error || 'Login failed');
                    resultEl.style.color = '#d32f2f';
                }
            })
            .catch(e => {
                resultEl.textContent = '❌ Error: ' + e.message;
                resultEl.style.color = '#d32f2f';
            });
        }
        
        document.getElementById('password').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') login();
        });
    </script>
</body>
</html>
"""

DOCS_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation - MRM Webpanel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 40px;
        }
        h1 { color: #667eea; margin-bottom: 20px; }
        h2 { color: #555; margin: 30px 0 15px 0; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        h3 { color: #666; margin: 20px 0 10px 0; font-weight: 600; }
        a { color: #667eea; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .endpoint {
            background: #f9f9f9;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
            font-family: monospace;
            font-size: 13px;
        }
        .method {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-weight: bold;
            margin-right: 10px;
            font-size: 12px;
        }
        .post { background: #4caf50; color: white; }
        .get { background: #2196F3; color: white; }
        .put { background: #ff9800; color: white; }
        .delete { background: #e74c3c; color: white; }
        code {
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 13px;
        }
        .code-block {
            background: #2b2b2b;
            color: #f8f8f2;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            font-family: monospace;
            font-size: 12px;
            margin: 10px 0;
        }
        .back { display: inline-block; margin-bottom: 20px; }
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
            margin-left: 10px;
        }
        .complete { background: #4caf50; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back">← Back to Home</a>
        
        <h1>🔌 API Documentation</h1>
        <p>Complete REST API reference for MRM Webpanel</p>
        
        <h2>Authentication</h2>
        <p>All endpoints except <code>/auth/login</code> require a Bearer token in the Authorization header.</p>
        <div class="code-block">
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" https://api.example.com/domains
        </div>
        
        <h2>Core Endpoints</h2>
        
        <h3>Auth</h3>
        <div class="endpoint"><span class="method post">POST</span> /auth/login <span class="status-badge complete">Complete</span></div>
        <p>Login with username and password, receive JWT token</p>
        <div class="code-block">{"username": "root", "password": "admin123"}</div>
        
        <div class="endpoint"><span class="method get">GET</span> /auth/verify <span class="status-badge complete">Complete</span></div>
        <p>Verify current JWT token validity</p>
        
        <h3>Users (Superadmin only)</h3>
        <div class="endpoint"><span class="method get">GET</span> /users <span class="status-badge complete">Complete</span></div>
        <p>List all users</p>
        
        <div class="endpoint"><span class="method post">POST</span> /users <span class="status-badge complete">Complete</span></div>
        <p>Create new user</p>
        
        <h3>Domains</h3>
        <div class="endpoint"><span class="method get">GET</span> /domains <span class="status-badge complete">Complete</span></div>
        <p>List domains (all if superadmin, own domain if admin)</p>
        
        <div class="endpoint"><span class="method post">POST</span> /domains <span class="status-badge complete">Complete</span></div>
        <p>Create domain with runtime (php|python|node)</p>
        <div class="code-block">{"domain": "example.com", "runtime": "php"}</div>
        
        <h3>Sites (Docker)</h3>
        <div class="endpoint"><span class="method get">GET</span> /domains/&lt;id&gt;/sites <span class="status-badge complete">Complete</span></div>
        <p>List sites for domain</p>
        
        <div class="endpoint"><span class="method post">POST</span> /domains/&lt;id&gt;/sites <span class="status-badge complete">Complete</span></div>
        <p>Create and deploy site (Docker container)</p>
        
        <div class="endpoint"><span class="method delete">DELETE</span> /domains/&lt;id&gt;/sites/&lt;site_id&gt; <span class="status-badge complete">Complete</span></div>
        <p>Delete site deployment (removes container, nginx config, and data)</p>
        
        <h3>Mail (Postfix + Dovecot)</h3>
        <div class="endpoint"><span class="method get">GET</span> /domains/&lt;id&gt;/mail/users <span class="status-badge complete">Complete</span></div>
        <p>List mail users for domain</p>
        
        <div class="endpoint"><span class="method post">POST</span> /domains/&lt;id&gt;/mail/users <span class="status-badge complete">Complete</span></div>
        <p>Create mail user</p>
        
        <h3>DNS (Bind9)</h3>
        <div class="endpoint"><span class="method get">GET</span> /domains/&lt;id&gt;/dns/zones <span class="status-badge complete">Complete</span></div>
        <p>Get DNS zone for domain</p>
        
        <div class="endpoint"><span class="method post">POST</span> /domains/&lt;id&gt;/dkim/generate <span class="status-badge complete">Complete</span></div>
        <p>Generate DKIM key pair</p>
        
        <h2>Response Format</h2>
        <p>All responses are JSON with the structure:</p>
        <div class="code-block">
{
  "ok": true,
  "data": {...},
  "error": null
}
        </div>
        
        <h2>Quick Start Example</h2>
        <div class="code-block">
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:5000/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"username":"root","password":"admin123"}' | jq -r '.token')

# 2. Create domain
curl -X POST http://localhost:5000/domains \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"domain":"myapp.com","runtime":"php"}'

# 3. Create mail user
curl -X POST http://localhost:5000/domains/1/mail/users \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"email":"admin@myapp.com","password":"secure123"}'
        </div>
        
        <h2>Status</h2>
        <p>✅ Phase 1-4 Complete (Installer, API, Docker, DNS)</p>
        <p>⏳ Phase 5-10 In Development (Mail integration, UI, Testing)</p>
    </div>
</body>
</html>
"""

# ============== Init Endpoints ==============

@app.route('/', methods=['GET'])
def home():
    """Home page with login and docs."""
    return render_template_string(HOME_PAGE)

@app.route('/docs', methods=['GET'])
def docs():
    """API documentation page."""
    return render_template_string(DOCS_PAGE)

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Admin dashboard page."""
    import os
    dashboard_path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
    with open(dashboard_path, 'r') as f:
        return f.read()


@app.route('/admin/migrate-deployments', methods=['POST'])
@superadmin_required
def migrate_deployments():
    """Migrate all existing deployments to use updated boilerplate and templates.
    
    This fixes Node.js 502 errors and other issues by regenerating:
    - Boilerplate files (server.js, app.py, index.php) with fixed code
    - docker-compose.yml files with updated templates
    - Restarts containers to apply changes
    
    Only superadmin can trigger this migration.
    """
    if not DockerEngine:
        return jsonify({'error': 'Docker engine not available'}), 503
    
    try:
        # Get all sites from database
        sites = fetch_all("""
            SELECT s.id, s.name, s.runtime, d.domain, d.runtime as domain_runtime, d.version
            FROM sites s
            JOIN domains d ON s.domain_id = d.id
            WHERE s.status IN ('active', 'failed')
        """)
        
        if not sites:
            return jsonify({
                'ok': True,
                'message': 'No sites to migrate',
                'migrated': 0,
                'failed': 0
            }), 200
        
        migrated_count = 0
        failed_count = 0
        failed_sites = []
        
        logger.info(f"Starting migration of {len(sites)} sites")
        
        for site in sites:
            try:
                domain = site['domain']
                runtime = site['domain_runtime'] or site['runtime'] or 'node'
                version = site['version'] or DEFAULT_VERSIONS.get(runtime, 'node18')
                site_id = site['id']
                
                logger.info(f"Migrating {domain} (runtime={runtime}, version={version})")
                
                # Create DockerEngine instance for this site
                # Determine boilerplate - if WordPress, keep it, otherwise use blank
                boilerplate = 'blank'
                if runtime == 'php':
                    # Check if this was a WordPress deployment by looking at compose file
                    compose_path = f"/srv/mrm/sites/{domain}/compose.yml"
                    if os.path.exists(compose_path):
                        with open(compose_path, 'r') as f:
                            if 'wordpress:php' in f.read():
                                boilerplate = 'wordpress'
                
                engine = DockerEngine(domain, runtime, site_id, version, boilerplate)
                
                # Run migration
                if engine.migrate_existing_deployment():
                    migrated_count += 1
                    update('sites', {'status': 'active'}, 'id=%s', (site_id,))
                    logger.info(f"✓ Successfully migrated {domain}")
                else:
                    failed_count += 1
                    failed_sites.append(domain)
                    update('sites', {'status': 'failed'}, 'id=%s', (site_id,))
                    logger.error(f"✗ Failed to migrate {domain}")
                    
            except Exception as e:
                failed_count += 1
                failed_sites.append(site.get('domain', 'unknown'))
                logger.error(f"Migration error for site {site.get('id')}: {e}")
        
        return jsonify({
            'ok': True,
            'message': f'Migration complete: {migrated_count} succeeded, {failed_count} failed',
            'total_sites': len(sites),
            'migrated': migrated_count,
            'failed': failed_count,
            'failed_sites': failed_sites
        }), 200
        
    except Exception as e:
        logger.error(f"Migration endpoint error: {e}")
        return jsonify({
            'error': 'Migration failed',
            'detail': str(e)
        }), 500


@app.route('/init', methods=['POST'])
def init_panel():
    """Initialize panel: create root superadmin."""
    data = request.json or {}
    password = data.get('password', 'admin123')
    
    try:
        user_id = create_root_superadmin(password)
        return jsonify({
            'ok': True,
            'message': 'Root superadmin initialized',
            'user_id': user_id
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============== Auth Endpoints ==============

@app.route('/auth/login', methods=['POST'])
def login():
    """Login endpoint: return JWT token."""
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    
    user = authenticate_user(username, password)
    
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    token = create_jwt_token(user['id'], user['username'], user['role'])
    
    return jsonify({
        'ok': True,
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'role': user['role']
        }
    }), 200

@app.route('/auth/verify', methods=['GET'])
@token_required
def verify_token():
    """Verify current token."""
    return jsonify({
        'ok': True,
        'user': request.current_user
    }), 200

# ============== User Management (Superadmin only) ==============

@app.route('/users', methods=['GET'])
@token_required
@superadmin_required
def list_users():
    """List all users (superadmin only)."""
    users = fetch_all("SELECT id, username, role, created_at FROM users ORDER BY created_at DESC")
    return jsonify({'ok': True, 'data': users}), 200

@app.route('/users', methods=['POST'])
@token_required
@superadmin_required
def create_user():
    """Create new admin user (superadmin only)."""
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'admin')
    
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    
    if role not in ('admin', 'superadmin'):
        return jsonify({'error': 'role must be admin or superadmin'}), 400
    
    # Check if user exists
    existing = fetch_one("SELECT id FROM users WHERE username=%s", (username,))
    if existing:
        return jsonify({'error': 'Username already exists'}), 409
    
    password_hash = hash_password(password)
    user_id = insert('users', {
        'username': username,
        'password_hash': password_hash,
        'role': role
    })
    
    return jsonify({
        'ok': True,
        'user_id': user_id,
        'username': username
    }), 201

@app.route('/users/<int:user_id>/password', methods=['PUT'])
@token_required
def change_password(user_id):
    """Change password for a user."""
    data = request.json or {}
    new_password = data.get('password')
    
    if not new_password:
        return jsonify({'error': 'password required'}), 400
    
    # Only superadmin can change other users; users can change own
    if request.current_user['user_id'] != user_id and not RBAC.is_superadmin(request.current_user):
        return jsonify({'error': 'Unauthorized'}), 403
    
    password_hash = hash_password(new_password)
    update('users', {'password_hash': password_hash}, 'id=%s', (user_id,))
    
    return jsonify({'ok': True}), 200

# ============== Templates API ==============

@app.route('/templates/available', methods=['GET'])
@token_required
def get_available_templates():
    """Detect and return available runtime templates."""
    import os
    templates_base = '/srv/mrm/templates'
    available = {
        'node': [],
        'python': [],
        'php': []
    }
    
    try:
        for runtime in ['node', 'python', 'php']:
            runtime_path = os.path.join(templates_base, runtime)
            if os.path.exists(runtime_path):
                for version_dir in os.listdir(runtime_path):
                    marker_file = os.path.join(runtime_path, version_dir, '.mrm-template')
                    if os.path.isfile(marker_file):
                        # Read the marker file to get metadata
                        try:
                            with open(marker_file, 'r') as f:
                                content = f.read()
                                # Extract label from marker file (format: "MRM Template: Node.js 18 LTS")
                                label = None
                                for line in content.split('\n'):
                                    if line.startswith('MRM Template:'):
                                        label = line.replace('MRM Template:', '').strip()
                                        break
                                
                                if not label:
                                    # Fallback label
                                    label = version_dir.replace(runtime, '').upper()
                                
                                available[runtime].append({
                                    'value': version_dir,
                                    'label': label
                                })
                        except Exception as e:
                            logger.warning(f"Could not read template marker: {e}")
                            continue
        
        return jsonify({'ok': True, 'templates': available}), 200
    except Exception as e:
        logger.error(f"Failed to scan templates: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

# ============== Domain Management ==============

def _default_runtime_settings(runtime: str) -> dict:
    runtime = (runtime or '').lower()
    if runtime == 'node':
        return {
            'node_entry_file': 'server.js',
            'node_watch': False,
        }
    if runtime == 'python':
        return {
            'python_gunicorn_app': 'app:app',
            'python_reload': False,
        }
    # php: no settings in v1
    return {}


def _load_domain_settings(domain_row: dict) -> dict:
    settings = {}
    raw = (domain_row or {}).get('settings_json')
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                settings = parsed
        except Exception:
            settings = {}

    merged = _default_runtime_settings((domain_row or {}).get('runtime'))
    if isinstance(settings, dict):
        merged.update(settings)
    return merged


def _validate_domain_settings(runtime: str, incoming: dict) -> tuple[bool, str | None, dict]:
    runtime = (runtime or '').lower()
    if not isinstance(incoming, dict):
        return False, 'settings must be an object', {}

    validated: dict = {}

    if runtime == 'node':
        entry = incoming.get('node_entry_file', 'server.js')
        watch = incoming.get('node_watch', False)

        if not isinstance(entry, str) or not entry.strip():
            return False, 'node_entry_file must be a non-empty string', {}
        entry = entry.strip()
        if entry.startswith('/') or '..' in entry.split('/'):
            return False, 'node_entry_file must be a relative path without ..', {}
        if not isinstance(watch, bool):
            return False, 'node_watch must be boolean', {}

        validated['node_entry_file'] = entry
        validated['node_watch'] = watch
        return True, None, validated

    if runtime == 'python':
        app_target = incoming.get('python_gunicorn_app', 'app:app')
        reload_flag = incoming.get('python_reload', False)

        if not isinstance(app_target, str) or not app_target.strip():
            return False, 'python_gunicorn_app must be a non-empty string', {}
        app_target = app_target.strip()
        if not re.match(r'^[A-Za-z0-9_\.]+:[A-Za-z0-9_]+$', app_target):
            return False, 'python_gunicorn_app must look like module:app', {}
        if not isinstance(reload_flag, bool):
            return False, 'python_reload must be boolean', {}

        validated['python_gunicorn_app'] = app_target
        validated['python_reload'] = reload_flag
        return True, None, validated

    if runtime == 'php':
        # No settings yet
        return True, None, {}

    return False, 'unknown runtime', {}


def _apply_domain_settings_if_deployed(domain_id: int, domain_row: dict):
    """Regenerate compose with settings and restart if the domain has a site."""
    try:
        if not DockerEngine:
            return

        site = fetch_one(
            "SELECT * FROM sites WHERE domain_id=%s ORDER BY created_at DESC LIMIT 1",
            (domain_id,)
        )
        if not site:
            return

        engine = DockerEngine(
            domain_row['domain'],
            domain_row.get('runtime', 'node'),
            site.get('id'),
            domain_row.get('version', 'node18'),
            'blank',
        )

        engine.generate_compose_file()
        engine.stop_container()
        engine.start_container()
        engine.wait_for_container_healthy()
    except Exception as e:
        logger.error(f"Failed to apply settings for domain_id={domain_id}: {e}")


def _php_ini_path_for_domain(domain_name: str) -> str:
    return os.path.join(SITES_DIR, domain_name, 'data', 'php.ini')


def _ensure_php_ini_exists(domain_name: str) -> str:
    ini_path = _php_ini_path_for_domain(domain_name)
    os.makedirs(os.path.dirname(ini_path), exist_ok=True)
    if not os.path.exists(ini_path):
        with open(ini_path, 'w') as f:
            f.write(
                f"; MRM per-domain PHP overrides for {domain_name}\n"
                "; Place only directives you want to override.\n"
                "; Changes apply after container restart.\n\n"
            )
    return ini_path


def _apply_php_ini_if_deployed(domain_id: int, domain_row: dict):
    """Regenerate compose (so php.ini volume mount is present) and restart if deployed."""
    try:
        if not DockerEngine:
            return

        site = fetch_one(
            "SELECT * FROM sites WHERE domain_id=%s ORDER BY created_at DESC LIMIT 1",
            (domain_id,)
        )
        if not site:
            return

        engine = DockerEngine(
            domain_row['domain'],
            domain_row.get('runtime', 'php'),
            site.get('id'),
            domain_row.get('version', 'php82'),
            'blank',
        )
        engine.generate_compose_file()
        engine.stop_container()
        engine.start_container()
        engine.wait_for_container_healthy()
    except Exception as e:
        logger.error(f"Failed to apply php.ini for domain_id={domain_id}: {e}")

@app.route('/domains', methods=['GET'])
@token_required
def list_domains():
    """List domains accessible to current user."""
    user = request.current_user
    
    if RBAC.is_superadmin(user):
        domains = fetch_all("SELECT * FROM domains ORDER BY created_at DESC")
    else:
        domains = fetch_all(
            "SELECT * FROM domains WHERE owner_user=%s ORDER BY created_at DESC",
            (user['user_id'],)
        )
    
    return jsonify({'ok': True, 'data': domains}), 200

@app.route('/domains', methods=['POST'])
@token_required
@admin_required
def create_domain():
    """Create new domain."""
    data = request.json or {}
    domain = data.get('domain')
    runtime = data.get('runtime')  # php|python|node
    version = data.get('version')
    
    if not domain or not runtime:
        return jsonify({'error': 'domain and runtime required'}), 400
    
    if runtime not in ('php', 'python', 'node'):
        return jsonify({'error': 'runtime must be php, python, or node'}), 400

    # Normalize version: treat empty string / null as default
    if not version:
        version = DEFAULT_VERSIONS.get(runtime, 'node18')
    
    # Check if domain exists
    existing = fetch_one("SELECT id FROM domains WHERE domain=%s", (domain,))
    if existing:
        return jsonify({'error': 'Domain already exists'}), 409
    
    # Check how many domains this admin has
    user = request.current_user
    if not RBAC.is_superadmin(user):
        count = fetch_one(
            "SELECT COUNT(*) as cnt FROM domains WHERE owner_user=%s",
            (user['user_id'],)
        )
        if count['cnt'] >= 1:  # Each admin can have only 1 domain for now (adjust if needed)
            return jsonify({'error': 'You can only create 1 domain per runtime'}), 403
    
    # Try to insert with version column, fallback if it doesn't exist
    try:
        domain_id = insert('domains', {
            'domain': domain,
            'owner_user': user['user_id'],
            'runtime': runtime,
            'version': version
        })
    except Exception as e:
        # If version column doesn't exist, try without it
        logger.warning(f"Could not insert version column: {e}, trying without version")
        domain_id = insert('domains', {
            'domain': domain,
            'owner_user': user['user_id'],
            'runtime': runtime
        })
    
    # Create SFTP user for this domain
    sftp_username = None
    sftp_password = None
    if SFTPManager:
        try:
            site_dir = os.path.join(SITES_DIR, domain)
            # Ensure site directory exists
            os.makedirs(site_dir, exist_ok=True)
            os.makedirs(os.path.join(site_dir, 'data'), exist_ok=True)
            
            sftp_manager = SFTPManager(domain, site_dir)
            result = sftp_manager.create_user()
            sftp_username = result['username']
            sftp_password = result['password']
            
            # Store SFTP credentials in database
            update('domains', {
                'sftp_username': sftp_username,
                'sftp_password': sftp_password
            }, 'id=%s', (domain_id,))
            
            logger.info(f"Created SFTP user {sftp_username} for domain {domain}")
        except Exception as e:
            logger.error(f"Failed to create SFTP user for {domain}: {e}")
            # Don't fail domain creation if SFTP fails
    
    return jsonify({
        'ok': True,
        'domain_id': domain_id,
        'domain': domain,
        'runtime': runtime,
        'version': version,
        'sftp_username': sftp_username,
        'sftp_password': sftp_password
    }), 201

@app.route('/domains/<int:domain_id>', methods=['GET'])
@token_required
def get_domain(domain_id):
    """Get domain details."""
    domain = fetch_one("SELECT * FROM domains WHERE id=%s", (domain_id,))
    
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({'ok': True, 'data': domain}), 200


@app.route('/domains/<int:domain_id>/settings', methods=['GET'])
@token_required
def get_domain_settings(domain_id):
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403

    domain = fetch_one("SELECT * FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404

    settings = _load_domain_settings(domain)
    return jsonify({'ok': True, 'data': settings}), 200


@app.route('/domains/<int:domain_id>/settings', methods=['PUT'])
@token_required
def update_domain_settings(domain_id):
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403

    domain = fetch_one("SELECT * FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404

    incoming = (request.json or {}).get('settings')
    ok, err, validated = _validate_domain_settings(domain.get('runtime'), incoming)
    if not ok:
        return jsonify({'error': err or 'Invalid settings'}), 400

    try:
        update('domains', {'settings_json': json.dumps(validated)}, 'id=%s', (domain_id,))
    except Exception as e:
        logger.error(f"Failed to store settings for domain_id={domain_id}: {e}")
        return jsonify({'error': 'Failed to store settings'}), 500

    # Apply automatically in background if deployed
    try:
        t = threading.Thread(
            target=_apply_domain_settings_if_deployed,
            args=(domain_id, domain),
            daemon=True,
        )
        t.start()
    except Exception as e:
        logger.warning(f"Could not start apply-settings worker: {e}")

    return jsonify({'ok': True, 'data': validated}), 200


@app.route('/domains/<int:domain_id>/phpini', methods=['GET'])
@token_required
def get_domain_php_ini(domain_id):
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403

    domain = fetch_one("SELECT * FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404

    if (domain.get('runtime') or '').lower() != 'php':
        return jsonify({'error': 'php.ini editor is only available for PHP domains'}), 400

    try:
        ini_path = _ensure_php_ini_exists(domain['domain'])
        with open(ini_path, 'r') as f:
            content = f.read()
        return jsonify({'ok': True, 'data': {'content': content}}), 200
    except Exception as e:
        logger.error(f"Failed to read php.ini for domain_id={domain_id}: {e}")
        return jsonify({'error': 'Failed to read php.ini'}), 500


@app.route('/domains/<int:domain_id>/phpini', methods=['PUT'])
@token_required
def update_domain_php_ini(domain_id):
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403

    domain = fetch_one("SELECT * FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404

    if (domain.get('runtime') or '').lower() != 'php':
        return jsonify({'error': 'php.ini editor is only available for PHP domains'}), 400

    content = (request.json or {}).get('content')
    if not isinstance(content, str):
        return jsonify({'error': 'content must be a string'}), 400
    if len(content) > 200_000:
        return jsonify({'error': 'php.ini content is too large'}), 413

    try:
        ini_path = _ensure_php_ini_exists(domain['domain'])
        with open(ini_path, 'w') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to write php.ini for domain_id={domain_id}: {e}")
        return jsonify({'error': 'Failed to write php.ini'}), 500

    # Apply automatically in background if deployed
    try:
        t = threading.Thread(
            target=_apply_php_ini_if_deployed,
            args=(domain_id, domain),
            daemon=True,
        )
        t.start()
    except Exception as e:
        logger.warning(f"Could not start php.ini apply worker: {e}")

    return jsonify({'ok': True}), 200

# ============== SFTP Management ==============

@app.route('/domains/<int:domain_id>/sftp', methods=['POST'])
@token_required
def create_sftp_user(domain_id):
    """Create SFTP user for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT * FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    # Check if SFTP user already exists
    if domain.get('sftp_username'):
        return jsonify({'error': 'SFTP user already exists'}), 409
    
    if not SFTPManager:
        return jsonify({'error': 'SFTP manager not available'}), 500
    
    try:
        site_dir = os.path.join(SITES_DIR, domain['domain'])
        # Ensure site directory exists
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(os.path.join(site_dir, 'data'), exist_ok=True)
        
        sftp_manager = SFTPManager(domain['domain'], site_dir)
        result = sftp_manager.create_user()
        sftp_username = result['username']
        sftp_password = result['password']
        
        # Store SFTP credentials in database
        update('domains', {
            'sftp_username': sftp_username,
            'sftp_password': sftp_password
        }, 'id=%s', (domain_id,))
        
        logger.info(f"Created SFTP user {sftp_username} for domain {domain['domain']}")
        
        return jsonify({
            'ok': True,
            'sftp_username': sftp_username,
            'sftp_password': sftp_password,
            'message': 'SFTP user created successfully'
        }), 201
    except Exception as e:
        logger.error(f"Failed to create SFTP user: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/domains/<int:domain_id>/sftp', methods=['DELETE'])
@token_required
def delete_sftp_user(domain_id):
    """Delete SFTP user for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT * FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    # Check if SFTP user exists
    if not domain.get('sftp_username'):
        return jsonify({'error': 'No SFTP user exists for this domain'}), 404
    
    if not SFTPManager:
        return jsonify({'error': 'SFTP manager not available'}), 500
    
    try:
        site_dir = os.path.join(SITES_DIR, domain['domain'])
        sftp_manager = SFTPManager(domain['domain'], site_dir)
        sftp_manager.delete_user()
        
        # Remove SFTP credentials from database
        update('domains', {
            'sftp_username': None,
            'sftp_password': None
        }, 'id=%s', (domain_id,))
        
        logger.info(f"Deleted SFTP user for domain {domain['domain']}")
        
        return jsonify({
            'ok': True,
            'message': 'SFTP user deleted successfully'
        }), 200
    except Exception as e:
        logger.error(f"Failed to delete SFTP user: {e}")
        return jsonify({'error': str(e)}), 500

# ============== Site Management ==============

@app.route('/domains/<int:domain_id>/sites/<int:site_id>/restart', methods=['POST'])
@token_required
def restart_site(domain_id, site_id):
    """Restart a site container."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT domain, runtime, version FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    site = fetch_one("SELECT * FROM sites WHERE id=%s AND domain_id=%s", (site_id, domain_id))
    if not site:
        return jsonify({'error': 'Site not found'}), 404
    
    if not DockerEngine:
        return jsonify({'error': 'Docker engine not available'}), 503
    
    try:
        runtime = domain.get('runtime') or 'node'
        version = domain.get('version') or DEFAULT_VERSIONS.get(runtime, 'node18')
        engine = DockerEngine(domain['domain'], runtime, site_id, version)
        if engine.stop_container() and engine.start_container():
            update('sites', {'status': 'active'}, 'id=%s', (site_id,))
            return jsonify({'ok': True, 'status': 'running'}), 200
        else:
            return jsonify({'error': 'Failed to restart container'}), 500
    except Exception as e:
        logger.error(f"Restart failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/domains/<int:domain_id>/sites/<int:site_id>/stop', methods=['POST'])
@token_required
def stop_site(domain_id, site_id):
    """Stop a site container."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT domain, runtime, version FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    site = fetch_one("SELECT * FROM sites WHERE id=%s AND domain_id=%s", (site_id, domain_id))
    if not site:
        return jsonify({'error': 'Site not found'}), 404
    
    if not DockerEngine:
        return jsonify({'error': 'Docker engine not available'}), 503
    
    try:
        runtime = domain.get('runtime') or 'node'
        version = domain.get('version') or DEFAULT_VERSIONS.get(runtime, 'node18')
        engine = DockerEngine(domain['domain'], runtime, site_id, version)
        if engine.stop_container():
            update('sites', {'status': 'stopped'}, 'id=%s', (site_id,))
            return jsonify({'ok': True, 'status': 'stopped'}), 200
        else:
            return jsonify({'error': 'Failed to stop container'}), 500
    except Exception as e:
        logger.error(f"Stop failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/domains/<int:domain_id>/sites/<int:site_id>', methods=['DELETE'])
@token_required
def delete_site(domain_id, site_id):
    """Delete a site and its deployment."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT domain, runtime FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    site = fetch_one("SELECT * FROM sites WHERE id=%s AND domain_id=%s", (site_id, domain_id))
    if not site:
        return jsonify({'error': 'Site not found'}), 404
    
    if not DockerEngine:
        return jsonify({'error': 'Docker engine not available'}), 503
    
    try:
        # Use Docker engine to destroy the deployment
        engine = DockerEngine(domain['domain'], domain['runtime'], site_id, domain.get('version', 'node18'))
        
        try:
            if not engine.destroy():
                # If destroy fails, try to get more details
                import subprocess
                try:
                    # Check if docker compose file exists
                    if not os.path.exists(engine.compose_file):
                        logger.warning(f"Compose file not found: {engine.compose_file}, but continuing with cleanup")
                    # Try to check docker status
                    result = subprocess.run(['docker', 'ps', '-a'], capture_output=True, text=True, timeout=5)
                    logger.error(f"Docker status: {result.stdout}")
                except:
                    pass
                return jsonify({'error': 'Failed to destroy site - check logs for details'}), 500
        except Exception as engine_error:
            logger.error(f"Engine destroy exception: {str(engine_error)}")
            return jsonify({'error': f'Destroy failed: {str(engine_error)}'}), 500
        
        # Remove from database
        delete('sites', 'id=%s', (site_id,))
        
        logger.info(f"Deleted site {site['name']} for domain {domain['domain']}")
        return jsonify({'ok': True, 'message': f'Site {site["name"]} deleted'}), 200
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/domains/<int:domain_id>', methods=['DELETE'])
@token_required
def delete_domain(domain_id):
    """Delete a domain and all related records (sites, mail users, databases)."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT id, domain, runtime, version FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    try:
        # Step 1: Delete all sites and their Docker deployments
        sites = fetch_all("SELECT id, name FROM sites WHERE domain_id=%s", (domain_id,))
        for site in sites:
            try:
                if DockerEngine:
                    engine = DockerEngine(domain['domain'], domain['runtime'], site['id'], domain.get('version', 'node18'))
                    engine.destroy()
                logger.info(f"Destroyed site {site['name']}")
            except Exception as e:
                logger.error(f"Failed to destroy site {site['name']}: {e}")
            
            # Delete from database
            delete('sites', 'id=%s', (site['id'],))
        
        # Step 2: Delete all mail users for this domain
        delete('mail_users', 'domain_id=%s', (domain_id,))
        
        # Step 3: Delete all databases for this domain
        delete('databases', 'domain_id=%s', (domain_id,))
        
        # Step 4: Delete the domain itself
        delete('domains', 'id=%s', (domain_id,))
        
        logger.info(f"Deleted domain {domain['domain']} and all related records")
        return jsonify({'ok': True, 'message': f'Domain {domain["domain"]} deleted'}), 200
    except Exception as e:
        logger.error(f"Delete domain failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/domains/<int:domain_id>/dkim/generate', methods=['POST'])
@token_required
def generate_dkim_key(domain_id):
    """Generate DKIM key for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT domain FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    data = request.json or {}
    selector = data.get('selector', 'default')
    
    try:
        import subprocess
        keydir = f"/etc/opendkim/keys/{domain['domain']}"
        os.makedirs(keydir, exist_ok=True)
        
        # Generate DKIM key
        result = subprocess.run(
            ['opendkim-genkey', '-D', keydir, '-d', domain['domain'], '-s', selector],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return jsonify({'error': 'DKIM generation failed', 'detail': result.stderr}), 500
        
        # Read public key
        public_key_file = os.path.join(keydir, f"{selector}.txt")
        with open(public_key_file, 'r') as f:
            public_key = f.read()
        
        # Store in DB
        insert('dkim_keys', {
            'domain_id': domain_id,
            'domain': domain['domain'],
            'selector': selector,
            'private_key': '***STORED_SECURELY***',
            'public_key': public_key
        })
        
        return jsonify({
            'ok': True,
            'domain': domain['domain'],
            'selector': selector,
            'public_key': public_key,
            'dns_record': f"{selector}._domainkey.{domain['domain']}"
        }), 201
    except Exception as e:
        logger.error(f"DKIM generation failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/domains/<int:domain_id>/sites', methods=['GET'])
@token_required
def list_sites(domain_id):
    """List sites for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    sites = fetch_all(
        "SELECT * FROM sites WHERE domain_id=%s ORDER BY created_at DESC",
        (domain_id,)
    )
    
    return jsonify({'ok': True, 'data': sites}), 200

@app.route('/domains/<int:domain_id>/sites/<int:site_id>/deployment-logs', methods=['GET'])
@token_required
def get_deployment_logs(domain_id, site_id):
    """Get real-time deployment logs for a site."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    # Find the active deployment engine for this site
    deployment_key = f"{domain_id}_{site_id}"
    engine = active_deployments.get(deployment_key)
    
    if not engine:
        # Check if site exists and get its status
        site = fetch_one("SELECT * FROM sites WHERE id=%s AND domain_id=%s", (site_id, domain_id))
        if not site:
            return jsonify({'error': 'Site not found'}), 404
        
        # If deployment is complete or failed, return final status
        if site['status'] in ('active', 'failed'):
            return jsonify({
                'ok': True,
                'phase': site['status'],
                'progress': 100 if site['status'] == 'active' else 0,
                'logs': [f"Deployment {site['status']}"],
                'completed': True
            }), 200
        
        # Otherwise no logs available yet
        return jsonify({
            'ok': True,
            'phase': 'deploying',
            'progress': 0,
            'logs': ['Initializing deployment...'],
            'completed': False
        }), 200
    
    # Return current deployment status and logs
    return jsonify({
        'ok': True,
        'phase': engine.deployment_phase,
        'progress': engine.deployment_progress,
        'logs': engine.deployment_logs,
        'completed': engine.deployment_phase in ('completed', 'failed')
    }), 200

@app.route('/domains/<int:domain_id>/sites', methods=['POST'])
@token_required
def create_site(domain_id):
    """Create site for a domain with Docker deployment."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT * FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    data = request.json or {}
    site_name = data.get('name', domain['domain'])
    
    if not DockerEngine:
        return jsonify({'error': 'Docker engine not available'}), 503
    
    try:
        # Record site in DB first with 'deploying' status so UI can show progress
        site_id = insert('sites', {
            'domain_id': domain_id,
            'name': site_name,
            'runtime': domain.get('runtime', 'node'),
            'status': 'deploying'
        })

        # Deploy with Docker engine in background to avoid blocking the Flask dev server
        runtime = domain.get('runtime') or 'node'  # Get runtime from domain record
        version = domain.get('version') or DEFAULT_VERSIONS.get(runtime, 'node18')  # Normalize empty strings
        boilerplate = data.get('boilerplate', 'blank')  # Get boilerplate selection from request
        
        # Ensure runtime and version are not None
        if not runtime:
            runtime = 'node'
        if not version:
            version = DEFAULT_VERSIONS.get(runtime, 'node18')
        
        engine = DockerEngine(domain['domain'], runtime, site_id, version, boilerplate)
        
        # Store engine in active_deployments for log streaming
        deployment_key = f"{domain_id}_{site_id}"
        active_deployments[deployment_key] = engine

        def _deploy_worker(engine_obj, domain_rec, site_rec_id, domain_rec_id, deploy_key):
            try:
                ok = engine_obj.deploy()
                if ok:
                    update('sites', {'status': 'active'}, 'id=%s', (site_rec_id,))
                else:
                    # Store deployment logs in deploy_error for debugging
                    error_msg = "Deployment failed. Logs:\n" + "\n".join(engine_obj.deployment_logs)
                    update('sites', {'status': 'failed', 'deploy_error': error_msg}, 'id=%s', (site_rec_id,))
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                logger.error(f"Background deploy failed for {domain_rec}: {tb}")
                # Try to persist the error to the sites table if a column exists
                try:
                    # Include deployment logs if available
                    error_msg = tb
                    if hasattr(engine_obj, 'deployment_logs') and engine_obj.deployment_logs:
                        error_msg += "\n\nDeployment Logs:\n" + "\n".join(engine_obj.deployment_logs)
                    update('sites', {'status': 'failed', 'deploy_error': error_msg}, 'id=%s', (site_rec_id,))
                except Exception:
                    update('sites', {'status': 'failed'}, 'id=%s', (site_rec_id,))
            finally:
                # Clean up active deployment after 60 seconds
                import time
                time.sleep(60)
                if deploy_key in active_deployments:
                    del active_deployments[deploy_key]

        t = threading.Thread(target=_deploy_worker, args=(engine, domain['domain'], site_id, domain_id, deployment_key), daemon=True)
        t.start()
        
        # Also deploy DNS zone if Bind9 available
        if Bind9Manager:
            try:
                dns = Bind9Manager(domain['domain'], '127.0.0.1')
                dns.deploy()
                insert('dns_zones', {
                    'domain_id': domain_id,
                    'domain': domain['domain'],
                    'zone_file_path': dns.zone_file,
                    'status': 'active'
                })
            except Exception as e:
                logger.warning(f"DNS deployment skipped: {e}")
        
        return jsonify({
            'ok': True,
            'site_id': site_id,
            'site_name': site_name,
            'domain': domain['domain'],
            'runtime': domain['runtime'],
            'status': 'deploying',
            'message': 'Deployment started (background)'
        }), 201
    except Exception as e:
        logger.error(f"Site creation failed: {e}")
        return jsonify({
            'error': 'Site creation failed',
            'detail': str(e)
        }), 500

# ============== Mail User Management ==============

@app.route('/domains/<int:domain_id>/mail/users', methods=['GET'])
@token_required
def list_mail_users(domain_id):
    """List mail users for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT id FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    domain_mail = fetch_one("SELECT id FROM mail_domains WHERE domain_id=%s", (domain_id,))
    if not domain_mail:
        return jsonify({'ok': True, 'data': []}), 200
    
    users = fetch_all(
        "SELECT id, username, created_at FROM mail_users WHERE domain_id=%s",
        (domain_mail['id'],)
    )
    
    return jsonify({'ok': True, 'data': users}), 200

@app.route('/domains/<int:domain_id>/mail/users', methods=['POST'])
@token_required
def create_mail_user(domain_id):
    """Create mail user for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT domain FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    
    # Ensure mail domain exists
    mail_domain = fetch_one("SELECT id FROM mail_domains WHERE domain=%s", (domain['domain'],))
    if not mail_domain:
        mail_domain_id = insert('mail_domains', {'domain': domain['domain']})
    else:
        mail_domain_id = mail_domain['id']
    
    # Create mail user
    password_hash = hash_password(password)
    mailbox = f"{username}@{domain['domain']}"
    user_id = insert('mail_users', {
        'domain_id': mail_domain_id,
        'username': username,
        'password_hash': password_hash,
        'mailbox': mailbox
    })
    
    return jsonify({
        'ok': True,
        'user_id': user_id,
        'username': username,
        'mailbox': mailbox
    }), 201

# ============== DNS Zone Management ==============

@app.route('/domains/<int:domain_id>/dns/zones', methods=['GET'])
@token_required
def get_dns_zone(domain_id):
    """Get DNS zone info for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT domain FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    zone = fetch_one("SELECT * FROM dns_zones WHERE domain_id=%s", (domain_id,))
    
    if zone:
        return jsonify({
            'zone': {
                'domain': zone['domain'],
                'zone_file': zone['zone_file_path'],
                'status': zone['status']
            }
        }), 200
    
    # Return basic zone info (zone not yet created)
    return jsonify({
        'zone': {
            'domain': domain['domain'],
            'status': 'not_created'
        }
    }), 200

@app.route('/domains/<int:domain_id>/dns/records', methods=['GET'])
@token_required
def list_dns_records(domain_id):
    """List DNS records for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    zone = fetch_one("SELECT id FROM dns_zones WHERE domain_id=%s", (domain_id,))
    if not zone:
        return jsonify({'records': []}), 200
    
    records = fetch_all(
        "SELECT type, name, value, ttl, priority FROM dns_records WHERE zone_id=%s ORDER BY type",
        (zone['id'],)
    )
    
    return jsonify({'ok': True, 'data': records}), 200

@app.route('/domains/<int:domain_id>/dns/records', methods=['POST'])
@token_required
def add_dns_record(domain_id):
    """Add DNS record for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.json or {}
    record_type = data.get('type')
    name = data.get('name', '@')
    value = data.get('value')
    ttl = data.get('ttl', 3600)
    priority = data.get('priority')
    
    if not record_type or not value:
        return jsonify({'error': 'type and value required'}), 400
    
    zone = fetch_one("SELECT id FROM dns_zones WHERE domain_id=%s", (domain_id,))
    if not zone:
        return jsonify({'error': 'DNS zone not created yet'}), 404
    
    record_id = insert('dns_records', {
        'zone_id': zone['id'],
        'type': record_type,
        'name': name,
        'value': value,
        'ttl': ttl,
        'priority': priority
    })
    
    return jsonify({
        'ok': True,
        'record_id': record_id,
        'type': record_type,
        'name': name
    }), 201

# ============== Database Management ==============

@app.route('/domains/<int:domain_id>/databases', methods=['GET'])
@token_required
def list_databases(domain_id):
    """List databases for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    dbs = fetch_all(
        "SELECT * FROM `databases` WHERE domain_id=%s ORDER BY created_at DESC",
        (domain_id,)
    )
    
    return jsonify({'ok': True, 'data': dbs}), 200

@app.route('/domains/<int:domain_id>/databases', methods=['POST'])
@token_required
def create_database(domain_id):
    """Create database for a domain."""
    if not RBAC.can_access_domain(request.current_user, domain_id):
        return jsonify({'error': 'Access denied'}), 403
    
    domain = fetch_one("SELECT domain FROM domains WHERE id=%s", (domain_id,))
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    
    data = request.json or {}
    db_name = data.get('name')
    
    if not db_name:
        return jsonify({'error': 'name required'}), 400
    
    db_id = insert('databases', {
        'domain_id': domain_id,
        'name': db_name,
        'created_by': request.current_user['user_id']
    })
    
    return jsonify({
        'ok': True,
        'db_id': db_id,
        'name': db_name
    }), 201

# ============== Health Check ==============

@app.route('/', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'MRM Webpanel',
        'version': '0.1.0',
        'endpoints': {
            'auth': ['/auth/login', '/auth/verify'],
            'users': ['/users', '/users/<id>/password'],
            'domains': ['/domains', '/domains/<id>'],
            'sites': ['/domains/<id>/sites'],
            'mail': ['/domains/<id>/mail/users'],
            'dns': ['/domains/<id>/dns/zones'],
            'databases': ['/domains/<id>/databases']
        }
    }), 200

# ============== Error Handlers ==============

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error', 'detail': str(e)}), 500

if __name__ == '__main__':
    # Run database migrations
    ensure_database_schema()
    
    # Initialize root superadmin if needed
    create_root_superadmin()
    
    # Configure SSH chroot for SFTP users
    if SFTPManager:
        try:
            SFTPManager.configure_ssh_chroot()
            logger.info("SSH chroot configuration completed")
        except Exception as e:
            logger.error(f"Failed to configure SSH chroot: {e}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
