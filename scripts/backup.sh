#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Intelligence Platform - SQLite Backup Script
# Phase 3 Task 3.3: Data Backup Solution
#
# Usage: ./backup.sh [DATA_DIR] [BACKUP_DIR]
#
#   DATA_DIR    - Root data directory containing domain subdirectories
#                 (default: ./intelligence_data from env or parent of this script)
#   BACKUP_DIR  - Directory to store backups
#                 (default: <DATA_DIR>/backups)
#
# Designed to run:
#   - Inside Docker containers (e.g. via cron in research/sales services)
#   - Outside Docker (standalone, e.g. on host cron)
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Data directory: env var > default
DATA_DIR="${INTELLIGENCE_DATA_DIR:-${PROJECT_DIR}/intelligence_data}"

# Backup directory: env var > default
BACKUP_DIR="${INTELLIGENCE_BACKUP_DIR:-${DATA_DIR}/backups}"

RETENTION_DAYS=7

# Logging
LOG_PREFIX="[backup]"

log_info() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') ${LOG_PREFIX} INFO: $*"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') ${LOG_PREFIX} ERROR: $*" >&2
}

# Find all SQLite databases under DATA_DIR
find_databases() {
    find "${DATA_DIR}" -name '*.db' -not -path '*/backups/*' -type f 2>/dev/null | sort
}

# Check prerequisites
check_prerequisites() {
    if ! command -v sqlite3 &>/dev/null; then
        log_error "sqlite3 command not found. Install it: apt-get install sqlite3"
        exit 1
    fi

    if ! command -v gzip &>/dev/null; then
        log_error "gzip command not found. Install it: apt-get install gzip"
        exit 1
    fi

    if [[ ! -d "${DATA_DIR}" ]]; then
        log_error "Data directory not found: ${DATA_DIR}"
        exit 1
    fi

    mkdir -p "${BACKUP_DIR}"
}

# Create a backup of a single database
backup_database() {
    local db_path="$1"
    local db_name
    db_name="$(basename "${db_path}" .db)"
    local timestamp
    timestamp="$(date '+%Y%m%d_%H%M%S')"
    local backup_filename="${db_name}_${timestamp}.sql.gz"
    local backup_path="${BACKUP_DIR}/${backup_filename}"

    # Skip if backup already exists (idempotency - safe to re-run within same second)
    if [[ -f "${backup_path}" ]]; then
        log_info "Skipping ${db_name}: backup ${backup_filename} already exists"
        return 0
    fi

    log_info "Backing up ${db_name} from ${db_path} ..."

    # Dump database and compress
    if sqlite3 "${db_path}" .dump | gzip > "${backup_path}"; then
        local backup_size
        backup_size="$(du -h "${backup_path}" | cut -f1)"
        log_info "Backup successful: ${backup_filename} (${backup_size})"
        return 0
    else
        log_error "Backup failed for ${db_name} (${db_path})"
        rm -f "${backup_path}"
        return 1
    fi
}

# Remove backups older than RETENTION_DAYS
cleanup_old_backups() {
    log_info "Cleaning up backups older than ${RETENTION_DAYS} days ..."

    local old_backups
    old_backups="$(find "${BACKUP_DIR}" -name '*.sql.gz' -type f -mtime +"${RETENTION_DAYS}" 2>/dev/null)"

    if [[ -z "${old_backups}" ]]; then
        log_info "No old backups to clean up"
        return 0
    fi

    local count=0
    while IFS= read -r old_file; do
        rm -f "${old_file}"
        log_info "Removed: $(basename "${old_file}")"
        ((count++)) || true
    done <<< "${old_backups}"

    log_info "Cleaned up ${count} old backup(s)"
}

# Report current backup status
report_status() {
    log_info "=== Backup Status ==="
    local db_count
    db_count="$(find_databases | wc -l)"
    log_info "Databases found: ${db_count}"

    local backup_count
    backup_count="$(find "${BACKUP_DIR}" -name '*.sql.gz' -type f 2>/dev/null | wc -l)"
    log_info "Backups stored: ${backup_count}"

    local total_size
    total_size="$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1)"
    log_info "Total backup size: ${total_size}"
}

# ============================================================================
# Main
# ============================================================================
main() {
    log_info "========================================="
    log_info "Starting backup process"
    log_info "Data directory: ${DATA_DIR}"
    log_info "Backup directory: ${BACKUP_DIR}"
    log_info "Retention: ${RETENTION_DAYS} days"
    log_info "========================================="

    check_prerequisites

    local dbs
    dbs="$(find_databases)"

    if [[ -z "${dbs}" ]]; then
        log_error "No .db files found under ${DATA_DIR}"
        exit 1
    fi

    local success=0
    local failed=0

    while IFS= read -r db; do
        if backup_database "${db}"; then
            ((success++)) || true
        else
            ((failed++)) || true
        fi
    done <<< "${dbs}"

    # Cleanup old backups (runs even if some backups failed)
    cleanup_old_backups

    report_status

    log_info "========================================="
    log_info "Backup complete: ${success} succeeded, ${failed} failed"
    log_info "========================================="

    if [[ ${failed} -gt 0 ]]; then
        exit 2
    fi
}

main "$@"