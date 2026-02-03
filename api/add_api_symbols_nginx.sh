#!/bin/bash
# Add /api/symbols location block to default nginx config

set -e

DEFAULT_CONFIG="/etc/nginx/sites-available/default"

echo "=== Adding /api/symbols Location Block ==="
echo ""

# Use Python to add the location block
python3 << 'PYTHON_SCRIPT'
import re
from datetime import datetime

config_file = '/etc/nginx/sites-available/default'

# Read config
with open(config_file, 'r') as f:
    content = f.read()

# Check if /api/symbols location already exists
if 'location /api/symbols' in content:
    print("✅ /api/symbols location already exists")
    exit(0)

# Find where to insert - after the last /api/heatmap location block
# Look for the pattern: location ~ ^/api/heatmap/(.+)$
pattern = r'(location ~ \^/api/heatmap/\(\.\+\)\$[^}]+})'
match = re.search(pattern, content, re.DOTALL)

if not match:
    print("❌ Could not find /api/heatmap location block")
    exit(1)

insert_pos = match.end()

# Create the /api/symbols location block
symbols_block = '''
   location /api/symbols {
       proxy_pass http://127.0.0.1:8004/api/symbols;
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

# Insert after the last /api/heatmap block
new_content = content[:insert_pos] + symbols_block + content[insert_pos:]

# Write back
with open(config_file, 'w') as f:
    f.write(new_content)

print("✅ Added /api/symbols location block")
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
        echo "Testing /api/symbols endpoint..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://api.wagmi-global.eu/api/symbols)
        echo "HTTP Code: $HTTP_CODE"
        
        if [ "$HTTP_CODE" = "200" ]; then
            echo ""
            echo "🎉 SUCCESS! /api/symbols endpoint is working!"
            curl -s https://api.wagmi-global.eu/api/symbols | python3 -m json.tool | head -10
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
