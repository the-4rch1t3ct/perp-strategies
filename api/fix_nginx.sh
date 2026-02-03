#!/bin/bash
# Script to fix nginx configuration for /vantage2/ endpoint
# Run with: sudo bash fix_nginx.sh

set -e

NGINX_CONFIG="/etc/nginx/sites-available/default"
BACKUP_FILE="/etc/nginx/sites-available/default.backup.$(date +%Y%m%d_%H%M%S)"

echo "=== Nginx Configuration Fix Script ==="
echo ""

# Backup current config
echo "1. Creating backup: $BACKUP_FILE"
cp "$NGINX_CONFIG" "$BACKUP_FILE"
echo "   ✅ Backup created"

# Find the line number for server_name api.wagmi-global.eu
LINE_NUM=$(grep -n "server_name api.wagmi-global.eu" "$NGINX_CONFIG" | head -1 | cut -d: -f1)
echo "2. Found api.wagmi-global.eu server block at line $LINE_NUM"

# Check if location /vantage2/ already exists
if grep -q "location /vantage2/" "$NGINX_CONFIG"; then
    echo "3. Location /vantage2/ block found"
    VANTAGE_LINE=$(grep -n "location /vantage2/" "$NGINX_CONFIG" | head -1 | cut -d: -f1)
    echo "   Found at line $VANTAGE_LINE"
    
    # Check if it's in the correct server block (should be after LINE_NUM)
    if [ "$VANTAGE_LINE" -gt "$LINE_NUM" ]; then
        echo "   ✅ Location block is in correct server block"
        echo ""
        echo "4. Checking nginx error logs..."
        echo "   Recent errors:"
        tail -20 /var/log/nginx/error.log 2>/dev/null | grep -i "vantage\|8003\|502" || echo "   No recent errors found"
    else
        echo "   ⚠️  Location block might be in wrong server block"
    fi
else
    echo "3. ⚠️  Location /vantage2/ block NOT found"
fi

echo ""
echo "5. Testing nginx configuration..."
if nginx -t; then
    echo "   ✅ Configuration is valid"
else
    echo "   ❌ Configuration has errors!"
    exit 1
fi

echo ""
echo "6. Checking if API is accessible..."
if curl -s -m 3 http://127.0.0.1:8003/vantage2/fundingOI > /dev/null; then
    echo "   ✅ API is responding on port 8003"
else
    echo "   ❌ API is NOT responding on port 8003"
    echo "   Check if vantagev2_api.py is running"
fi

echo ""
echo "=== Next Steps ==="
echo "If configuration is valid, reload nginx:"
echo "  sudo systemctl reload nginx"
echo ""
echo "Then test the endpoint:"
echo "  curl https://api.wagmi-global.eu/vantage2/fundingOI"
echo ""
echo "If still getting 502, check error logs:"
echo "  sudo tail -f /var/log/nginx/error.log"
