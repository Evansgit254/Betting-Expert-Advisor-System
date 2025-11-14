# Deployment Guide

Complete deployment instructions for the Betting Expert Advisor system.

## Table of Contents
- [Replit Deployment](#replit-deployment)
- [Docker Deployment](#docker-deployment)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Production Checklist](#production-checklist)
- [Monitoring](#monitoring)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

---

## Replit Deployment

Replit provides native deployment with automatic SSL, domain management, and infrastructure.

### 1. Initial Setup
```bash
# The monitoring API runs automatically on workflow startup
# Default command: python -m src.main --mode serve --host 0.0.0.0 --port 5000
```

### 2. Configure Secrets
Navigate to **Secrets** in Replit sidebar and add:
```
ENV=production
MODE=DRY_RUN              # Start in DRY_RUN, switch to LIVE after validation
LOG_LEVEL=INFO
DB_URL=<your-postgres-url>  # Use Replit's PostgreSQL integration

# Optional: API Keys
THEODDS_API_KEY=<your-key>
BETFAIR_APP_KEY=<your-key>
BETFAIR_USERNAME=<username>
BETFAIR_PASSWORD=<password>

# Optional: Telegram Alerts
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<chat-id>
```

### 3. Deploy
1. Click **Deploy** button in Replit
2. Select **Reserved VM** deployment type (stateful monitoring API)
3. Configure autoscaling if needed
4. Click **Deploy** and wait for build

### 4. Access Your Application
- **Dashboard**: `https://<your-repl-name>.<your-username>.repl.co`
- **Health**: `https://<your-repl-name>.<your-username>.repl.co/health`
- **Metrics**: `https://<your-repl-name>.<your-username>.repl.co/metrics`

### Replit Deployment Configuration
The system uses Replit's native deployment (configured via deploy_config_tool):
- **Deployment Target**: Reserved VM (stateful, always-on)
- **Run Command**: `python -m src.main --mode serve --host 0.0.0.0 --port 5000`
- **Port**: 5000 (automatically exposed by Replit)

### Advantages of Replit Deployment
- ✅ Automatic HTTPS with valid SSL certificates
- ✅ Custom domain support
- ✅ Built-in secrets management
- ✅ Zero DevOps overhead
- ✅ Instant rollbacks via checkpoints
- ✅ Integrated database (PostgreSQL)

---

## Docker Deployment

For self-hosting outside Replit, use the provided Docker configuration.

### 1. Prerequisites
```bash
# Install Docker and Docker Compose
docker --version  # Should be 20.10+
docker-compose --version  # Should be 1.29+
```

### 2. Environment Configuration
```bash
# Create production environment file
cp .env.example .env.production

# Edit with your production values
nano .env.production
```

Example `.env.production`:
```bash
ENV=production
MODE=DRY_RUN
DB_URL=postgresql://betting_user:CHANGE_THIS_PASSWORD@db:5432/betting_advisor
LOG_LEVEL=INFO
LOG_FILE=logs/betting_advisor.log

# Risk Management
DEFAULT_KELLY_FRACTION=0.2
MAX_STAKE_FRAC=0.05
DAILY_LOSS_LIMIT=1000
MAX_CONSECUTIVE_LOSSES=5
MAX_OPEN_BETS=10

# API Keys
THEODDS_API_KEY=your_theodds_key
BETFAIR_APP_KEY=your_betfair_key
BETFAIR_USERNAME=your_username
BETFAIR_PASSWORD=your_password

# Telegram Alerts
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Start the Stack
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f monitoring

# Check service status
docker-compose ps
```

The stack includes:
- **PostgreSQL 15** - Production database (port 5432)
- **Redis 7** - Caching layer (port 6379)
- **Monitoring API** - FastAPI dashboard (port 5000)

### 4. Verify Deployment
```bash
# Check health endpoint
curl http://localhost:5000/health

# Access dashboard
open http://localhost:5000
```

### 5. Production Hardening

#### Add nginx Reverse Proxy
Create `nginx.conf`:
```nginx
upstream betting_api {
    server localhost:5000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req zone=api_limit burst=20 nodelay;

    location / {
        proxy_pass http://betting_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check endpoint (no auth)
    location /health {
        proxy_pass http://betting_api;
        access_log off;
    }
}
```

Start nginx:
```bash
# Test configuration
nginx -t

# Start nginx
systemctl start nginx
systemctl enable nginx
```

#### SSL Certificate (Let's Encrypt)
```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

---

## Environment Configuration

### Configuration Hierarchy
1. **Environment Variables** (highest priority)
2. **`.env` file** 
3. **Default values in `src/config.py`**

### Critical Settings

#### Mode Configuration
```bash
ENV=production      # development | production
MODE=DRY_RUN       # DRY_RUN | LIVE (start with DRY_RUN!)
```

#### Database Configuration
```bash
# Development (SQLite)
DB_URL=sqlite:///./data/betting_advisor.db

# Production (PostgreSQL)
DB_URL=postgresql://user:password@host:5432/dbname

# Replit PostgreSQL (automatically provided)
DB_URL=$DATABASE_URL  # Replit sets this automatically
```

#### Logging Configuration
```bash
LOG_LEVEL=INFO              # DEBUG | INFO | WARNING | ERROR | CRITICAL
LOG_FILE=logs/betting_advisor.log
```

---

## Database Setup

### PostgreSQL (Production)

#### Option 1: Replit Database
1. Click **Database** in Replit sidebar
2. Create new PostgreSQL database
3. Connection URL is automatically set as `$DATABASE_URL`

#### Option 2: External PostgreSQL
```bash
# Create database and user
psql -U postgres
CREATE DATABASE betting_advisor;
CREATE USER betting_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE betting_advisor TO betting_user;

# Run migrations
alembic upgrade head
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

---

## Production Checklist

### Pre-Deployment
- [ ] All tests passing: `pytest`
- [ ] Code formatted: `black src/ tests/` and `isort src/ tests/`
- [ ] Linting clean: `flake8 src/ tests/ --max-line-length=100`
- [ ] Security scan: `bandit -r src/`
- [ ] Dependencies updated: `pip list --outdated`

### Initial Production Setup
- [ ] Set `ENV=production` in environment
- [ ] Set `MODE=DRY_RUN` (never start with LIVE!)
- [ ] Configure PostgreSQL database
- [ ] Set all required API keys in secrets
- [ ] Configure Telegram alerting
- [ ] Review and adjust risk thresholds in `src/config.py`
- [ ] Set up nginx reverse proxy with HTTPS
- [ ] Configure database backups
- [ ] Set up log aggregation
- [ ] Configure monitoring and alerting

### Paper Trading Validation (Required Before LIVE)
- [ ] Run in `MODE=DRY_RUN` for minimum 30 days
- [ ] Monitor daily performance metrics
- [ ] Verify no critical errors in logs
- [ ] Validate risk management working correctly
- [ ] Confirm circuit breakers trigger appropriately
- [ ] Review all edge cases and error handling
- [ ] Analyze paper trading P&L and accuracy
- [ ] Document any issues encountered
- [ ] Get stakeholder sign-off

### Enabling LIVE Mode (After Validation)
- [ ] Legal compliance verified for jurisdiction
- [ ] All paper trading validation complete
- [ ] Monitoring and alerting tested
- [ ] Backup and recovery procedures tested
- [ ] Incident response plan documented
- [ ] Bankroll limits configured conservatively
- [ ] Team trained on operations
- [ ] Manual approval gate for MODE=LIVE change
- [ ] Gradual rollout plan prepared
- [ ] Rollback procedure documented

---

## Monitoring

### Health Checks
```bash
# Liveness (is the service up?)
curl http://localhost:5000/health

# Readiness (is the service ready to handle requests?)
curl http://localhost:5000/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-11-14T12:00:00",
  "mode": "DRY_RUN",
  "database": "connected",
  "circuit_breakers": {
    "theodds": "closed",
    "pinnacle": "closed",
    "betfair": "closed"
  }
}
```

### Prometheus Metrics
```bash
# View all metrics
curl http://localhost:5000/metrics

# Example metrics:
# betting_predictions_total - Total predictions made
# betting_bets_total - Total bets placed
# betting_errors_total - Total errors encountered
# betting_circuit_breaker_state - Circuit breaker states (0=closed, 1=open)
```

### Log Monitoring
```bash
# Follow application logs
tail -f logs/betting_advisor.log

# Search for errors
grep ERROR logs/betting_advisor.log

# Search by correlation ID
grep "correlation_id=abc123" logs/betting_advisor.log
```

### Telegram Alerts
Configure Telegram bot for critical alerts:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Alerts sent for:
- Daily loss limit approaching
- Consecutive loss threshold reached
- Circuit breaker opened
- Critical errors
- System startup/shutdown

---

## Backup & Recovery

### Database Backups

#### Automated Backup Script
Create `scripts/backup_db.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/betting-advisor"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="betting_advisor"
DB_USER="betting_user"

# Create backup directory
mkdir -p $BACKUP_DIR

# Dump database
pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_DIR/backup_$TIMESTAMP.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: backup_$TIMESTAMP.sql.gz"
```

#### Schedule with cron
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/scripts/backup_db.sh
```

#### Restore from Backup
```bash
# List available backups
ls -lh /var/backups/betting-advisor/

# Restore specific backup
gunzip -c /var/backups/betting-advisor/backup_20251114_020000.sql.gz | psql -U betting_user betting_advisor
```

### Application State Backup
```bash
# Backup critical directories
tar -czf betting_advisor_backup_$(date +%Y%m%d).tar.gz \
    data/ \
    models/ \
    logs/ \
    .env.production
```

---

## Troubleshooting

### Service Won't Start
```bash
# Check Docker logs
docker-compose logs monitoring

# Check Python syntax
python -m py_compile src/main.py

# Check database connection
docker-compose exec monitoring python -c "from src.db import init_db; init_db()"
```

### Database Connection Errors
```bash
# Test PostgreSQL connection
docker-compose exec db psql -U betting_user -d betting_advisor -c "SELECT 1;"

# Check database URL format
echo $DB_URL

# Verify database is running
docker-compose ps db
```

### Circuit Breakers Open
```bash
# Check circuit breaker status
curl http://localhost:5000/health | jq .circuit_breakers

# Circuit breakers auto-reset after 60 seconds
# Check external API status manually

# Review circuit breaker configuration
grep -A 5 "CIRCUIT_BREAKER" src/adapters/_circuit.py
```

### High Memory Usage
```bash
# Check container stats
docker stats betting-advisor-monitoring

# Restart service
docker-compose restart monitoring

# Check for memory leaks in logs
grep -i "memory" logs/betting_advisor.log
```

### Performance Issues
```bash
# Check database query performance
docker-compose exec db psql -U betting_user -d betting_advisor

# Enable query logging
SET log_statement = 'all';

# Check slow queries
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

# Optimize database
VACUUM ANALYZE;
```

---

## Scaling Considerations

### Horizontal Scaling
- Deploy multiple monitoring API instances behind load balancer
- Use PostgreSQL for shared state
- Redis for distributed caching
- Message queue (RabbitMQ/Redis) for async tasks

### Vertical Scaling
- Increase container memory limits in docker-compose.yml
- Add more CPU cores
- Upgrade database instance

### High Availability
- PostgreSQL replication (primary + standby)
- Redis Sentinel for cache failover
- Multi-region deployment
- Automated health checks and failover

---

## Support & Resources

- **Documentation**: See README.md and ARCHITECTURE.md
- **Issues**: Open GitHub issue
- **Logs**: Check `logs/betting_advisor.log`
- **Health**: Monitor `/health` endpoint

---

**Remember**: Always start with `MODE=DRY_RUN` and validate thoroughly before enabling `MODE=LIVE`.
