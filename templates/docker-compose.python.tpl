version: '3.8'
services:
  app:
    image: {{DOCKER_IMAGE}}
    container_name: {{DOMAIN}}-app
    restart: unless-stopped
    working_dir: /app
    volumes:
      - {{SITE_DIR}}:/app
    ports:
      - "{{UPSTREAM_PORT}}:{{CONTAINER_PORT}}"
    command: sh -c "pip install -r requirements.txt && python3 app.py"
    environment:
      - PYTHONUNBUFFERED=1
      - PORT={{CONTAINER_PORT}}
