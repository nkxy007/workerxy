# Apache & Nginx Web Server Management

## Apache Configuration

### Installation

**Ubuntu:**
```bash
sudo apt update
sudo apt install apache2 -y
sudo systemctl enable apache2
sudo systemctl start apache2
```

**RedHat:**
```bash
sudo dnf install httpd -y
sudo systemctl enable httpd
sudo systemctl start httpd
```

### Virtual Hosts

**Ubuntu (`/etc/apache2/sites-available/example.com.conf`):**
```apache
<VirtualHost *:80>
    ServerName example.com
    ServerAlias www.example.com
    DocumentRoot /var/www/example.com
    
    <Directory /var/www/example.com>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    ErrorLog ${APACHE_LOG_DIR}/example.com-error.log
    CustomLog ${APACHE_LOG_DIR}/example.com-access.log combined
</VirtualHost>
```

Enable site:
```bash
sudo a2ensite example.com.conf
sudo systemctl reload apache2
```

**RedHat (`/etc/httpd/conf.d/example.com.conf`):**
```apache
<VirtualHost *:80>
    ServerName example.com
    ServerAlias www.example.com
    DocumentRoot /var/www/html/example.com
    
    <Directory /var/www/html/example.com>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    ErrorLog /var/log/httpd/example.com-error.log
    CustomLog /var/log/httpd/example.com-access.log combined
</VirtualHost>
```

Apply:
```bash
sudo systemctl reload httpd
```

### SSL/TLS Configuration

**With Let's Encrypt:**
```bash
# Ubuntu
sudo apt install certbot python3-certbot-apache -y
sudo certbot --apache -d example.com -d www.example.com

# RedHat
sudo dnf install certbot python3-certbot-apache -y
sudo certbot --apache -d example.com -d www.example.com

# Auto-renewal
sudo systemctl enable certbot-renew.timer
```

### Apache Modules

```bash
# Ubuntu
sudo a2enmod rewrite
sudo a2enmod ssl
sudo a2enmod headers
sudo a2dismod status
sudo systemctl reload apache2

# RedHat - edit /etc/httpd/conf.modules.d/
# LoadModule rewrite_module modules/mod_rewrite.so
sudo systemctl reload httpd
```

### Performance Tuning

Edit `/etc/apache2/mods-available/mpm_prefork.conf` (Ubuntu) or `/etc/httpd/conf.modules.d/00-mpm.conf` (RedHat):

```apache
<IfModule mpm_prefork_module>
    StartServers             5
    MinSpareServers          5
    MaxSpareServers         10
    MaxRequestWorkers      150
    MaxConnectionsPerChild   3000
</IfModule>
```

### Testing Configuration

```bash
# Ubuntu
sudo apache2ctl configtest
sudo apache2ctl -S  # Show virtual hosts

# RedHat
sudo httpd -t
sudo httpd -S
```

## Nginx Configuration

### Installation

**Ubuntu:**
```bash
sudo apt update
sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

**RedHat:**
```bash
sudo dnf install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Server Blocks (Virtual Hosts)

**Ubuntu/RedHat (`/etc/nginx/sites-available/example.com` or `/etc/nginx/conf.d/example.com.conf`):**

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;
    root /var/www/example.com;
    index index.html index.php;
    
    access_log /var/log/nginx/example.com-access.log;
    error_log /var/log/nginx/example.com-error.log;
    
    location / {
        try_files $uri $uri/ =404;
    }
    
    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php8.1-fpm.sock;
    }
    
    location ~ /\.ht {
        deny all;
    }
}
```

Enable (Ubuntu):
```bash
sudo ln -s /etc/nginx/sites-available/example.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

RedHat: Files in `/etc/nginx/conf.d/` are auto-loaded.

### SSL/TLS with Let's Encrypt

```bash
# Ubuntu
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d example.com -d www.example.com

# RedHat
sudo dnf install certbot python3-certbot-nginx -y
sudo certbot --nginx -d example.com -d www.example.com
```

### Reverse Proxy

```nginx
server {
    listen 80;
    server_name app.example.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Load Balancing

```nginx
upstream backend {
    least_conn;
    server backend1.example.com:8080;
    server backend2.example.com:8080;
    server backend3.example.com:8080;
}

