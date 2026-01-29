#!/bin/bash
# ==============================================
# SFA-Routing: Cleanup Script for Production
# ==============================================
# Removes development artifacts before deployment
# Usage: ./scripts/cleanup.sh [--dry-run]

set -e

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY RUN] Showing what would be deleted..."
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== SFA-Routing Cleanup Script ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Function to safely remove files/directories
safe_remove() {
    local target="$1"
    if [[ -e "$target" ]] || [[ -d "$target" ]]; then
        if $DRY_RUN; then
            echo "[WOULD DELETE] $target"
        else
            rm -rf "$target"
            echo "[DELETED] $target"
        fi
    fi
}

# 1. Python cache files
echo "--- Cleaning Python cache ---"
find . -type d -name "__pycache__" -print0 2>/dev/null | while IFS= read -r -d '' dir; do
    safe_remove "$dir"
done
find . -type f -name "*.pyc" -print0 2>/dev/null | while IFS= read -r -d '' file; do
    safe_remove "$file"
done
find . -type f -name "*.pyo" -print0 2>/dev/null | while IFS= read -r -d '' file; do
    safe_remove "$file"
done

# 2. Test caches
echo "--- Cleaning test caches ---"
safe_remove ".pytest_cache"
safe_remove "backend/.pytest_cache"
safe_remove ".coverage"
safe_remove "backend/.coverage"
safe_remove "htmlcov"
safe_remove "backend/htmlcov"
safe_remove ".mypy_cache"
safe_remove "backend/.mypy_cache"

# 3. IDE and editor files
echo "--- Cleaning IDE files ---"
safe_remove ".idea"
safe_remove ".vscode"
find . -type f -name "*.swp" -print0 2>/dev/null | while IFS= read -r -d '' file; do
    safe_remove "$file"
done
find . -type f -name "*.swo" -print0 2>/dev/null | while IFS= read -r -d '' file; do
    safe_remove "$file"
done
find . -type f -name "*~" -print0 2>/dev/null | while IFS= read -r -d '' file; do
    safe_remove "$file"
done

# 4. Node.js cache (frontend)
echo "--- Cleaning Node.js cache ---"
safe_remove "frontend/node_modules"
safe_remove "frontend/.cache"
safe_remove "frontend/dist"
safe_remove "frontend/build"

# 5. Temporary files
echo "--- Cleaning temporary files ---"
safe_remove "tmp"
safe_remove "temp"
find . -type f -name "*.tmp" -print0 2>/dev/null | while IFS= read -r -d '' file; do
    safe_remove "$file"
done
find . -type f -name "*.bak" -print0 2>/dev/null | while IFS= read -r -d '' file; do
    safe_remove "$file"
done

# 6. Log files
echo "--- Cleaning log files ---"
find . -type f -name "*.log" -print0 2>/dev/null | while IFS= read -r -d '' file; do
    safe_remove "$file"
done
safe_remove "logs"

# 7. Docker build cache (optional - uncomment if needed)
# echo "--- Cleaning Docker build cache ---"
# docker builder prune -f 2>/dev/null || true

# 8. Virtual environments (WARNING: this will delete venvs)
# Uncomment only if you want to clean virtual environments
# echo "--- Cleaning virtual environments ---"
# safe_remove "venv"
# safe_remove ".venv"
# safe_remove "backend/venv"
# safe_remove "backend/.venv"

echo ""
echo "=== Cleanup completed ==="

if $DRY_RUN; then
    echo ""
    echo "This was a dry run. Run without --dry-run to actually delete files."
fi
