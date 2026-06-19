# TaxiOps Deployment Guide

This guide covers deploying TaxiOps to various environments.

## Quick Start (Local Development)

```bash
# Install dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

Visit `http://localhost:8000`

## Environment Variables

Create a `.env` file in the project root with these variables:

```env
# Required
SECRET_KEY=your-secret-key-here-min-32-chars
DATABASE_URL=sqlite:///./taxi_ops.db

# Optional
ENVIRONMENT=development
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
ACCESS_TOKEN_EXPIRE_MINUTES=720
REFRESH_TOKEN_EXPIRE_DAYS=30
```

### Generating a Secret Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Production Deployment

### Prerequisites

- Ubuntu 20.04+ or similar Linux distribution
- Python 3.11+
- Nginx
- Supervisor or systemd (for process management)
- Domain name with DNS configured

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip nginx

# Create application user
sudo useradd -m -s /bin/bash taxiops
sudo su - taxiops
```

### 2. Application Setup

```bash
# Clone repository
git clone <repository-url> /home/taxiops/taxi-ops
cd /home/taxiops/taxi-ops

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -e .

# Create production .env file
nano .env
```

Production `.env`:
```env
SECRET_KEY=<generated-secret-key>
DATABASE_URL=sqlite:////home/taxiops/taxi-ops/taxi_ops.db
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://yourdomain.com
ACCESS_TOKEN_EXPIRE_MINUTES=720
REFRESH_TOKEN_EXPIRE_DAYS=30
```

```bash
# Run migrations
alembic upgrade head

# Create database backup directory
mkdir -p /home/taxiops/backups

# Exit taxiops user
exit
```

### 3. Gunicorn Configuration

Create `/home/taxiops/taxi-ops/gunicorn_config.py`:

```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
keepalive = 120
timeout = 120
accesslog = "/home/taxiops/taxi-ops/logs/access.log"
errorlog = "/home/taxiops/taxi-ops/logs/error.log"
loglevel = "info"
```

```bash
# Create logs directory
sudo mkdir -p /home/taxiops/taxi-ops/logs
sudo chown -R taxiops:taxiops /home/taxiops/taxi-ops/logs
```

### 4. Systemd Service

Create `/etc/systemd/system/taxiops.service`:

```ini
[Unit]
Description=TaxiOps Gunicorn Application
After=network.target

[Service]
Type=notify
User=taxiops
Group=taxiops
WorkingDirectory=/home/taxiops/taxi-ops
Environment="PATH=/home/taxiops/taxi-ops/venv/bin"
ExecStart=/home/taxiops/taxi-ops/venv/bin/gunicorn app.main:app -c /home/taxiops/taxi-ops/gunicorn_config.py
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable taxiops
sudo systemctl start taxiops
sudo systemctl status taxiops
```

### 5. Nginx Configuration

Create `/etc/nginx/sites-available/taxiops`:

```nginx
upstream taxiops_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (use certbot to generate)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;

    client_max_body_size 10M;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    location / {
        proxy_pass http://taxiops_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed in future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static {
        alias /home/taxiops/taxi-ops/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://taxiops_app;
    }
}
```

Enable site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/taxiops /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. SSL Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Generate certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

## Database Backups

### Automated Daily Backups

Create `/home/taxiops/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/taxiops/backups"
DB_FILE="/home/taxiops/taxi-ops/taxi_ops.db"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/taxi_ops_$DATE.db"

# Create backup
cp $DB_FILE $BACKUP_FILE
gzip $BACKUP_FILE

# Keep only last 30 days of backups
find $BACKUP_DIR -name "taxi_ops_*.db.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

```bash
chmod +x /home/taxiops/backup.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e -u taxiops
# Add line:
0 2 * * * /home/taxiops/backup.sh
```

## Monitoring

### Application Logs

```bash
# View application logs
sudo journalctl -u taxiops -f

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# View Gunicorn logs
tail -f /home/taxiops/taxi-ops/logs/access.log
tail -f /home/taxiops/taxi-ops/logs/error.log
```

### Health Check

Add a health check endpoint if not already present in `app/main.py`:

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

## Updating the Application

```bash
# SSH into server
ssh user@yourdomain.com
sudo su - taxiops

cd /home/taxiops/taxi-ops

# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install any new dependencies
pip install -e .

# Run migrations
alembic upgrade head

# Exit taxiops user
exit

# Restart application
sudo systemctl restart taxiops

# Check status
sudo systemctl status taxiops
```

## Rollback Procedure

```bash
sudo su - taxiops
cd /home/taxiops/taxi-ops

# Checkout previous version
git log --oneline -10
git checkout <previous-commit-hash>

# Rollback migrations if needed
alembic downgrade -1

# Exit and restart
exit
sudo systemctl restart taxiops
```

## Performance Tuning

### Gunicorn Workers

Calculate optimal workers:
```
workers = (2 × CPU cores) + 1
```

For 2 CPU cores: 5 workers
For 4 CPU cores: 9 workers

### SQLite Optimization

Add to your application startup in `app/database.py`:

```python
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=10000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()
```

## Troubleshooting

### Application won't start

```bash
# Check logs
sudo journalctl -u taxiops -n 50

# Check if port is in use
sudo netstat -tulpn | grep 8000

# Verify file permissions
ls -la /home/taxiops/taxi-ops
```

### Database locked errors

```bash
# Check for stale lock files
ls -la /home/taxiops/taxi-ops/*.db*

# Ensure WAL mode is enabled
sqlite3 taxi_ops.db "PRAGMA journal_mode=WAL;"
```

### High memory usage

```bash
# Monitor resources
htop

# Reduce Gunicorn workers
# Edit gunicorn_config.py and restart
sudo systemctl restart taxiops
```

## Security Checklist

- [ ] Strong SECRET_KEY generated and set
- [ ] DEBUG=false in production
- [ ] HTTPS enabled with valid SSL certificate
- [ ] Firewall configured (UFW or iptables)
- [ ] SSH key-based authentication
- [ ] Regular security updates
- [ ] Database backups automated
- [ ] Application user with limited privileges
- [ ] CORS configured for specific origins only
- [ ] Rate limiting enabled (if applicable)

## Scaling Considerations

For larger deployments:

1. **Database**: Consider migrating to PostgreSQL for better concurrent write performance
2. **Caching**: Add Redis for session storage and caching
3. **Load Balancing**: Use multiple application servers behind a load balancer
4. **CDN**: Serve static assets via CloudFlare or similar
5. **Monitoring**: Implement Prometheus + Grafana for metrics
6. **Logging**: Centralized logging with ELK stack or similar

## Support

For deployment issues, check:
- Application logs: `sudo journalctl -u taxiops -f`
- Nginx logs: `/var/log/nginx/`
- Gunicorn logs: `/home/taxiops/taxi-ops/logs/`
