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
    command: sh -c "npm install --prefer-offline --no-audit && npm start"
    environment:
      - NODE_ENV=production
      - PORT={{CONTAINER_PORT}}
