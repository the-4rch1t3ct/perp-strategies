#!/bin/bash
# Fix nginx config to use exact match for liquidation-heatmap

NGINX_CONFIG="/etc/nginx/sites-available/scalper-agent"

# Backup
cp "$NGINX_CONFIG" "${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"

# Replace prefix match with exact match
sed -i 's|location /liquidation-heatmap {|location = /liquidation-heatmap {\n        return 301 /liquidation-heatmap/;\n    }\n\n    location /liquidation-heatmap/ {|' "$NGINX_CONFIG"

# Actually, let's try a simpler approach - just change to exact match
# But first, let's add both exact matches
python3 << 'PYTHON'
import re
import shutil
from datetime import datetime

config_file = '/etc/nginx/sites-available/scalper-agent'
backup_file = f'{config_file}.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'

# Read config
with open(config_file, 'r') as f:
    content = f.read()

# Create backup
shutil.copy(config_file, backup_file)
print(f"Created backup: {backup_file}")

# Find and replace the location block
# Change from: location /liquidation-heatmap {
# To: location = /liquidation-heatmap { (exact match)
# And add: location /liquidation-heatmap/ { (for trailing slash)

# First, try exact match for the main path
pattern = r'(\s+)location /liquidation-heatmap \{'
replacement = r'\1location = /liquidation-heatmap {\n\1    return 301 /liquidation-heatmap/;\n\1}\n\n\1location /liquidation-heatmap/ {'

fixed_content = re.sub(pattern, replacement, content)

# Write fixed config
with open(config_file, 'w') as f:
    f.write(fixed_content)

print("✅ Changed to exact match + trailing slash handler")
print("\nNow:")
print("  location = /liquidation-heatmap { redirects to /liquidation-heatmap/")
print("  location /liquidation-heatmap/ { proxies to backend")
PYTHON

echo ""
echo "Testing nginx config..."
if sudo nginx -t; then
    echo "✅ Config is valid"
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
            echo "✅ SUCCESS!"
        else
            echo "Still getting $HTTP_CODE"
        fi
    fi
else
    echo "❌ Config test failed"
    exit 1
fi
