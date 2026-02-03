#!/bin/bash
# Final comprehensive fix for nginx liquidation-heatmap

set -e

NGINX_CONFIG="/etc/nginx/sites-available/scalper-agent"

echo "=== Final Nginx Fix ==="
echo ""

# Backup
cp "$NGINX_CONFIG" "${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
echo "✅ Created backup"

# Use Python to do the replacement (more reliable than sed)
python3 << 'PYTHON_SCRIPT'
import re
import shutil
from datetime import datetime

config_file = '/etc/nginx/sites-available/scalper-agent'

# Read config
with open(config_file, 'r') as f:
    content = f.read()

# Replace the location block
# Change: location /liquidation-heatmap {
# To: location = /liquidation-heatmap { (exact match) + redirect
# And: location /liquidation-heatmap/ { (for trailing slash)

pattern = r'(\s+)location /liquidation-heatmap \{'
replacement = r'''\1location = /liquidation-heatmap {
\1    return 301 /liquidation-heatmap/;
\1}
\1
\1location /liquidation-heatmap/ {'''

fixed_content = re.sub(pattern, replacement, content)

# Write fixed config
with open(config_file, 'w') as f:
    f.write(fixed_content)

print("✅ Updated location block to use exact match + trailing slash handler")
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
        HTTP_CODE=$(curl -s -o /tmp/test_response.html -w "%{http_code}" https://api.wagmi-global.eu/liquidation-heatmap)
        echo "HTTP Code: $HTTP_CODE"
        
        if [ "$HTTP_CODE" = "200" ]; then
            echo ""
            echo "🎉 SUCCESS! Endpoint is working!"
            head -3 /tmp/test_response.html
        elif [ "$HTTP_CODE" = "301" ]; then
            echo "Got redirect (301) - checking redirect location..."
            curl -s -I https://api.wagmi-global.eu/liquidation-heatmap 2>&1 | grep -i location
        else
            echo ""
            echo "Still getting $HTTP_CODE"
            echo ""
            echo "Checking if API is running..."
            if curl -s http://localhost:8004/ > /dev/null 2>&1; then
                echo "✅ API is running on port 8004"
            else
                echo "❌ API is NOT running"
            fi
        fi
        rm -f /tmp/test_response.html
    else
        echo "❌ Failed to reload nginx"
    fi
else
    echo "❌ Configuration test failed"
    exit 1
fi
