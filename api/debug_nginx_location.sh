#!/bin/bash
# Debug script to check nginx location matching

echo "=== Debugging Nginx Location Matching ==="
echo ""

echo "1. Checking if location blocks exist:"
grep -n "location.*liquidation-heatmap\|location.*api/heatmap" /etc/nginx/sites-available/scalper-agent

echo ""
echo "2. Testing direct backend connection:"
curl -s http://127.0.0.1:8004/ | head -3

echo ""
echo "3. Testing through nginx (should work if config is loaded):"
curl -s -H "Host: api.wagmi-global.eu" http://127.0.0.1/liquidation-heatmap 2>&1 | head -5

echo ""
echo "4. Checking nginx access log for recent requests:"
sudo tail -5 /var/log/nginx/access.log 2>/dev/null | grep -i liquidation || echo "No liquidation requests in log"

echo ""
echo "5. Checking for syntax issues in location block:"
sed -n '143,160p' /etc/nginx/sites-available/scalper-agent | grep -E "(proxy_pass|location|})"

echo ""
echo "6. Verifying location block is in HTTPS server block:"
awk '/listen 443 ssl/,/^}/ {if (/location \/liquidation-heatmap/) print "✅ Found in HTTPS block at line", NR}' /etc/nginx/sites-available/scalper-agent
