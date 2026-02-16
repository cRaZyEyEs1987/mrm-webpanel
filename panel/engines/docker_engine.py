"""
Docker orchestration engine for per-site deployment.
Manages Docker Compose files, container lifecycle, and nginx reverse-proxy config.
"""

import os
import json
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SITES_DIR = os.environ.get('SITES_DIR', '/srv/mrm/sites')
TEMPLATES_DIR = os.environ.get('TEMPLATES_DIR', '/etc/mrm-webpanel/templates')
NGINX_AVAILABLE = '/etc/nginx/sites-available'
NGINX_ENABLED = '/etc/nginx/sites-enabled'

class DockerEngine:
    """Manage Docker Compose deployments for sites."""
    
    # Version to Docker image mapping (simplified to single version per runtime)
    VERSION_MAP = {
        'node18': 'node:18-alpine',
        'python311': 'python:3.11-slim',
        'php82': 'php:8.2-apache',
    }
    
    def __init__(self, domain, runtime, site_id=None, version=None, boilerplate=None):
        self.domain = domain
        self.runtime = runtime
        self.version = version or 'node18'  # Default version
        self.boilerplate = boilerplate or 'blank'  # Default boilerplate
        self.site_id = site_id or domain
        self.site_dir = os.path.join(SITES_DIR, domain)
        self.compose_file = os.path.join(self.site_dir, 'compose.yml')
        self.data_dir = os.path.join(self.site_dir, 'data')
        # Use dynamic port: 3000 + site_id
        self.upstream_port = 3000 + (int(self.site_id) if isinstance(self.site_id, (int, str)) else 0)
        
        # Get the Docker image for this version
        self.docker_image = self.VERSION_MAP.get(self.version, 'node:18-alpine')
        
        # Deployment progress tracking
        self.deployment_logs = []
        self.deployment_phase = 'initializing'
        self.deployment_progress = 0
        
        logger.info(f"DockerEngine initialized: domain={domain}, runtime={runtime}, version={version}, boilerplate={boilerplate}, image={self.docker_image}")
    
    def get_friendly_version_label(self):
        """Get a human-friendly label for the current version."""
        labels = {
            'node18': 'Node.js 18 (LTS)',
            'node20': 'Node.js 20 (LTS)',
            'node21': 'Node.js 21 (Current)',
            'php82': 'PHP 8.2',
            'php83': 'PHP 8.3',
            'python310': 'Python 3.10',
            'python311': 'Python 3.11',
            'python312': 'Python 3.12',
        }
        return labels.get(self.version, self.version)
    
    def create_directories(self):
        """Create site directory structure."""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.site_dir, exist_ok=True)
        logger.info(f"Created directories for {self.domain}")
    
    def create_boilerplate(self):
        """Create default application boilerplate for the runtime."""
        try:
            if self.runtime == 'node':
                self._create_node_boilerplate(self.boilerplate)
            elif self.runtime == 'python':
                self._create_python_boilerplate(self.boilerplate)
            elif self.runtime == 'php':
                # WordPress is handled by its own container image; no local code scaffold needed.
                if self.boilerplate != 'wordpress':
                    self._create_php_boilerplate(self.boilerplate)
            logger.info(f"Created {self.boilerplate} boilerplate for {self.runtime} runtime")
        except Exception as e:
            logger.error(f"Failed to create boilerplate: {e}")

    def _select_compose_template(self) -> str:
        """Select the right docker-compose template based on runtime and boilerplate."""
        if self.runtime == 'php' and self.boilerplate == 'wordpress':
            return 'docker-compose.wordpress.tpl'

        template_map = {
            'php': 'docker-compose.php.tpl',
            'python': 'docker-compose.python.tpl',
            'node': 'docker-compose.node.tpl'
        }

        if self.runtime not in template_map:
            raise ValueError(f"Unknown runtime: {self.runtime}")

        return template_map[self.runtime]

    def _get_container_port(self) -> int:
        """Return the internal container port the app listens on."""
        if self.runtime == 'php':
            # php-apache and wordpress images serve HTTP on 80
            return 80
        # Node and our Python gunicorn template listen on 3000
        return 3000
    
    def migrate_existing_deployment(self):
        """Migrate an existing deployment to use updated boilerplate and templates.
        
        This regenerates:
        - Boilerplate code (server.js, app.py, index.php)
        - docker-compose.yml from updated templates
        - Restarts the container to apply changes
        
        Returns True if migration successful, False otherwise.
        """
        try:
            logger.info(f"Migrating existing deployment for {self.domain}")
            
            # Stop the container first
            self.stop_container()
            
            # Regenerate boilerplate files (this will overwrite old code)
            self.create_boilerplate()
            
            # Regenerate docker-compose.yml with updated template
            self.generate_compose_file()
            
            # Start container with new configuration
            if self.start_container():
                logger.info(f"Successfully migrated {self.domain}")
                return True
            else:
                logger.error(f"Failed to start container after migration for {self.domain}")
                return False
                
        except Exception as e:
            logger.error(f"Migration failed for {self.domain}: {e}")
            return False
    
    def _create_node_boilerplate(self, boilerplate='blank'):
        """Create Node.js/Express boilerplate."""
        # package.json
        package_json = {
            "name": self.domain.replace('.', '-'),
            "version": "1.0.0",
            "description": f"Auto-generated Node.js app for {self.domain}",
            "main": "server.js",
            "scripts": {
                "start": "node server.js",
                "dev": "node server.js"
            },
            "dependencies": {
                "express": "^4.18.0"
            }
        }
        with open(os.path.join(self.data_dir, 'package.json'), 'w') as f:
            json.dump(package_json, f, indent=2)
        
        # server.js
        server_js = f'''const express = require('express');
const path = require('path');
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(__dirname));

// Serve HTML
app.get('/', (req, res) => {{
  res.sendFile(path.join(__dirname, 'index.html'));
}});

// API endpoints
app.get('/api/status', (req, res) => {{
  res.json({{
    status: 'ok',
    domain: '{self.domain}',
    runtime: '{self.get_friendly_version_label()}',
    uptime: process.uptime().toFixed(2),
    timestamp: new Date().toISOString()
  }});
}});

app.get('/health', (req, res) => {{
  res.json({{ status: 'healthy' }});
}});

// 404 handler
app.use((req, res) => {{
  res.status(404).json({{ error: 'Not found' }});
}});

app.listen(port, '0.0.0.0', () => {{
  console.log(`✓ Server running on port ${{port}}`);
  console.log(`✓ Domain: {self.domain}`);
  console.log(`✓ Visit http://localhost:${{port}}/`);
}});
'''
        with open(os.path.join(self.data_dir, 'server.js'), 'w') as f:
            f.write(server_js)
        
        # index.html
        index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.domain}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 60px 40px;
            max-width: 600px;
            text-align: center;
        }}
        h1 {{
            color: #333;
            font-size: 48px;
            margin-bottom: 20px;
        }}
        p {{
            color: #666;
            font-size: 16px;
            margin-bottom: 30px;
        }}
        .info {{
            background: #f0f7ff;
            border-left: 4px solid #667eea;
            padding: 20px;
            text-align: left;
            border-radius: 5px;
            margin-top: 30px;
            font-family: monospace;
            font-size: 14px;
        }}
        button {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            margin-top: 20px;
            font-weight: 600;
        }}
        button:hover {{ transform: translateY(-2px); }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 {self.domain}</h1>
        <p>Your Node.js application is live!</p>
        <div class="info" id="info">Loading...</div>
        <button onclick="getStatus()">Check Status 📊</button>
    </div>
    <script>
        getStatus();
        setInterval(getStatus, 5000);
        
        function getStatus() {{
            fetch('/api/status')
                .then(r => r.json())
                .then(d => {{
                    document.getElementById('info').innerHTML = `
                        <strong>Domain:</strong> ${{d.domain}}<br>
                        <strong>Runtime:</strong> ${{d.runtime}}<br>
                        <strong>Uptime:</strong> ${{d.uptime}}s<br>
                        <strong>Status:</strong> ✅ ${{d.status}}
                    `;
                }})
                .catch(e => console.error(e));
        }}
    </script>
</body>
</html>
'''
        with open(os.path.join(self.data_dir, 'index.html'), 'w') as f:
            f.write(index_html)
    
    def _create_python_boilerplate(self, boilerplate='blank'):
        """Create Python/Flask boilerplate."""
        app_py = f'''from flask import Flask, render_template_string
import time

app = Flask(__name__)
start_time = time.time()

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{self.domain}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .container {{ background: white; padding: 40px; border-radius: 10px; text-align: center; }}
            h1 {{ color: #333; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🐍 {self.domain}</h1>
            <p>Python/Flask is running!</p>
        </div>
    </body>
    </html>
    """)

@app.route('/api/status')
def status():
    uptime = int(time.time() - start_time)
    return {{
        'status': 'ok',
        'domain': '{self.domain}',
        'runtime': '{self.get_friendly_version_label()}',
        'uptime': uptime
    }}

@app.route('/health')
def health():
    return {{'status': 'healthy'}}

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
'''
        with open(os.path.join(self.data_dir, 'app.py'), 'w') as f:
            f.write(app_py)
        
        # requirements.txt
        with open(os.path.join(self.data_dir, 'requirements.txt'), 'w') as f:
            f.write('Flask==2.3.0\n')
    
    def _create_php_boilerplate(self, boilerplate='blank'):
        """Create PHP boilerplate."""
        index_php = f'''<?php
header('Content-Type: text/html');
?>
<!DOCTYPE html>
<html>
<head>
    <title>{self.domain}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }}
        .container {{ background: white; padding: 40px; border-radius: 10px; text-align: center; }}
        h1 {{ color: #333; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🐘 {self.domain}</h1>
        <p>PHP is running!</p>
        <p>Version: <?php echo phpversion(); ?></p>
    </div>
</body>
</html>
'''
        with open(os.path.join(self.data_dir, 'index.php'), 'w') as f:
            f.write(index_php)

    def generate_compose_file(self):
        """Generate docker-compose.yml from template."""
        template_name = self._select_compose_template()
        template_path = os.path.join(TEMPLATES_DIR, template_name)
        
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Replace placeholders
        container_port = self._get_container_port()
        content = content.replace('{{DOMAIN}}', self.domain)
        content = content.replace('{{SITE_DIR}}', self.data_dir)
        content = content.replace('{{DOCKER_IMAGE}}', self.docker_image)
        content = content.replace('{{UPSTREAM_PORT}}', str(self.upstream_port))
        content = content.replace('{{CONTAINER_PORT}}', str(container_port))
        
        # Write compose file
        with open(self.compose_file, 'w') as f:
            f.write(content)
        
        os.chmod(self.compose_file, 0o600)
        logger.info(
            f"Generated compose file for {self.domain} using template {template_name} "
            f"on port {self.upstream_port} (container {container_port}) using image {self.docker_image}"
        )
    
    
    def generate_nginx_config(self, upstream_port=3000):
        """Generate nginx reverse-proxy config."""
        nginx_conf = f"""
upstream {self.domain.replace('.', '_')} {{
    server 127.0.0.1:{upstream_port};
    keepalive 64;
}}

server {{
    listen 80;
    listen [::]:80;
    server_name {self.domain} www.{self.domain};
    root {self.data_dir};
    
    # Let's Encrypt
    location /.well-known/acme-challenge/ {{
        allow all;
    }}
    
    # Proxy to application
    location / {{
        proxy_pass http://{self.domain.replace('.', '_')};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
    }}
    
    # Deny access to sensitive files
    location ~ /\\. {{
        deny all;
        access_log off;
        log_not_found off;
    }}
    
    access_log /var/log/nginx/{self.domain}.access.log;
    error_log /var/log/nginx/{self.domain}.error.log;
}}
"""
        
        nginx_file = os.path.join(NGINX_AVAILABLE, f"{self.domain}.conf")
        with open(nginx_file, 'w') as f:
            f.write(nginx_conf)
        
        os.chmod(nginx_file, 0o644)
        
        # Create symlink in sites-enabled
        nginx_enabled_link = os.path.join(NGINX_ENABLED, f"{self.domain}.conf")
        if os.path.exists(nginx_enabled_link):
            os.remove(nginx_enabled_link)
        os.symlink(nginx_file, nginx_enabled_link)
        
        logger.info(f"Generated nginx config for {self.domain}")
    
    def validate_nginx_config(self):
        """Test nginx config syntax."""
        try:
            subprocess.run(['nginx', '-t'], check=True, capture_output=True)
            logger.info("Nginx config valid")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Nginx config error: {e.stderr.decode()}")
            return False
    
    def reload_nginx(self):
        """Reload nginx to apply new config."""
        try:
            if not self.validate_nginx_config():
                return False
            subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
            logger.info("Nginx reloaded")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload nginx: {e}")
            return False
    
    def start_container(self):
        """Start Docker container using docker-compose."""
        try:
            self.deployment_phase = 'pulling_image'
            self.deployment_progress = 10
            self._add_deployment_log(f"Starting deployment for {self.domain}...")
            self._add_deployment_log(f"Using Docker image: {self.docker_image}")
            
            # Use Popen to capture output in real-time
            process = subprocess.Popen(
                ['docker', 'compose', '-f', self.compose_file, 'up', '-d'],
                cwd=self.site_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output line by line
            for line in process.stdout:
                line = line.strip()
                if line:
                    self._add_deployment_log(line)
                    
                    # Update phase based on output
                    if 'Pulling' in line or 'Downloading' in line:
                        self.deployment_phase = 'pulling_image'
                        self.deployment_progress = min(self.deployment_progress + 5, 60)
                    elif 'Creating' in line or 'Starting' in line:
                        self.deployment_phase = 'starting_container'
                        self.deployment_progress = 70
                    elif 'Started' in line or 'Created' in line:
                        self.deployment_phase = 'container_started'
                        self.deployment_progress = 80
            
            process.wait()
            
            if process.returncode != 0:
                self._add_deployment_log(f"ERROR: Container startup failed with exit code {process.returncode}")
                logger.error(f"Failed to start container for {self.domain}")
                return False
            
            self.deployment_phase = 'installing_dependencies'
            self.deployment_progress = 85
            self._add_deployment_log("Container started, waiting for application to be ready...")
            logger.info(f"Started container for {self.domain}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            self._add_deployment_log(f"ERROR: {error_msg}")
            logger.error(f"Unexpected error starting container for {self.domain}: {e}")
            return False
    
    def _add_deployment_log(self, message):
        """Add a log message to deployment logs."""
        import time
        timestamp = time.strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.deployment_logs.append(log_entry)
        logger.debug(f"Deployment log: {log_entry}")
    
    def stop_container(self):
        """Stop Docker container."""
        try:
            # Try docker compose down first if compose file exists
            if os.path.exists(self.compose_file):
                result = subprocess.run(
                    ['docker', 'compose', '-f', self.compose_file, 'down'],
                    cwd=self.site_dir,
                    check=False,
                    capture_output=True,
                    timeout=30
                )
                logger.info(f"Stopped container for {self.domain} via compose")
                return True
            
            # Fallback: stop by container name directly
            # Try common container name patterns that docker-compose might use
            for pattern in [f"{self.domain}-app", f"{self.domain.replace('.', '')}-app-1", f"{self.domain.replace('.', '')}_app_1"]:
                try:
                    result = subprocess.run(
                        ['docker', 'stop', pattern],
                        check=False,
                        capture_output=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        logger.info(f"Stopped container {pattern} for {self.domain}")
                        
                        # Also try to remove it
                        subprocess.run(
                            ['docker', 'rm', pattern],
                            check=False,
                            capture_output=True,
                            timeout=10
                        )
                        return True
                except:
                    pass
            
            logger.warning(f"Could not find running container for {self.domain}, continuing with cleanup")
            return True
        except Exception as e:
            logger.error(f"Failed to stop container: {e}")
            return False
    
    def get_container_status(self):
        """Get container status."""
        try:
            result = subprocess.run(
                ['docker', 'compose', '-f', self.compose_file, 'ps', '--quiet'],
                cwd=self.site_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return 'running'
            else:
                return 'stopped'
        except Exception as e:
            logger.error(f"Failed to get container status: {e}")
            return 'error'
    
    def deploy(self, upstream_port=None):
        """Full deployment: create dirs, compose file, nginx config, and start container."""
        try:
            self.deployment_phase = 'initializing'
            self.deployment_progress = 0
            self._add_deployment_log(f"Starting deployment for {self.domain}")
            
            self.deployment_phase = 'creating_directories'
            self.deployment_progress = 5
            self.create_directories()
            self._add_deployment_log("Created site directories")
            
            self.deployment_phase = 'creating_boilerplate'
            self._add_deployment_log(f"Creating {self.boilerplate} boilerplate code")
            self.create_boilerplate()  # AUTO-GENERATE APP CODE
            
            self.deployment_phase = 'generating_compose'
            self._add_deployment_log("Generating docker-compose configuration")
            self.generate_compose_file()
            
            # Start container FIRST before nginx config
            if not self.start_container():
                logger.error("Failed to start container")
                self.deployment_phase = 'failed'
                return False
            
            # Wait for container to be healthy (5 minutes timeout for image pulls)
            if not self.wait_for_container_health(timeout=300):
                logger.error("Container failed to become healthy within 5 minutes")
                self.deployment_phase = 'failed'
                return False
            
            # Now generate and reload nginx config
            self.deployment_phase = 'configuring_nginx'
            self.deployment_progress = 97
            self._add_deployment_log("Configuring nginx reverse proxy")
            self.generate_nginx_config(self.upstream_port)
            
            if not self.reload_nginx():
                logger.error("Failed to reload nginx")
                self.deployment_phase = 'failed'
                return False
            
            self.deployment_phase = 'completed'
            self.deployment_progress = 100
            self._add_deployment_log(f"✓ Successfully deployed {self.domain} on port {self.upstream_port}")
            logger.info(f"Successfully deployed {self.domain} on port {self.upstream_port}")
            return True
        except Exception as e:
            self.deployment_phase = 'failed'
            self._add_deployment_log(f"ERROR: Deployment failed: {e}")
            logger.error(f"Deployment failed: {e}")
            return False
    
    def destroy(self):
        """Remove site: stop container, remove configs, cleanup."""
        errors = []
        
        # Step 1: Stop container
        try:
            self.stop_container()
            logger.info(f"Stopped container for {self.domain}")
        except Exception as e:
            msg = f"Failed to stop container: {str(e)}"
            logger.error(msg)
            errors.append(msg)
        
        # Step 2: Remove nginx symlink first (so nginx -t doesn't fail)
        try:
            nginx_enabled = os.path.join(NGINX_ENABLED, f"{self.domain}.conf")
            if os.path.islink(nginx_enabled):
                os.unlink(nginx_enabled)
                logger.info(f"Removed nginx symlink: {nginx_enabled}")
            elif os.path.exists(nginx_enabled):
                os.remove(nginx_enabled)
                logger.info(f"Removed nginx enabled file: {nginx_enabled}")
        except Exception as e:
            msg = f"Failed to remove nginx symlink: {str(e)}"
            logger.error(msg)
            # Don't add to critical errors for symlink issues
        
        # Step 3: Remove nginx config file
        try:
            nginx_file = os.path.join(NGINX_AVAILABLE, f"{self.domain}.conf")
            if os.path.exists(nginx_file):
                os.remove(nginx_file)
                logger.info(f"Removed nginx config: {nginx_file}")
        except Exception as e:
            msg = f"Failed to remove nginx config: {str(e)}"
            logger.error(msg)
            errors.append(msg)
        
        # Step 4: Reload nginx (this should work now that broken symlinks are gone)
        try:
            if self.validate_nginx_config():
                self.reload_nginx()
                logger.info(f"Reloaded nginx after removing {self.domain}")
            else:
                logger.warning(f"Nginx config validation failed, but continuing cleanup")
        except Exception as e:
            msg = f"Nginx reload failed: {str(e)}"
            logger.warning(msg)
            # Don't add to critical errors - nginx reload can fail if not critical
        
        # Step 5: Remove site directory
        try:
            if os.path.exists(self.site_dir):
                import shutil
                shutil.rmtree(self.site_dir)
                logger.info(f"Removed site directory: {self.site_dir}")
        except Exception as e:
            msg = f"Failed to remove site directory: {str(e)}"
            logger.error(msg)
            errors.append(msg)
        
        # Return success only if no critical errors
        if not errors:
            logger.info(f"Successfully destroyed site {self.domain}")
            return True
        else:
            logger.error(f"Destruction had errors: {'; '.join(errors)}")
            return False

    def wait_for_container_health(self, timeout=300, poll_interval=2):
        """Wait for container to be healthy and responding on its port.
        
        Default timeout is 300s (5 minutes) to accommodate:
        - Docker image downloads (30-120s on first deployment)
        - Dependency installation (npm install, pip install: 30-90s)
        - Application startup (5-10s)
        """
        import time
        import socket
        
        self.deployment_phase = 'checking_health'
        self.deployment_progress = 90
        self._add_deployment_log(f"Waiting for container to become healthy (timeout={timeout}s)...")
        logger.info(f"Waiting for container {self.domain} to become healthy (timeout={timeout}s)...")
        start_time = time.time()
        
        attempt = 0
        while time.time() - start_time < timeout:
            attempt += 1
            try:
                # Check if container is running
                container_name = f"{self.domain}-app"
                result = subprocess.run(
                    ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Status}}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and 'Up' in result.stdout:
                    # Container is up, now verify the app is responding to HTTP requests
                    import urllib.request
                    import urllib.error
                    try:
                        # Determine health check endpoint based on runtime
                        # PHP doesn't have /health, so check root instead
                        if self.runtime.lower().startswith('php'):
                            health_endpoint = '/'
                        else:
                            # Node.js and Python have /health endpoint
                            health_endpoint = '/health'
                        
                        req = urllib.request.Request(
                            f'http://127.0.0.1:{self.upstream_port}{health_endpoint}',
                            headers={'User-Agent': 'MRM-HealthCheck/1.0'}
                        )
                        try:
                            urllib.request.urlopen(req, timeout=2)
                        except urllib.error.HTTPError as http_err:
                            # HTTPError means the server responded (even if 404, 500, etc.)
                            # This is still "healthy" - the web server is running
                            # WordPress without DB config returns 500, which is fine for health check
                            pass
                        
                        # If we get here, the app is responding to HTTP requests
                        self._add_deployment_log(f"✓ Container is healthy and responding on port {self.upstream_port}")
                        logger.info(f"Container {self.domain} is healthy and responding on port {self.upstream_port}")
                        self.deployment_phase = 'healthy'
                        self.deployment_progress = 95
                        return True
                    except (urllib.error.URLError, ConnectionResetError, ConnectionRefusedError, OSError) as e:
                        # These errors mean the server is not responding yet (connection refused, timeout, etc.)
                        if attempt % 10 == 0:  # Log every 20 seconds
                            logger.debug(f"Health endpoint not ready: {e}")
                            self._add_deployment_log(f"Waiting for application to start responding on port {self.upstream_port}...")
                        pass
                else:
                    if attempt % 10 == 0:
                        self._add_deployment_log(f"Waiting for container to start...")
                
            except Exception as e:
                logger.debug(f"Health check attempt failed: {e}")
            
            time.sleep(poll_interval)
        
        self._add_deployment_log(f"ERROR: Container did not become healthy within {timeout}s")
        logger.error(f"Container {self.domain} did not become healthy within {timeout}s")
        return False
