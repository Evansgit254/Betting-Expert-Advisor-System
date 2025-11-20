#!/bin/bash
# Simple local backup script for Betting Expert Advisor
# Run this daily (add to crontab: 0 2 * * * /path/to/backup.sh)

BACKUP_DIR="$HOME/betting-backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting backup at $(date)"

# 1. Backup PostgreSQL database
echo "Backing up database..."
docker exec betting-advisor-db pg_dump -U betting_user betting_db > "$BACKUP_DIR/db_$DATE.sql"
gzip "$BACKUP_DIR/db_$DATE.sql"

# 2. Backup ML models (already versioned by ModelVersionManager)
echo "Backing up models..."
cp -r "$(pwd)/models/ensemble" "$BACKUP_DIR/models_$DATE/" 2>/dev/null || true

# 3. Backup configuration
echo "Backing up configuration..."
cp .env "$BACKUP_DIR/env_$DATE.bak" 2>/dev/null || true

# 4. Cleanup old backups (keep last 30 days)
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "models_*" -mtime +30 -exec rm -rf {} + 2>/dev/null || true

echo "Backup completed at $(date)"
echo "Backup location: $BACKUP_DIR"
echo ""
echo "To restore database: gunzip -c $BACKUP_DIR/db_$DATE.sql.gz | docker exec -i betting-advisor-db psql -U betting_user betting_db"
