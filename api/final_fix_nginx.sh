#!/bin/bash
# Final fix script - reloads nginx and tests the endpoint

set -e

echo "=== Final Nginx Fix for Liquidation Heatmap ==="
echo ""

# Test nginx config
echo "1. Testing nginx configuration..."
if sudo nginx -t; then
    echo "   ✅ Configuration is valid"
else
    echo "   ❌ Configuration has errors"
    exit 1
fi

echo ""
echo "2. Reloading nginx..."
if sudo systemctl reload nginx; then
    echo "   ✅ Nginx reloaded"
else
    echo "   ❌ Failed to reload nginx"
    exit 1
fi

echo ""
echo "3. Waiting 2 seconds for nginx to stabilize..."
sleep 2

echo ""
echo "4. Testing endpoints..."
echo ""

# Test the endpoint
HTTP_CODE=$(curl -s -o /tmp/liquidation_test.html -w "%{http_code}" https://api.wagmi-global.eu/liquidation-heatmap)
echo "   https://api.wagmi-global.eu/liquidation-heatmap"
echo "   HTTP Code: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    echo ""
    echo "   ✅ SUCCESS! Endpoint is working!"
    echo ""
    echo "   Response preview:"
    head -5 /tmp/liquidation_test.html
    rm -f /tmp/liquidation_test.html
elif [ "$HTTP_CODE" = "404" ]; then
    echo ""
    echo "   ❌ Still getting 404"
    echo ""
    echo "   Checking nginx error log..."
    sudo tail -20 /var/log/nginx/error.log | grep -i "liquidation\|8004" || echo "   No relevant errors found"
    echo ""
    echo "   Checking if API is running on port 8004..."
    if curl -s http://localhost:8004/ > /dev/null 2>&1; then
        echo "   ✅ API is running on port 8004"
    else
        echo "   ❌ API is NOT running on port 8004"
    fi
    echo ""
    echo "   Current location block configuration:"
    grep -A 3 "location /liquidation-heatmap" /etc/nginx/sites-available/scalper-agent | head -5
else
    echo ""
    echo "   Got unexpected HTTP code: $HTTP_CODE"
fi

echo ""
echo "=== Done ==="
