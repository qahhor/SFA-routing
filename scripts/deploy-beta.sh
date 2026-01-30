#!/bin/bash
# ============================================================
# SFA-Routing: Beta Deployment Script
# ============================================================
# Быстрое развёртывание Beta-версии
# Использование: ./scripts/deploy-beta.sh [--with-osrm]
# ============================================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Директория проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Логирование
LOG_FILE="logs/deploy_beta_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# ============================================================
# Проверка предварительных требований
# ============================================================
check_prerequisites() {
    header "Проверка предварительных требований"

    # Docker
    if ! command -v docker &> /dev/null; then
        error "Docker не установлен. Установите Docker: https://docs.docker.com/get-docker/"
    fi
    log "✓ Docker установлен: $(docker --version)"

    # Docker Compose
    if ! docker compose version &> /dev/null; then
        error "Docker Compose не установлен или устарел"
    fi
    log "✓ Docker Compose установлен: $(docker compose version --short)"

    # Проверка .env файла
    if [ ! -f ".env" ]; then
        warn ".env файл не найден. Создаю из шаблона..."
        cp .env.example .env
        warn "ВАЖНО: Отредактируйте .env файл и установите секретные ключи!"
        echo ""
        echo -e "${YELLOW}Сгенерируйте ключи командами:${NC}"
        echo "  python3 -c \"import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))\""
        echo "  python3 -c \"import secrets; print('WEBHOOK_SECRET_KEY=' + secrets.token_urlsafe(32))\""
        echo "  python3 -c \"import secrets; print('GEO_ENCRYPTION_KEY=' + secrets.token_urlsafe(32))\""
        echo "  python3 -c \"import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))\""
        echo ""
        read -p "Нажмите Enter после редактирования .env файла..."
    fi
    log "✓ .env файл существует"

    # Проверка обязательных переменных
    source .env
    if [[ "$SECRET_KEY" == *"CHANGE_ME"* ]] || [[ -z "$SECRET_KEY" ]]; then
        error "SECRET_KEY не установлен в .env файле!"
    fi
    if [[ "$POSTGRES_PASSWORD" == *"CHANGE_ME"* ]] || [[ -z "$POSTGRES_PASSWORD" ]]; then
        error "POSTGRES_PASSWORD не установлен в .env файле!"
    fi
    log "✓ Секретные ключи настроены"
}

# ============================================================
# Создание директорий
# ============================================================
create_directories() {
    header "Создание директорий"

    mkdir -p data/postgres data/redis backups logs
    log "✓ Директории созданы"
}

# ============================================================
# Сборка образов
# ============================================================
build_images() {
    header "Сборка Docker образов"

    log "Сборка backend образа..."
    docker compose -f docker-compose.yml -f docker-compose.beta.yml build --no-cache api

    log "✓ Образы собраны"
}

# ============================================================
# Запуск сервисов
# ============================================================
start_services() {
    header "Запуск сервисов"

    local COMPOSE_FILES="-f docker-compose.yml -f docker-compose.beta.yml"

    # Проверка флага --with-osrm
    if [[ "$1" == "--with-osrm" ]]; then
        log "Запуск с OSRM/VROOM сервисами..."
        docker compose $COMPOSE_FILES --profile with-osrm up -d
    else
        log "Запуск основных сервисов..."
        docker compose $COMPOSE_FILES up -d
    fi

    log "Ожидание запуска сервисов..."
    sleep 10

    log "✓ Сервисы запущены"
}

# ============================================================
# Применение миграций
# ============================================================
apply_migrations() {
    header "Применение миграций базы данных"

    log "Ожидание готовности PostgreSQL..."
    for i in {1..30}; do
        if docker compose exec -T db pg_isready -U routeuser -d routes &> /dev/null; then
            break
        fi
        sleep 2
    done

    log "Применение миграций..."
    docker compose exec -T api alembic upgrade head

    log "✓ Миграции применены"
}

# ============================================================
# Проверка работоспособности
# ============================================================
health_check() {
    header "Проверка работоспособности"

    log "Проверка Health endpoint..."
    for i in {1..30}; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log "✓ API отвечает"
            break
        fi
        if [ $i -eq 30 ]; then
            error "API не отвечает после 60 секунд ожидания"
        fi
        sleep 2
    done

    # Детальная проверка
    log "Детальная проверка сервисов..."

    HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null || echo '{"status":"error"}')
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"

    log ""
    log "Статус контейнеров:"
    docker compose ps
}

# ============================================================
# Вывод информации
# ============================================================
print_info() {
    header "Развёртывание завершено!"

    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           SFA-Routing Beta успешно развёрнут!              ║${NC}"
    echo -e "${GREEN}╠════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║${NC}  API:           http://localhost:8000                      ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  Документация:  http://localhost:8000/api/v1/docs          ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  Health:        http://localhost:8000/health               ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  Метрики:       http://localhost:8000/metrics              ${GREEN}║${NC}"
    echo -e "${GREEN}╠════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║${NC}  Логи:          docker compose logs -f api                 ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  Остановка:     docker compose down                        ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  Диагностика:   ./scripts/diagnose.sh                      ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    log "Лог развёртывания: $LOG_FILE"
}

# ============================================================
# Основной процесс
# ============================================================
main() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║     SFA-Routing Service - Beta Deployment                     ║"
    echo "║     Version: 1.2.0-beta                                       ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    check_prerequisites
    create_directories
    build_images
    start_services "$1"
    apply_migrations
    health_check
    print_info
}

# Запуск
main "$@"
