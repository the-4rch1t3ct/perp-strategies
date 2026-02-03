# How to Work Around Sudo Limitations

## Option 1: Run Commands Yourself (Recommended)
I'll provide you with exact commands to run. Just copy-paste them into your terminal.

## Option 2: Use Helper Scripts
I've created scripts you can run with sudo:

### Check Nginx Errors
```bash
sudo bash memecoin-perp-strategies/api/check_nginx_errors.sh
```
This will show you the exact error causing the 502.

### Fix Nginx Configuration
```bash
sudo bash memecoin-perp-strategies/api/fix_nginx.sh
```
This will diagnose and help fix the configuration.

## Option 3: Grant Passwordless Sudo (Advanced)
If you want me to run sudo commands directly, you could configure passwordless sudo for specific commands. **Only do this if you trust me and understand the security implications.**

### Option 3a: NOPASSWD for specific commands
Edit sudoers (use `visudo` - never edit directly!):
```bash
sudo visudo
```

Add this line (replace `botadmin` with your actual username):
```
botadmin ALL=(ALL) NOPASSWD: /usr/sbin/nginx, /bin/systemctl reload nginx, /bin/tail /var/log/nginx/error.log
```

### Option 3b: Add to sudoers.d (safer)
```bash
echo "botadmin ALL=(ALL) NOPASSWD: /usr/sbin/nginx, /bin/systemctl reload nginx, /bin/tail /var/log/nginx/error.log" | sudo tee /etc/sudoers.d/botadmin-nginx
sudo chmod 440 /etc/sudoers.d/botadmin-nginx
```

**⚠️ Security Warning**: This allows passwordless sudo for nginx commands. Only do this if:
- You trust the AI assistant
- You're on a secure system
- You understand the risks

## Recommended Approach
**Just run the commands I provide** - it's safer and you maintain full control. I'll give you:
1. Exact commands to copy-paste
2. Expected output
3. What to do if something goes wrong

## Current Issue: 502 Bad Gateway
The most important thing right now is to see the nginx error log:

```bash
sudo tail -50 /var/log/nginx/error.log
```

This will tell us exactly why nginx can't connect to the API. Then I can provide the exact fix!
