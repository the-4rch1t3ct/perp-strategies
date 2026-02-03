#!/bin/bash
# Setup script for Liquidation Heatmap nginx configuration

echo "Setting up Liquidation Heatmap nginx configuration..."
echo ""

# Find nginx config file
NGINX_CONFIG=""
if [ -f "/etc/nginx/sites-available/scalper-agent" ]; then
    NGINX_CONFIG="/etc/nginx/sites-available/scalper-agent"
elif [ -f "/etc/nginx/sites-available/api.wagmi-global.eu" ]; then
    NGINX_CONFIG="/etc/nginx/sites-available/api.wagmi-global.eu"
elif [ -f "/etc/nginx/sites-enabled/api.wagmi-global.eu" ]; then
    NGINX_CONFIG="/etc/nginx/sites-enabled/api.wagmi-global.eu"
elif [ -f "/etc/nginx/conf.d/api.wagmi-global.eu.conf" ]; then
    NGINX_CONFIG="/etc/nginx/conf.d/api.wagmi-global.eu.conf"
fi

if [ -z "$NGINX_CONFIG" ]; then
    echo "❌ Could not find nginx config file"
    echo "Please manually add the configuration from:"
    echo "  /home/botadmin/memecoin-perp-strategies/api/nginx_liquidation_heatmap.conf"
    exit 1
fi

echo "✅ Found nginx config: $NGINX_CONFIG"
echo ""

# Check if configuration already exists
if grep -q "liquidation-heatmap" "$NGINX_CONFIG"; then
    echo "⚠️  Liquidation heatmap configuration already exists"
    echo "Skipping..."
else
    echo "Adding liquidation heatmap configuration..."
    
    # Find the server block for api.wagmi-global.eu
    if grep -q "server_name api.wagmi-global.eu" "$NGINX_CONFIG"; then
        # Find the line number of the closing brace before the last location block
        # We'll add it before the root location block
        
        # Create backup
        cp "$NGINX_CONFIG" "${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "✅ Created backup: ${NGINX_CONFIG}.backup.*"
        
        # Read the config to add
        CONFIG_CONTENT=$(cat /home/botadmin/memecoin-perp-strategies/api/nginx_liquidation_heatmap.conf)
        
        # Find insertion point (before root location /)
        INSERT_LINE=$(grep -n "location / {" "$NGINX_CONFIG" | head -1 | cut -d: -f1)
        
        if [ -n "$INSERT_LINE" ]; then
            # Insert before root location
            sed -i "${INSERT_LINE}i\\$CONFIG_CONTENT" "$NGINX_CONFIG"
            echo "✅ Added configuration at line $INSERT_LINE"
        else
            # Append to end of server block (before closing brace)
            sed -i '/^}/i\\'"$CONFIG_CONTENT" "$NGINX_CONFIG"
            echo "✅ Added configuration before server block closing"
        fi
    else
        echo "⚠️  Could not find api.wagmi-global.eu server block"
        echo "Please manually add the configuration from:"
        echo "  /home/botadmin/memecoin-perp-strategies/api/nginx_liquidation_heatmap.conf"
        exit 1
    fi
fi

echo ""
echo "Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Nginx configuration is valid"
    echo ""
    read -p "Reload nginx? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl reload nginx
        echo "✅ Nginx reloaded"
    else
        echo "⚠️  Nginx not reloaded. Run manually: sudo systemctl reload nginx"
    fi
else
    echo ""
    echo "❌ Nginx configuration test failed"
    echo "Please check the configuration manually"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Access the UI at:"
echo "  https://api.wagmi-global.eu/liquidation-heatmap"
echo ""
echo "API endpoints:"
echo "  https://api.wagmi-global.eu/api/heatmap/BTCUSDT"
echo "  https://api.wagmi-global.eu/api/heatmap/BTCUSDT/best"
echo "  https://api.wagmi-global.eu/api/heatmap/symbols"
echo ""
echo "Test with:"
echo "  curl https://api.wagmi-global.eu/api/heatmap/BTCUSDT"
