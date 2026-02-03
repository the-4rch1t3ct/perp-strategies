#!/bin/bash
# Comprehensive script to verify and fix nginx configuration

NGINX_CONFIG="/etc/nginx/sites-available/scalper-agent"

echo "=== Verifying Nginx Configuration ==="
echo ""

# Check if location blocks exist
if grep -q "location /liquidation-heatmap" "$NGINX_CONFIG"; then
    echo "✅ Location blocks found"
    grep -n "location.*liquidation-heatmap\|location.*api/heatmap" "$NGINX_CONFIG"
else
    echo "❌ Location blocks NOT found"
    exit 1
fi

echo ""
echo "=== Checking proxy_pass configuration ==="
grep -A 1 "location /liquidation-heatmap" "$NGINX_CONFIG" | grep proxy_pass

echo ""
echo "=== Testing nginx configuration ==="
if sudo nginx -t; then
    echo ""
    echo "✅ Nginx configuration is valid"
    echo ""
    echo "=== Reloading nginx ==="
    if sudo systemctl reload nginx; then
        echo "✅ Nginx reloaded successfully"
        echo ""
        echo "=== Testing endpoints ==="
        sleep 2
        echo "Testing: https://api.wagmi-global.eu/liquidation-heatmap"
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://api.wagmi-global.eu/liquidation-heatmap)
        echo "HTTP Code: $HTTP_CODE"
        
        if [ "$HTTP_CODE" = "200" ]; then
            echo "✅ SUCCESS! The endpoint is working!"
        elif [ "$HTTP_CODE" = "404" ]; then
            echo "❌ Still getting 404. Checking logs..."
            echo ""
            echo "Recent nginx error log:"
            sudo tail -10 /var/log/nginx/error.log 2>/dev/null || echo "Cannot access error log"
        else
            echo "Got HTTP $HTTP_CODE"
        fi
    else
        echo "❌ Failed to reload nginx"
    fi
else
    echo "❌ Nginx configuration test failed"
    exit 1
fi
