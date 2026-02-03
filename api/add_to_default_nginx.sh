#!/bin/bash
# Add liquidation-heatmap location blocks to default nginx config
# (since that's the one nginx is actually using)

set -e

DEFAULT_CONFIG="/etc/nginx/sites-available/default"

echo "=== Adding Liquidation Heatmap to Default Config ==="
echo ""

# Backup
cp "$DEFAULT_CONFIG" "${DEFAULT_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
echo "✅ Created backup"

# Use Python to add the location blocks
python3 << 'PYTHON_SCRIPT'
import re
from datetime import datetime

config_file = '/etc/nginx/sites-available/default'

# Read config
with open(config_file, 'r') as f:
    lines = f.readlines()

# Find the HTTPS server block with api.wagmi-global.eu (around line 114)
# Find insertion point - before the catch-all location / block (around line 127)
insert_line = None
for i, line in enumerate(lines):
    if i >= 120 and i < 130 and 'location / {' in line and 'vantage2' not in lines[i-10:i]:
        insert_line = i
        break

if not insert_line:
    # Fallback: find location / in HTTPS block
    for i, line in enumerate(lines):
        if i > 110 and 'location / {' in line:
            # Check if we're in HTTPS block (has api.wagmi-global.eu above)
            for j in range(max(0, i-20), i):
                if 'listen 443' in lines[j] and 'api.wagmi-global.eu' in ''.join(lines[j:i]):
                    insert_line = i
                    break
            if insert_line:
                break

if not insert_line:
    print("❌ Could not find insertion point")
    exit(1)

print(f"Will insert at line {insert_line + 1} (before location /)")

# Create the location blocks to insert
location_blocks = '''    # Liquidation Heatmap API endpoints (port 8004)
    location = /liquidation-heatmap {
        return 301 /liquidation-heatmap/;
    }

    location /liquidation-heatmap/ {
        proxy_pass http://127.0.0.1:8004/;
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

'''

# Insert the blocks
new_lines = lines[:insert_line] + [location_blocks] + lines[insert_line:]

# Write fixed config
with open(config_file, 'w') as f:
    f.writelines(new_lines)

print("✅ Added liquidation-heatmap location blocks to default config")
PYTHON_SCRIPT

echo ""
echo "Testing nginx configuration..."
if sudo nginx -t; then
    echo "✅ Configuration is valid"
    echo ""
    echo "Reloading nginx..."
    if sudo systemctl reload nginx; then
        echo "✅ Nginx reloaded"
        sleep 2
        echo ""
        echo "Testing endpoint..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://api.wagmi-global.eu/liquidation-heatmap)
        echo "HTTP Code: $HTTP_CODE"
        
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ]; then
            echo ""
            echo "🎉 SUCCESS! Endpoint is working!"
            curl -s https://api.wagmi-global.eu/liquidation-heatmap | head -5
        else
            echo "Still getting $HTTP_CODE"
        fi
    else
        echo "❌ Failed to reload nginx"
    fi
else
    echo "❌ Configuration test failed"
    exit 1
fi
