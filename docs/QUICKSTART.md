# SFA-Routing: Quick Start Guide

## Быстрый старт для Beta v1.1

Это руководство поможет запустить систему за 15 минут.

---

## Предварительные требования

- Ubuntu 22.04 LTS (или Debian 12)
- Docker Engine 24.0+
- Docker Compose v2.20+
- 8GB RAM, 4 vCPU, 100GB SSD

---

## 1. Клонирование и настройка (2 мин)

```bash
# Клонировать репозиторий
git clone https://github.com/your-org/sfa-routing.git
cd sfa-routing

# Создать конфигурацию
cp backend/.env.example backend/.env

# Настроить окружение
nano backend/.env
# Измените:
# - POSTGRES_PASSWORD (openssl rand -base64 32)
# - SECRET_KEY (python3 -c "import secrets; print(secrets.token_urlsafe(64))")
```

---

## 2. Запуск для разработки (3 мин)

```bash
# Запустить все сервисы
make dev-up

# Или напрямую через Docker Compose
docker compose up -d

# Проверить статус
docker compose ps

# Применить миграции
docker compose exec api alembic upgrade head

# Проверить работоспособность
curl http://localhost:8000/api/v1/health
```

**Доступные URL:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3001

---

## 3. Запуск для Production (5 мин)

```bash
# Использовать production конфигурацию
cp backend/.env.production.example backend/.env
nano backend/.env  # Настроить все переменные

# Собрать и запустить
make deploy
# Или:
./scripts/deploy.sh --full

# Проверить
make health
# Или:
curl http://localhost/api/v1/health/detailed
```

---

## 4. Подготовка OSRM данных (5-10 мин)

Для работы маршрутизации нужны картографические данные:

```bash
# Скачать и подготовить данные для Узбекистана
make osrm-setup

# Или вручную:
cd docker/osrm
wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf

# Подготовить данные (занимает 5-10 минут)
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-partition /data/uzbekistan-latest.osrm
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-customize /data/uzbekistan-latest.osrm

# Запустить OSRM
cd ../..
docker compose --profile with-osrm up -d osrm vroom

# Проверить OSRM
curl "http://localhost:5001/route/v1/driving/69.24,41.31;69.28,41.32"
```

---

## Основные команды (Makefile)

```bash
# Разработка
make dev          # Запуск dev окружения
make dev-up       # Запуск в фоне
make dev-down     # Остановка
make dev-logs     # Просмотр логов

# Production
make prod         # Запуск production
make prod-status  # Статус сервисов
make deploy       # Полный деплой

# База данных
make migrate      # Применить миграции
make db-shell     # Подключиться к PostgreSQL

# Тестирование
make test         # Запустить тесты
make lint         # Проверить код

# Обслуживание
make health       # Проверить здоровье
make backup       # Создать бэкап
make clean        # Очистить артефакты

# Справка
make help         # Показать все команды
```

---

## Тестирование API

### Создание агента
```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Тест Агент",
    "external_id": "agent-001",
    "start_latitude": 41.311,
    "start_longitude": 69.279
  }'
```

### Создание клиента
```bash
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Магазин Тест",
    "external_id": "client-001",
    "address": "ул. Амира Темура, 1",
    "latitude": 41.315,
    "longitude": 69.285,
    "category": "A"
  }'
```

### Генерация недельного плана
```bash
curl -X POST http://localhost:8000/api/v1/planning/weekly \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "AGENT_UUID",
    "week_start_date": "2025-01-27"
  }'
```

### Оптимизация доставки
```bash
curl -X POST http://localhost:8000/api/v1/delivery/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "order_ids": ["ORDER_UUID_1", "ORDER_UUID_2"],
    "vehicle_ids": ["VEHICLE_UUID"],
    "date": "2025-01-30"
  }'
```

---

## Диагностика

```bash
# Быстрая диагностика
./scripts/diagnose.sh

# Полная диагностика
./scripts/diagnose.sh --full

# Просмотр логов
docker compose logs -f api celery

# Проверка ресурсов
docker stats
```

---

## Частые проблемы

### API не отвечает
```bash
docker compose logs api | tail -50
docker compose restart api
```

### База данных недоступна
```bash
docker compose logs db | tail -20
docker compose restart db
```

### Ошибки миграций
```bash
docker compose exec api alembic current
docker compose exec api alembic upgrade head
```

### OSRM не работает
```bash
docker compose --profile with-osrm logs osrm
# Проверьте, что файлы .osrm существуют в docker/osrm/
ls -la docker/osrm/*.osrm
```

---

## Следующие шаги

1. **Настройка SSL** - см. [DEPLOYMENT_GUIDE_RU.md](DEPLOYMENT_GUIDE_RU.md#5-настройка-ssltls)
2. **Мониторинг** - см. [MONITORING_RU.md](MONITORING_RU.md)
3. **Бэкапы** - `./scripts/backup.sh --help`
4. **Production checklist** - см. [PREFLIGHT_CHECKLIST.md](PREFLIGHT_CHECKLIST.md)

---

## Контакты

При проблемах:
1. Проверьте [TROUBLESHOOTING_RU.md](TROUBLESHOOTING_RU.md)
2. Запустите диагностику: `./scripts/diagnose.sh --full`
3. Создайте issue в репозитории

---

*Quick Start v1.1.0*
