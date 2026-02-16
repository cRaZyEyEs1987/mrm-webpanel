version: '3.8'
services:
  app:
    image: {{DOCKER_IMAGE}}
    container_name: {{DOMAIN}}-app
    restart: unless-stopped
    working_dir: /var/www/html
    volumes:
      - {{SITE_DIR}}:/var/www/html
    ports:
      - "{{UPSTREAM_PORT}}:{{CONTAINER_PORT}}"
    environment:
      - APACHE_DOCUMENT_ROOT=/var/www/html
