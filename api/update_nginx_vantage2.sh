#!/bin/bash
# Script to update nginx config for /vantage2/ endpoint

echo "=== Updating Nginx Configuration for /vantage2/ Endpoint ==="
echo ""

# Find nginx config location
NGINX_CONFIG=""
if [ -f "/etc/nginx/sites-available/api.wagmi-global.eu" ]; then
    NGINX_CONFIG="/etc/nginx/sites-available/api.wagmi-global.eu"
elif [ -f "/etc/nginx/conf.d/api.wagmi-global.eu.conf" ]; then
    NGINX_CONFIG="/etc/nginx/conf.d/api.wagmi-global.eu.conf"
elif [ -f "/etc/nginx/sites-enabled/api.wagmi-global.eu" ]; then
    NGINX_CONFIG="/etc/nginx/sites-enabled/api.wagmi-global.eu"
else
    echo "❌ Could not find nginx config file"
    echo "Please manually update your nginx config with the content from:"
    echo "  /home/botadmin/memecoin-perp-strategies/api/nginx_wagmi_indicators.conf"
    exit 1
fi

echo "Found nginx config: $NGINX_CONFIG"
echo ""

# Check if /vantage2/ location already exists
if grep -q "location /vantage2/" "$NGINX_CONFIG" 2>/dev/null; then
    echo "⚠️  /vantage2/ location already exists in config"
    echo "Skipping update. If it's not working, check the config manually."
else
    echo "✅ /vantage2/ location not found, needs to be added"
    echo ""
    echo "To add it manually:"
    echo "1. Edit: $NGINX_CONFIG"
    echo "2. Add the /vantage2/ location block BEFORE the 'location /' block"
    echo "3. See: /home/botadmin/memecoin-perp-strategies/api/nginx_vantagev2_patch.txt"
    echo ""
    echo "Or copy the full updated config:"
    echo "  sudo cp /home/botadmin/memecoin-perp-strategies/api/nginx_wagmi_indicators.conf $NGINX_CONFIG"
fi

echo ""
echo "After updating, run:"
echo "  sudo nginx -t"
echo "  sudo systemctl reload nginx"
