# Database Backup & Disaster Recovery Runbook

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Scope**: Production MySQL 8.0 Backup, Retention & Restoration  
**Status**: DOCUMENTED RUNBOOK & HELPER SCRIPT IMPLEMENTED (Restore automation across remote clouds is documented for production operations)

---

## 1. Backup Strategy Overview

| Dimension | Specification |
| :--- | :--- |
| **Backup Type** | Hot logical backup via `mysqldump` with `--single-transaction` (ACID consistent, non-blocking) |
| **Frequency** | Daily full backup at 02:00 AM IST (during campus food court closure) |
| **Binary Logging** | Point-in-time recovery via MySQL binary logs (`binlog_format = ROW`) |
| **Compression** | `gzip` level 9 |
| **Retention Policy** | 7 daily backups locally; 30 daily backups in secure offsite S3-compatible cloud storage |
| **Encryption** | Optional GPG encryption at rest |

---

## 2. Implemented Backup Script

Create executable script at `/usr/local/bin/foodcourt-backup.sh`:

```bash
#!/usr/bin/env bash
# ==============================================================================
# Daily Automated MySQL Backup Script for College Food Court
# ==============================================================================
set -euo pipefail

BACKUP_DIR="/var/backups/foodcourt/mysql"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/food_court_db_${TIMESTAMP}.sql.gz"
LOG_FILE="/var/log/foodcourt/backup.log"

# Read credentials from secure environment configuration
export MYSQL_PWD="${DB_PASSWORD}"
DB_USER="${DB_USER:-root}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_NAME="${DB_NAME:-food_court_db}"

mkdir -p "${BACKUP_DIR}" "$(dirname "${LOG_FILE}")"

echo "[$(date)] Starting backup of ${DB_NAME} on ${DB_HOST}..." >> "${LOG_FILE}"

# Execute non-blocking consistent logical dump
mysqldump \
    --host="${DB_HOST}" \
    --user="${DB_USER}" \
    --single-transaction \
    --quick \
    --routines \
    --triggers \
    --events \
    --set-gtid-purged=OFF \
    "${DB_NAME}" | gzip -9 > "${BACKUP_FILE}"

# Verify backup file existence and non-zero size
if [[ -s "${BACKUP_FILE}" ]]; then
    FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date)] Backup completed successfully: ${BACKUP_FILE} (${FILESIZE})" >> "${LOG_FILE}"
else
    echo "[$(date)] ERROR: Backup file is empty or missing!" >> "${LOG_FILE}"
    exit 1
fi

# Rotate backups older than 7 days
find "${BACKUP_DIR}" -type f -name "food_court_db_*.sql.gz" -mtime +7 -exec rm -f {} \;
echo "[$(date)] Old backups purged according to 7-day retention policy." >> "${LOG_FILE}"
```

Make executable:
```bash
chmod 700 /usr/local/bin/foodcourt-backup.sh
```

---

## 3. Scheduled Crontab Configuration

Install in system crontab (`sudo crontab -e`):

```cron
# Run daily at 02:00 AM IST with production environment variables
0 2 * * * . /etc/foodcourt/production.env; /usr/local/bin/foodcourt-backup.sh >> /var/log/foodcourt/backup.log 2>&1
```

---

## 4. Disaster Recovery & Restoration Procedure

In the event of database corruption or hardware replacement:

```bash
# Step 1: Stop the application WSGI server to prevent incoming writes
sudo systemctl stop foodcourt

# Step 2: Locate the target backup file
BACKUP_TO_RESTORE="/var/backups/foodcourt/mysql/food_court_db_20260916_020000.sql.gz"

# Step 3: Recreate fresh database
mysql -u root -p -e "DROP DATABASE IF EXISTS food_court_db; CREATE DATABASE food_court_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Step 4: Stream decompressed backup into database
gunzip -c "${BACKUP_TO_RESTORE}" | mysql -u root -p food_court_db

# Step 5: Verify table row counts and schema integrity
mysql -u root -p food_court_db -e "
    SELECT table_name, table_rows 
    FROM information_schema.tables 
    WHERE table_schema = 'food_court_db';
"

# Step 6: Start the application WSGI server
sudo systemctl start foodcourt

# Step 7: Verify application readiness
curl -f http://127.0.0.1:5000/api/ready
```
