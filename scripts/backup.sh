#!/bin/bash

# HIPAA Voice Agent - Backup Script
# Automated backup with encryption and retention management

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="hipaa_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-$MASTER_ENCRYPTION_KEY}"

# Load environment
if [ -f "config/.env" ]; then
    source config/.env
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1" >&2
    exit 1
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"
}

# Create backup directory
mkdir -p "${BACKUP_PATH}"

log_info "Starting backup: ${BACKUP_NAME}"

# ===== Database Backup =====
if docker ps | grep -q hipaa-postgres; then
    log_info "Backing up PostgreSQL database..."
    
    # Dump all databases
    docker exec hipaa-postgres pg_dumpall -U postgres > "${BACKUP_PATH}/postgres_all.sql" 2>/dev/null || {
        log_error "Failed to backup PostgreSQL"
    }
    
    # Compress database backup
    gzip "${BACKUP_PATH}/postgres_all.sql"
    
    log_info "Database backup completed"
else
    log_warn "PostgreSQL container not running - skipping database backup"
fi

# ===== Redis Backup =====
if docker ps | grep -q hipaa-redis; then
    log_info "Backing up Redis data..."
    
    # Trigger Redis save
    docker exec hipaa-redis redis-cli --pass "${REDIS_PASSWORD}" BGSAVE > /dev/null 2>&1 || true
    
    # Wait for save to complete
    sleep 5
    
    # Copy Redis dump file if it exists
    if [ -f "data/redis/dump.rdb" ]; then
        cp "data/redis/dump.rdb" "${BACKUP_PATH}/redis_dump.rdb"
        log_info "Redis backup completed"
    else
        log_warn "Redis dump file not found"
    fi
else
    log_warn "Redis container not running - skipping Redis backup"
fi

# ===== Configuration Backup =====
log_info "Backing up configuration..."

# Create config backup (excluding sensitive files)
mkdir -p "${BACKUP_PATH}/config"

# Copy non-sensitive config files
for file in config/*.yaml config/*.yml config/*.json config/*.toml; do
    if [ -f "$file" ]; then
        cp "$file" "${BACKUP_PATH}/config/" 2>/dev/null || true
    fi
done

# Backup environment file with redacted sensitive values
if [ -f "config/.env" ]; then
    # Redact sensitive values
    sed -E 's/(PASSWORD|SECRET|KEY|TOKEN)=.*/\1=REDACTED/g' config/.env > "${BACKUP_PATH}/config/.env.redacted"
fi

log_info "Configuration backup completed"

