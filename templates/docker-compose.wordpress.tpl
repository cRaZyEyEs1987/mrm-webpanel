version: '3.8'

services:
  app:
    # WordPress with PHP-Apache (database will be configured later)
    image: wordpress:php8.2-apache
    container_name: {{DOMAIN}}-app
    restart: unless-stopped
    working_dir: /var/www/html
    environment:
      # Database config - currently empty, will be configured when DB integration added
      - WORDPRESS_DB_HOST=
      - WORDPRESS_DB_NAME=
      - WORDPRESS_DB_USER=
      - WORDPRESS_DB_PASSWORD=
    volumes:
      - {{SITE_DIR}}:/var/www/html
    ports:
      - "{{UPSTREAM_PORT}}:{{CONTAINER_PORT}}"
