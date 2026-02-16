server {
    listen 80;
    server_name {{DOMAIN}} www.{{DOMAIN}};

    # Health check endpoint
    location /_mrm_probe {
        return 200 "mrm ok";
        add_header Content-Type text/plain;
    }

    # Proxy all requests to Docker container
    location / {
        proxy_pass http://127.0.0.1:{{UPSTREAM_PORT}};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Let's Encrypt challenge
    location ~ /\.well-known/acme-challenge/ {
        allow all;
    }

    access_log /var/log/nginx/{{DOMAIN}}.access.log;
    error_log /var/log/nginx/{{DOMAIN}}.error.log;
}