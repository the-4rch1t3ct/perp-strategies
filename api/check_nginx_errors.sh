#!/bin/bash
# Quick script to check nginx error logs
# Run with: sudo bash check_nginx_errors.sh

echo "=== Nginx Error Log (last 50 lines) ==="
tail -50 /var/log/nginx/error.log

echo ""
echo "=== Filtering for vantage/8003/502 errors ==="
tail -100 /var/log/nginx/error.log | grep -i "vantage\|8003\|502\|bad gateway" || echo "No matching errors found"

echo ""
echo "=== Testing API connectivity ==="
echo "From current user:"
curl -s -m 3 http://127.0.0.1:8003/vantage2/fundingOI | head -c 100 || echo "FAILED"

echo ""
echo "From www-data user (nginx worker):"
sudo -u www-data curl -s -m 3 http://127.0.0.1:8003/vantage2/fundingOI | head -c 100 || echo "FAILED - nginx user cannot connect"
