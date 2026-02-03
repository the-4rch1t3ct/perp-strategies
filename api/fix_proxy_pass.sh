#!/bin/bash
# Fix proxy_pass to strip the /liquidation-heatmap prefix

NGINX_CONFIG="/etc/nginx/sites-available/scalper-agent"

# Create backup
cp "$NGINX_CONFIG" "${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"

# Fix the proxy_pass - add trailing slash to strip prefix
sed -i 's|proxy_pass http://127.0.0.1:8004;|proxy_pass http://127.0.0.1:8004/;|' "$NGINX_CONFIG"

echo "✅ Fixed proxy_pass configuration"
echo ""
echo "Please run:"
echo "  sudo nginx -t"
echo "  sudo systemctl reload nginx"
