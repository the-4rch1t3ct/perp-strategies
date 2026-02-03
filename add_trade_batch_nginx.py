#!/usr/bin/env python3
"""
Add /api/trade route to Nginx configuration
Run with: sudo python3 add_trade_batch_nginx.py
"""

import sys
import subprocess

NGINX_CONFIG = "/etc/nginx/sites-available/default"

# Location block to add
LOCATION_BLOCK = """    location /api/trade {
        proxy_pass http://127.0.0.1:8004/api/trade;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }
"""

try:
    # Read current config
    with open(NGINX_CONFIG, 'r') as f:
        lines = f.readlines()
    
    # Check if already exists
    if any('location /api/trade' in line for line in lines):
        print("⚠️  Route /api/trade already exists")
        sys.exit(0)
    
    # Find /api/symbols location block
    symbols_line = None
    for i, line in enumerate(lines):
        if 'location /api/symbols' in line:
            symbols_line = i
            break
    
    if symbols_line is None:
        print("❌ Could not find /api/symbols location block")
        sys.exit(1)
    
    # Find the closing brace of /api/symbols block
    insert_line = None
    brace_count = 0
    for i in range(symbols_line, len(lines)):
        line = lines[i]
        if '{' in line:
            brace_count += line.count('{')
        if '}' in line:
            brace_count -= line.count('}')
            if brace_count == 0:
                insert_line = i + 1
                break
    
    if insert_line is None:
        print("❌ Could not find end of /api/symbols block")
        sys.exit(1)
    
    # Insert the new location block
    lines.insert(insert_line, LOCATION_BLOCK)
    
    # Write back
    with open(NGINX_CONFIG, 'w') as f:
        f.writelines(lines)
    
    print(f"✅ Added /api/trade route at line {insert_line + 1}")
    
    # Test Nginx config
    print("🔍 Testing Nginx configuration...")
    result = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Nginx config is valid")
        print("🔄 Reloading Nginx...")
        reload_result = subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True, text=True)
        if reload_result.returncode == 0:
            print("✅ Nginx reloaded - /api/trade/batch endpoint should now work")
            print("\nTest with:")
            print("curl 'https://api.wagmi-global.eu/api/trade/batch?min_strength=0.6&max_distance=3.0'")
        else:
            print(f"❌ Failed to reload Nginx: {reload_result.stderr}")
            sys.exit(1)
    else:
        print(f"❌ Nginx config test failed:\n{result.stderr}")
        sys.exit(1)
        
except PermissionError:
    print("❌ Permission denied - run with sudo:")
    print("sudo python3 add_trade_batch_nginx.py")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
