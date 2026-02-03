#!/bin/bash
# Script to add liquidation-heatmap location blocks to nginx config

NGINX_CONFIG="/etc/nginx/sites-available/scalper-agent"

if [ ! -f "$NGINX_CONFIG" ]; then
    echo "Error: Nginx config not found at $NGINX_CONFIG"
    exit 1
fi

# Check if already added
if grep -q "location /liquidation-heatmap" "$NGINX_CONFIG"; then
    echo "Liquidation heatmap config already exists in nginx"
    exit 0
fi

# Create backup
cp "$NGINX_CONFIG" "${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
echo "Created backup: ${NGINX_CONFIG}.backup.*"

# Find the HTTPS server block for api.wagmi-global.eu (line 17)
# Find a good insertion point - before the root location / block
INSERT_LINE=$(grep -n "^    location / {" "$NGINX_CONFIG" | head -1 | cut -d: -f1)

if [ -z "$INSERT_LINE" ]; then
    # If no root location, find the closing brace of the server block
    INSERT_LINE=$(grep -n "^}" "$NGINX_CONFIG" | tail -1 | cut -d: -f1)
fi

if [ -z "$INSERT_LINE" ]; then
    echo "Error: Could not find insertion point"
    exit 1
fi

echo "Will insert at line $INSERT_LINE"

# Read the config to add
CONFIG_CONTENT=$(cat <<'EOF'
    # Liquidation Heatmap API endpoints (port 8004)
    location /liquidation-heatmap {
        proxy_pass http://127.0.0.1:8004;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
    }

    location ~ ^/liquidation-heatmap/(.+)$ {
        proxy_pass http://127.0.0.1:8004/$1;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }

    location /api/heatmap {
        proxy_pass http://127.0.0.1:8004/api/heatmap;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }

    location ~ ^/api/heatmap/(.+)$ {
        proxy_pass http://127.0.0.1:8004/api/heatmap/$1;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }

EOF
)

# Insert the config
sed -i "${INSERT_LINE}i\\${CONFIG_CONTENT}" "$NGINX_CONFIG"

echo "Added liquidation-heatmap configuration to nginx"
echo ""
echo "Please run:"
echo "  sudo nginx -t"
echo "  sudo systemctl reload nginx"