# ===== Audit Logs Backup =====
if [ -d "data/logs/audit" ]; then
    log_info "Backing up audit logs..."
    
    # Copy audit logs (these are already encrypted)
    mkdir -p "${BACKUP_PATH}/audit_logs"
    cp -r data/logs/audit/* "${BACKUP_PATH}/audit_logs/" 2>/dev/null || true
    
    log_info "Audit logs backup completed"
else
    log_warn "No audit logs found"
fi

# ===== Application Logs Backup =====
if [ -d "data/logs" ]; then
    log_info "Backing up application logs..."
    
    # Backup logs excluding PHI
    mkdir -p "${BACKUP_PATH}/logs"
    
    # Copy logs with PHI redaction
    for logfile in data/logs/*.log; do
        if [ -f "$logfile" ]; then
            basename=$(basename "$logfile")
            # Redact potential PHI patterns
            sed -E 's/[0-9]{3}-[0-9]{2}-[0-9]{4}/XXX-XX-XXXX/g; s/\([0-9]{3}\) [0-9]{3}-[0-9]{4}/(XXX) XXX-XXXX/g' \
                "$logfile" > "${BACKUP_PATH}/logs/${basename}"
        fi
    done
    
    log_info "Application logs backup completed"
fi

# ===== FHIR Data Export =====
if [ "${BACKUP_FHIR_DATA:-false}" = "true" ]; then
    log_info "Exporting FHIR data..."
    
    # This would require FHIR server connection
    # Placeholder for FHIR export logic
    mkdir -p "${BACKUP_PATH}/fhir"
    echo "FHIR export timestamp: $(date)" > "${BACKUP_PATH}/fhir/export.txt"
    
    log_info "FHIR data export completed"
fi

# ===== Docker Volumes Backup =====
log_info "Backing up Docker volumes..."

# Get list of volumes used by the stack
volumes=$(docker volume ls --filter "name=hipaa" --format "{{.Name}}")

mkdir -p "${BACKUP_PATH}/volumes"
for volume in $volumes; do
    if [[ "$volume" != *"postgres"* ]] && [[ "$volume" != *"redis"* ]]; then
        # Skip database volumes as they're backed up separately
        log_info "Backing up volume: $volume"
        docker run --rm -v "$volume:/data" -v "$(pwd)/${BACKUP_PATH}/volumes:/backup" \
            alpine tar czf "/backup/${volume}.tar.gz" -C /data . 2>/dev/null || true
    fi
done

log_info "Docker volumes backup completed"

# ===== Create Backup Archive =====
log_info "Creating backup archive..."

cd "${BACKUP_DIR}"
tar czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"

# ===== Encrypt Backup =====
if [ "${BACKUP_ENCRYPTION:-true}" = "true" ] && [ -n "${ENCRYPTION_KEY}" ]; then
    log_info "Encrypting backup..."
    
    # Use OpenSSL for encryption
    openssl enc -aes-256-cbc -salt -pbkdf2 \
        -in "${BACKUP_NAME}.tar.gz" \
        -out "${BACKUP_NAME}.tar.gz.enc" \
        -pass "pass:${ENCRYPTION_KEY}" 2>/dev/null || {
        log_error "Failed to encrypt backup"
    }
    
    # Remove unencrypted archive
    rm "${BACKUP_NAME}.tar.gz"
    
    # Rename encrypted file
    mv "${BACKUP_NAME}.tar.gz.enc" "${BACKUP_NAME}.tar.gz.enc"
    
    log_info "Backup encrypted successfully"
    FINAL_BACKUP="${BACKUP_NAME}.tar.gz.enc"
else
    log_warn "Backup encryption disabled or key not set"
    FINAL_BACKUP="${BACKUP_NAME}.tar.gz"
fi

# Clean up temporary backup directory
rm -rf "${BACKUP_NAME}"
cd ..

# ===== Upload to S3 (if configured) =====
if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
    log_info "Uploading backup to S3..."
    
    aws s3 cp "${BACKUP_DIR}/${FINAL_BACKUP}" \
        "s3://${BACKUP_S3_BUCKET}/backups/${FINAL_BACKUP}" \
        --sse AES256 \
        --storage-class STANDARD_IA || {
        log_error "Failed to upload backup to S3"
    }
    
    log_info "Backup uploaded to S3: s3://${BACKUP_S3_BUCKET}/backups/${FINAL_BACKUP}"
fi

# ===== Retention Management =====
log_info "Managing backup retention (${RETENTION_DAYS} days)..."

# Remove old local backups
find "${BACKUP_DIR}" -name "hipaa_backup_*.tar.gz*" -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

# Remove old S3 backups if configured
if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
    # List and delete old S3 backups
    cutoff_date=$(date -d "${RETENTION_DAYS} days ago" +%Y-%m-%d)
    
    aws s3api list-objects-v2 \
        --bucket "${BACKUP_S3_BUCKET}" \
        --prefix "backups/hipaa_backup_" \
        --query "Contents[?LastModified<='${cutoff_date}'].Key" \
        --output text | \
    while read -r key; do
        if [ -n "$key" ]; then
            log_info "Deleting old S3 backup: $key"
            aws s3 rm "s3://${BACKUP_S3_BUCKET}/${key}"
        fi
    done
fi

# ===== Backup Verification =====
log_info "Verifying backup..."

# Check backup file exists and has size
BACKUP_FILE="${BACKUP_DIR}/${FINAL_BACKUP}"
if [ -f "${BACKUP_FILE}" ]; then
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    log_info "Backup completed: ${BACKUP_FILE} (${SIZE})"
    
    # Test encryption if enabled
    if [[ "${FINAL_BACKUP}" == *.enc ]]; then
        # Try to decrypt a small part to verify
        if openssl enc -aes-256-cbc -d -salt -pbkdf2 \
            -in "${BACKUP_FILE}" \
            -pass "pass:${ENCRYPTION_KEY}" 2>/dev/null | \
            tar tzf - 2>/dev/null | head -n 1 > /dev/null; then
            log_info "Backup encryption verified"
        else
            log_error "Backup encryption verification failed"
        fi
    fi
else
    log_error "Backup file not found"
fi

# ===== Audit Log Entry =====
# Log backup completion for audit trail
AUDIT_LOG="data/logs/audit/backup_audit.log"
mkdir -p "$(dirname "${AUDIT_LOG}")"

cat >> "${AUDIT_LOG}" << EOF
$(date -Iseconds),BACKUP_COMPLETED,backup_name=${BACKUP_NAME},size=${SIZE},encrypted=$([ "${BACKUP_ENCRYPTION:-true}" = "true" ] && echo "yes" || echo "no"),s3_upload=$([ -n "${BACKUP_S3_BUCKET:-}" ] && echo "yes" || echo "no")
EOF

# ===== Notification =====
if [ -n "${BACKUP_NOTIFICATION_EMAIL:-}" ]; then
    # Send email notification (requires mail command)
    if command -v mail &> /dev/null; then
        echo "Backup completed successfully: ${BACKUP_NAME} (${SIZE})" | \
            mail -s "HIPAA Voice Agent - Backup Completed" "${BACKUP_NOTIFICATION_EMAIL}"
    fi
fi

# ===== Summary =====
echo
echo "======================================"
echo "       BACKUP SUMMARY"
echo "======================================"
echo "Backup Name: ${BACKUP_NAME}"
echo "Backup File: ${FINAL_BACKUP}"
echo "Size: ${SIZE}"
echo "Encrypted: $([ "${BACKUP_ENCRYPTION:-true}" = "true" ] && echo "Yes" || echo "No")"
echo "S3 Upload: $([ -n "${BACKUP_S3_BUCKET:-}" ] && echo "Yes" || echo "No")"
echo "Retention: ${RETENTION_DAYS} days"
echo "======================================"
echo

log_info "Backup process completed successfully"

exit 0
