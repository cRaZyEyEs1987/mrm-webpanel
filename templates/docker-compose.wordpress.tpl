version: '3.8'

services:
  app:
    # WordPress with PHP-Apache
    image: wordpress:php8.2-apache
    container_name: {{DOMAIN}}-app
    restart: unless-stopped
    network_mode: bridge
    working_dir: /var/www/html
    environment:
      # Database configuration
      - WORDPRESS_DB_HOST={{WP_DB_HOST}}
      - WORDPRESS_DB_NAME={{WP_DB_NAME}}
      - WORDPRESS_DB_USER={{WP_DB_USER}}
      - WORDPRESS_DB_PASSWORD={{WP_DB_PASSWORD}}
      # WordPress admin credentials for auto-install
      - WORDPRESS_ADMIN_USER={{WP_ADMIN_USER}}
      - WORDPRESS_ADMIN_PASSWORD={{WP_ADMIN_PASS}}
      - WORDPRESS_ADMIN_EMAIL={{WP_ADMIN_EMAIL}}
      - WORDPRESS_SITE_URL={{WP_SITE_URL}}
      - WORDPRESS_SITE_TITLE={{DOMAIN}}
      - WORDPRESS_TABLE_PREFIX={{WP_TABLE_PREFIX}}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - {{SITE_DIR}}:/var/www/html
    ports:
      - "{{UPSTREAM_PORT}}:{{CONTAINER_PORT}}"
