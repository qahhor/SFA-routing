#!/bin/bash
# ==============================================
# SFA-Routing: System Diagnostic Script
# ==============================================
# Быстрая диагностика состояния системы
# Usage: ./scripts/diagnose.sh [--full]

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
FULL_MODE=false

if [[ "$1" == "--full" ]]; then
    FULL_MODE=true
fi

cd "$PROJECT_ROOT"

echo -e "${BLUE}=============================================="
echo "  SFA-Routing System Diagnostics"
echo -e "==============================================${NC}"
echo ""

# 1. Docker Status
echo -e "${YELLOW}=== 1. Docker Status ===${NC}"
if ! docker info &> /dev/null; then
    echo -e "${RED}[ERROR] Docker is not running!${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Docker is running${NC}"
echo ""

# 2. Container Status
echo -e "${YELLOW}=== 2. Container Status ===${NC}"
docker compose $COMPOSE_FILES ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 3. Resource Usage
echo -e "${YELLOW}=== 3. Resource Usage ===${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
echo ""

# 4. Health Checks
echo -e "${YELLOW}=== 4. Health Checks ===${NC}"
API_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health 2>/dev/null || echo "000")
if [[ "$API_HEALTH" == "200" ]]; then
    echo -e "${GREEN}[OK] API Health: $API_HEALTH${NC}"
    if $FULL_MODE; then
        echo "Detailed health:"
        curl -s http://localhost:8000/api/v1/health/detailed 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Could not parse response"
    fi
else
    echo -e "${RED}[ERROR] API Health: $API_HEALTH${NC}"
fi

# Check Database
DB_STATUS=$(docker compose $COMPOSE_FILES exec -T db pg_isready -U routeuser 2>/dev/null && echo "OK" || echo "FAIL")
if [[ "$DB_STATUS" == *"OK"* ]]; then
    echo -e "${GREEN}[OK] Database: Ready${NC}"
else
    echo -e "${RED}[ERROR] Database: Not Ready${NC}"
fi

# Check Redis
REDIS_STATUS=$(docker compose $COMPOSE_FILES exec -T redis redis-cli ping 2>/dev/null || echo "FAIL")
if [[ "$REDIS_STATUS" == "PONG" ]]; then
    echo -e "${GREEN}[OK] Redis: $REDIS_STATUS${NC}"
else
    echo -e "${RED}[ERROR] Redis: $REDIS_STATUS${NC}"
fi
echo ""

# 5. Disk Space
echo -e "${YELLOW}=== 5. Disk Space ===${NC}"
df -h / | tail -1 | awk '{print "Root: " $3 " used / " $2 " total (" $5 " used)"}'
df -h /var/lib/docker 2>/dev/null | tail -1 | awk '{print "Docker: " $3 " used / " $2 " total (" $5 " used)"}' || echo "Docker dir: (same as root)"
echo ""

# 6. Recent Errors
echo -e "${YELLOW}=== 6. Recent Errors (last 10) ===${NC}"
docker compose $COMPOSE_FILES logs --tail=500 api 2>&1 | grep -i "error\|exception\|traceback" | tail -10 || echo "No recent errors found"
echo ""

# 7. Database Connections
echo -e "${YELLOW}=== 7. Database Connections ===${NC}"
docker compose $COMPOSE_FILES exec -T db psql -U routeuser -d routes -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || echo "Could not query database"
echo ""

# 8. Redis Info
echo -e "${YELLOW}=== 8. Redis Info ===${NC}"
docker compose $COMPOSE_FILES exec -T redis redis-cli info 2>/dev/null | grep -E "connected_clients|used_memory_human|total_connections_received" || echo "Could not query Redis"
echo ""

# 9. Celery Workers
echo -e "${YELLOW}=== 9. Celery Workers ===${NC}"
docker compose $COMPOSE_FILES exec -T celery celery -A app.core.celery_app inspect ping 2>/dev/null | head -5 || echo "Could not query Celery"
echo ""

if $FULL_MODE; then
    # 10. Network Configuration
    echo -e "${YELLOW}=== 10. Network Configuration ===${NC}"
    docker network ls | grep route
    echo ""

    # 11. Volumes
    echo -e "${YELLOW}=== 11. Docker Volumes ===${NC}"
    docker volume ls | grep -E "postgres|redis" || echo "No relevant volumes found"
    echo ""

    # 12. Recent Logs Summary
    echo -e "${YELLOW}=== 12. Log Level Distribution (API, last 1000 lines) ===${NC}"
    docker compose $COMPOSE_FILES logs --tail=1000 api 2>&1 | grep -oE '"level":"[A-Z]+"' | sort | uniq -c | sort -rn || echo "Could not analyze logs"
    echo ""
fi

# Summary
echo -e "${BLUE}=============================================="
echo "  Diagnostic Summary"
echo -e "==============================================${NC}"

ISSUES=0

if [[ "$API_HEALTH" != "200" ]]; then
    echo -e "${RED}[ISSUE] API is not healthy${NC}"
    ISSUES=$((ISSUES + 1))
fi

if [[ "$DB_STATUS" != *"OK"* ]]; then
    echo -e "${RED}[ISSUE] Database is not ready${NC}"
    ISSUES=$((ISSUES + 1))
fi

if [[ "$REDIS_STATUS" != "PONG" ]]; then
    echo -e "${RED}[ISSUE] Redis is not responding${NC}"
    ISSUES=$((ISSUES + 1))
fi

DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%')
if [[ "$DISK_USAGE" -gt 90 ]]; then
    echo -e "${RED}[ISSUE] Disk usage is above 90%${NC}"
    ISSUES=$((ISSUES + 1))
fi

if [[ "$ISSUES" -eq 0 ]]; then
    echo -e "${GREEN}All systems operational!${NC}"
else
    echo -e "${YELLOW}Found $ISSUES issue(s). Please review above.${NC}"
fi

echo ""
echo "For full diagnostics, run: $0 --full"
echo "For troubleshooting, see: docs/TROUBLESHOOTING_RU.md"