server {
    listen 80;
    server_name lb.example.com;
    
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Performance Tuning

Edit `/etc/nginx/nginx.conf`:

```nginx
user nginx;
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # Basic settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss;
    
    # Client buffer settings
    client_body_buffer_size 128k;
    client_max_body_size 10m;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 16k;
    
    # File cache
    open_file_cache max=5000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;
}
```

### Testing Configuration

```bash
sudo nginx -t
sudo nginx -T  # Show full configuration
```

## Common Troubleshooting

### Apache Issues

**Check if running:**
```bash
sudo systemctl status apache2  # Ubuntu
sudo systemctl status httpd    # RedHat
```

**Check ports:**
```bash
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443
```

**Permission errors:**
```bash
# Set proper ownership
sudo chown -R www-data:www-data /var/www/example.com  # Ubuntu
sudo chown -R apache:apache /var/www/html/example.com # RedHat

# Set proper permissions
sudo find /var/www/example.com -type d -exec chmod 755 {} \;
sudo find /var/www/example.com -type f -exec chmod 644 {} \;
```

**View error logs:**
```bash
# Ubuntu
sudo tail -f /var/log/apache2/error.log

# RedHat
sudo tail -f /var/log/httpd/error_log
```

### Nginx Issues

**Check if running:**
```bash
sudo systemctl status nginx
```

**Permission errors:**
```bash
# Check nginx user in /etc/nginx/nginx.conf
# Set ownership
sudo chown -R nginx:nginx /var/www/example.com

# SELinux context (RedHat)
sudo chcon -R -t httpd_sys_content_t /var/www/example.com
sudo setsebool -P httpd_can_network_connect 1  # For reverse proxy
```

**View error logs:**
```bash
sudo tail -f /var/log/nginx/error.log
```

### SSL Certificate Issues

**Check certificate expiry:**
```bash
echo | openssl s_client -connect example.com:443 2>/dev/null | openssl x509 -noout -dates
```

**Test SSL configuration:**
```bash
openssl s_client -connect example.com:443 -tls1_2
```

**Certbot renewal:**
```bash
sudo certbot renew --dry-run
sudo systemctl status certbot-renew.timer
```

## Security Best Practices

### Apache Security Headers

Add to virtual host or in `/etc/apache2/conf-available/security.conf`:

```apache
# Enable headers module first
<IfModule mod_headers.c>
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set Permissions-Policy "geolocation=(), microphone=(), camera=()"
</IfModule>

# Hide Apache version
ServerTokens Prod
ServerSignature Off
```

### Nginx Security Headers

Add to server block:

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

# Hide Nginx version
server_tokens off;
```

### Rate Limiting (Nginx)

```nginx
http {
    limit_req_zone $binary_remote_addr zone=limitzone:10m rate=10r/s;
    
    server {
        location /api/ {
            limit_req zone=limitzone burst=20 nodelay;
        }
    }
}
```

## Monitoring & Logs

### Log Analysis

**Top requesting IPs:**
```bash
# Apache
sudo awk '{print $1}' /var/log/apache2/access.log | sort | uniq -c | sort -rn | head -20

# Nginx
sudo awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -20
```

**Response codes:**
```bash
# Apache
sudo awk '{print $9}' /var/log/apache2/access.log | sort | uniq -c | sort -rn

# Nginx
sudo awk '{print $9}' /var/log/nginx/access.log | sort | uniq -c | sort -rn
```

**Most requested URLs:**
```bash
# Apache
sudo awk '{print $7}' /var/log/apache2/access.log | sort | uniq -c | sort -rn | head -20

# Nginx
sudo awk '{print $7}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -20
```

### Status Modules

**Apache mod_status:**
```apache
<Location "/server-status">
    SetHandler server-status
    Require ip 127.0.0.1
</Location>
```

Access: `http://localhost/server-status`

**Nginx stub_status:**
```nginx
location /nginx_status {
    stub_status on;
    access_log off;
    allow 127.0.0.1;
    deny all;
}
```

Access: `http://localhost/nginx_status`