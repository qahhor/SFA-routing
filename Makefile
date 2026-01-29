# ==============================================
# SFA-Routing: Makefile
# ==============================================
# Автоматизация общих команд разработки и развертывания
# Использование: make <target>
# Справка: make help

.PHONY: help install dev prod build test lint clean migrate logs shell backup rollback

# Переменные
COMPOSE_DEV = docker compose
COMPOSE_PROD = docker compose -f docker-compose.yml -f docker-compose.prod.yml
BACKEND = backend
FRONTEND = frontend

# Цвета для вывода
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
BLUE   := $(shell tput -Txterm setaf 4)
RESET  := $(shell tput -Txterm sgr0)

# ==============================================
# ПОМОЩЬ
# ==============================================

help: ## Показать справку по командам
	@echo ''
	@echo '${BLUE}SFA-Routing - Makefile Commands${RESET}'
	@echo ''
	@echo '${YELLOW}Использование:${RESET}'
	@echo '  make ${GREEN}<target>${RESET}'
	@echo ''
	@echo '${YELLOW}Цели:${RESET}'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  ${GREEN}%-20s${RESET} %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ''

# ==============================================
# УСТАНОВКА И НАСТРОЙКА
# ==============================================

install: ## Установить зависимости для разработки
	@echo "${BLUE}Установка зависимостей...${RESET}"
	cd $(BACKEND) && pip install -r requirements.txt
	pip install pre-commit
	pre-commit install
	@echo "${GREEN}Установка завершена!${RESET}"

setup-env: ## Создать .env файлы из шаблонов
	@echo "${BLUE}Настройка окружения...${RESET}"
	@if [ ! -f $(BACKEND)/.env ]; then \
		cp $(BACKEND)/.env.example $(BACKEND)/.env; \
		echo "${GREEN}Создан $(BACKEND)/.env${RESET}"; \
	else \
		echo "${YELLOW}$(BACKEND)/.env уже существует${RESET}"; \
	fi
	@echo "${YELLOW}Не забудьте отредактировать .env файлы!${RESET}"

# ==============================================
# РАЗРАБОТКА
# ==============================================

dev: ## Запустить в режиме разработки
	@echo "${BLUE}Запуск dev окружения...${RESET}"
	$(COMPOSE_DEV) up -d db redis
	@sleep 3
	$(COMPOSE_DEV) up api celery celery-beat frontend

dev-up: ## Запустить все сервисы в фоне (dev)
	$(COMPOSE_DEV) up -d

dev-down: ## Остановить все сервисы (dev)
	$(COMPOSE_DEV) down

dev-restart: ## Перезапустить сервисы (dev)
	$(COMPOSE_DEV) restart

dev-logs: ## Показать логи (dev)
	$(COMPOSE_DEV) logs -f --tail=100

# ==============================================
# PRODUCTION
# ==============================================

prod: ## Запустить в production режиме
	@echo "${BLUE}Запуск production окружения...${RESET}"
	$(COMPOSE_PROD) up -d

prod-down: ## Остановить production сервисы
	$(COMPOSE_PROD) down

prod-restart: ## Перезапустить production сервисы
	$(COMPOSE_PROD) restart

prod-logs: ## Показать production логи
	$(COMPOSE_PROD) logs -f --tail=100

prod-status: ## Статус production сервисов
	$(COMPOSE_PROD) ps
	@echo ""
	@docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# ==============================================
# СБОРКА
# ==============================================

build: ## Собрать Docker образы
	@echo "${BLUE}Сборка образов...${RESET}"
	$(COMPOSE_DEV) build

build-prod: ## Собрать production образы
	@echo "${BLUE}Сборка production образов...${RESET}"
	$(COMPOSE_PROD) build --no-cache

build-api: ## Собрать только API образ
	$(COMPOSE_DEV) build api

# ==============================================
# ТЕСТИРОВАНИЕ
# ==============================================

test: ## Запустить тесты
	@echo "${BLUE}Запуск тестов...${RESET}"
	cd $(BACKEND) && pytest tests/ -v

test-cov: ## Запустить тесты с покрытием
	cd $(BACKEND) && pytest tests/ -v --cov=app --cov-report=html --cov-report=term

test-fast: ## Быстрые тесты (без медленных)
	cd $(BACKEND) && pytest tests/ -v -m "not slow"

# ==============================================
# ЛИНТИНГ И ФОРМАТИРОВАНИЕ
# ==============================================

lint: ## Проверить код линтерами
	@echo "${BLUE}Проверка кода...${RESET}"
	cd $(BACKEND) && flake8 app --max-line-length=120 --ignore=E501,W503,E402
	cd $(BACKEND) && mypy app --ignore-missing-imports

