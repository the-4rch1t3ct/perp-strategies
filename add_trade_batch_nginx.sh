#!/bin/bash
# Add /api/trade route to Nginx configuration
# Run with: sudo bash add_trade_batch_nginx.sh

NGINX_CONFIG="/etc/nginx/sites-available/default"

# Check if route already exists
if grep -q "location /api/trade" "$NGINX_CONFIG"; then
    echo "⚠️  Route /api/trade already exists"
    nginx -t && systemctl reload nginx
    exit 0
fi

# Find line number after /api/symbols closing brace
LINE_NUM=$(grep -n "location /api/symbols" "$NGINX_CONFIG" | tail -1 | cut -d: -f1)
if [ -z "$LINE_NUM" ]; then
    echo "❌ Could not find /api/symbols location block"
    exit 1
fi

# Find the closing brace of /api/symbols block (should be around line + 14)
END_LINE=$((LINE_NUM + 14))
INSERT_LINE=$((END_LINE + 1))

# Create the location block to insert
LOCATION_BLOCK="    location /api/trade {
        proxy_pass http://127.0.0.1:8004/api/trade;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$server_name;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }
"

# Use sed to insert after the /api/symbols block
sed -i "${INSERT_LINE}a\\${LOCATION_BLOCK}" "$NGINX_CONFIG"

if [ $? -eq 0 ]; then
    echo "✅ Added /api/trade route to Nginx config"
    echo "🔍 Testing Nginx configuration..."
    nginx -t
    if [ $? -eq 0 ]; then
        echo "✅ Nginx config is valid"
        echo "🔄 Reloading Nginx..."
        systemctl reload nginx
        echo "✅ Nginx reloaded - /api/trade/batch endpoint should now work"
        echo ""
        echo "Test with: curl 'https://api.wagmi-global.eu/api/trade/batch?min_strength=0.6&max_distance=3.0'"
    else
        echo "❌ Nginx config test failed - check the configuration"
        exit 1
    fi
else
    echo "❌ Failed to update Nginx configuration"
    exit 1
fi
