#!/bin/bash
# ==============================================
# SFA-Routing: Rollback Script
# ==============================================
# Rolls back to a previous version or database state
# Usage: ./scripts/rollback.sh [--db backup_file] [--code commit_hash]
#
# Options:
#   --db FILE       Restore database from backup file
#   --code HASH     Rollback code to specific git commit
#   --list-backups  List available database backups
#   --list-commits  List recent commits for rollback

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/backups"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

# Database credentials
if [[ -f "$PROJECT_ROOT/backend/.env" ]]; then
    source "$PROJECT_ROOT/backend/.env" 2>/dev/null || true
fi
DB_USER="${POSTGRES_USER:-routeuser}"
DB_NAME="${POSTGRES_DB:-routes}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    local level=$1
    shift
    case $level in
        INFO)  echo -e "${BLUE}[INFO]${NC} $*" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $*" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $*" ;;
        OK)    echo -e "${GREEN}[OK]${NC} $*" ;;
    esac
}

# List available backups
list_backups() {
    log INFO "Available database backups:"
    echo ""
    if ls -lh "$BACKUP_DIR"/*.sql* 2>/dev/null; then
        echo ""
        log INFO "Usage: $0 --db /path/to/backup.sql"
    else
        log WARN "No backups found in $BACKUP_DIR"
    fi
}

# List recent commits
list_commits() {
    log INFO "Recent commits for rollback:"
    echo ""
    cd "$PROJECT_ROOT"
    git log --oneline -20
    echo ""
    log INFO "Usage: $0 --code <commit_hash>"
}

# Restore database from backup
restore_database() {
    local backup_file=$1

    # Validate backup file
    if [[ ! -f "$backup_file" ]]; then
        log ERROR "Backup file not found: $backup_file"
        exit 1
    fi

    log INFO "Restoring database from: $backup_file"
    log WARN "This will OVERWRITE the current database!"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm

    if [[ "$confirm" != "yes" ]]; then
        log INFO "Rollback cancelled"
        exit 0
    fi

    cd "$PROJECT_ROOT"

    # Check if database is running
    if ! docker compose $COMPOSE_FILES ps db --status running &> /dev/null; then
        log ERROR "Database container is not running"
        exit 1
    fi

    # Create pre-rollback backup
    log INFO "Creating pre-rollback backup..."
    PRE_ROLLBACK_BACKUP="$BACKUP_DIR/pre_rollback_$(date +%Y%m%d_%H%M%S).sql"
    docker compose $COMPOSE_FILES exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists > "$PRE_ROLLBACK_BACKUP" 2>/dev/null || true
    log INFO "Pre-rollback backup: $PRE_ROLLBACK_BACKUP"

    # Stop application services (keep db running)
    log INFO "Stopping application services..."
    docker compose $COMPOSE_FILES stop api celery celery-beat 2>/dev/null || true

    # Restore database
    log INFO "Restoring database..."

    # Decompress if needed
    if [[ "$backup_file" == *.gz ]]; then
        log INFO "Decompressing backup..."
        gunzip -c "$backup_file" | docker compose $COMPOSE_FILES exec -T db psql -U "$DB_USER" -d "$DB_NAME"
    else
        cat "$backup_file" | docker compose $COMPOSE_FILES exec -T db psql -U "$DB_USER" -d "$DB_NAME"
    fi

    # Restart application services
    log INFO "Restarting application services..."
    docker compose $COMPOSE_FILES up -d api celery celery-beat

    log OK "Database restored successfully!"
}

# Rollback code to specific commit
rollback_code() {
    local commit_hash=$1

    cd "$PROJECT_ROOT"

    # Validate commit exists
    if ! git cat-file -t "$commit_hash" &> /dev/null; then
        log ERROR "Commit not found: $commit_hash"
        exit 1
    fi

    log INFO "Rolling back code to commit: $commit_hash"
    log WARN "Current HEAD: $(git rev-parse --short HEAD)"

    # Show what will change
    echo ""
    log INFO "Changes to be rolled back:"
    git log --oneline HEAD...$commit_hash 2>/dev/null || git log --oneline $commit_hash...HEAD

    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm

    if [[ "$confirm" != "yes" ]]; then
        log INFO "Rollback cancelled"
        exit 0
    fi

    # Create tag for current state
    ROLLBACK_TAG="pre-rollback-$(date +%Y%m%d_%H%M%S)"
    git tag "$ROLLBACK_TAG"
    log INFO "Created tag for current state: $ROLLBACK_TAG"

    # Reset to commit
    git reset --hard "$commit_hash"

    # Rebuild and restart
    log INFO "Rebuilding and restarting services..."
    docker compose $COMPOSE_FILES build --no-cache api celery
    docker compose $COMPOSE_FILES up -d

    log OK "Code rolled back successfully!"
    log INFO "To undo this rollback, run: git reset --hard $ROLLBACK_TAG"
}

# Show help
show_help() {
    echo "SFA-Routing Rollback Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --db FILE         Restore database from backup file"
    echo "  --code HASH       Rollback code to specific git commit"
    echo "  --list-backups    List available database backups"
    echo "  --list-commits    List recent commits"
    echo "  --help            Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 --list-backups"
    echo "  $0 --db backups/daily_20250129_020000.sql.gz"
    echo "  $0 --code abc123"
}

# Parse arguments
if [[ $# -eq 0 ]]; then
    show_help
    exit 0
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --db)
            shift
            if [[ -z "$1" ]]; then
                log ERROR "Backup file path required"
                exit 1
            fi
            restore_database "$1"
            exit 0
            ;;
        --code)
            shift
            if [[ -z "$1" ]]; then
                log ERROR "Commit hash required"
                exit 1
            fi
            rollback_code "$1"
            exit 0
            ;;
        --list-backups)
            list_backups
            exit 0
            ;;
        --list-commits)
            list_commits
            exit 0
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log ERROR "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
    shift
done