format: ## Форматировать код
	@echo "${BLUE}Форматирование кода...${RESET}"
	cd $(BACKEND) && black app --line-length=120
	cd $(BACKEND) && isort app --profile=black --line-length=120

pre-commit: ## Запустить pre-commit hooks
	pre-commit run --all-files

# ==============================================
# БАЗА ДАННЫХ
# ==============================================

migrate: ## Применить миграции
	@echo "${BLUE}Применение миграций...${RESET}"
	$(COMPOSE_DEV) exec api alembic upgrade head

migrate-create: ## Создать новую миграцию (usage: make migrate-create MSG="description")
	$(COMPOSE_DEV) exec api alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Откатить последнюю миграцию
	$(COMPOSE_DEV) exec api alembic downgrade -1

migrate-history: ## Показать историю миграций
	$(COMPOSE_DEV) exec api alembic history

db-shell: ## Подключиться к PostgreSQL
	$(COMPOSE_DEV) exec db psql -U routeuser -d routes

# ==============================================
# SHELL ДОСТУП
# ==============================================

shell: ## Открыть shell в API контейнере
	$(COMPOSE_DEV) exec api bash

shell-db: ## Открыть shell в DB контейнере
	$(COMPOSE_DEV) exec db bash

shell-redis: ## Подключиться к Redis CLI
	$(COMPOSE_DEV) exec redis redis-cli

# ==============================================
# БЭКАПЫ И ВОССТАНОВЛЕНИЕ
# ==============================================

backup: ## Создать бэкап базы данных
	@echo "${BLUE}Создание бэкапа...${RESET}"
	./scripts/backup.sh --compress

backup-list: ## Список доступных бэкапов
	@ls -lh backups/ 2>/dev/null || echo "Нет бэкапов"

rollback-list: ## Список коммитов для отката
	./scripts/rollback.sh --list-commits

# ==============================================
# ОЧИСТКА
# ==============================================

clean: ## Очистить артефакты разработки
	@echo "${BLUE}Очистка...${RESET}"
	./scripts/cleanup.sh
	@echo "${GREEN}Очистка завершена!${RESET}"

clean-docker: ## Очистить Docker (контейнеры, образы, volumes)
	@echo "${YELLOW}ВНИМАНИЕ: Это удалит все неиспользуемые Docker ресурсы!${RESET}"
	@read -p "Продолжить? [y/N] " confirm && [ "$$confirm" = "y" ] && \
		docker system prune -af --volumes || echo "Отменено"

clean-all: clean clean-docker ## Полная очистка

# ==============================================
# ДЕПЛОЙ
# ==============================================

deploy: ## Полный деплой (build + migrate + restart)
	@echo "${BLUE}Запуск полного деплоя...${RESET}"
	./scripts/deploy.sh --full

deploy-build: ## Деплой: только сборка
	./scripts/deploy.sh --build

deploy-restart: ## Деплой: только перезапуск
	./scripts/deploy.sh --restart

# ==============================================
# МОНИТОРИНГ
# ==============================================

health: ## Проверить здоровье сервисов
	@echo "${BLUE}Проверка здоровья...${RESET}"
	@curl -s http://localhost:8000/api/v1/health | python3 -m json.tool || echo "API недоступен"

health-detailed: ## Детальная проверка здоровья
	@curl -s http://localhost:8000/api/v1/health/detailed | python3 -m json.tool || echo "API недоступен"

metrics: ## Показать Prometheus метрики
	@curl -s http://localhost:8000/metrics | head -50

# ==============================================
# OSRM
# ==============================================

osrm-setup: ## Скачать и подготовить OSRM данные для Узбекистана
	@echo "${BLUE}Настройка OSRM...${RESET}"
	@mkdir -p docker/osrm
	@cd docker/osrm && \
		wget -c https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf && \
		docker run -t -v $$(pwd):/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf && \
		docker run -t -v $$(pwd):/data osrm/osrm-backend osrm-partition /data/uzbekistan-latest.osrm && \
		docker run -t -v $$(pwd):/data osrm/osrm-backend osrm-customize /data/uzbekistan-latest.osrm
	@echo "${GREEN}OSRM данные готовы!${RESET}"

# ==============================================
# ВЕРСИОНИРОВАНИЕ
# ==============================================

version: ## Показать версии компонентов
	@echo "${BLUE}Версии:${RESET}"
	@echo "Python: $$(python3 --version)"
	@echo "Docker: $$(docker --version)"
	@echo "Docker Compose: $$(docker compose version)"
	@echo "Git: $$(git --version)"
	@git log -1 --format="Last commit: %h - %s (%cr)"
