# SFA-Routing: Руководство по развёртыванию Beta-версии

**Версия:** 1.2.0-beta
**Дата:** Январь 2026
**Статус:** Production Ready

---

## Содержание

1. [Обзор системы](#1-обзор-системы)
2. [Системные требования](#2-системные-требования)
3. [Предварительные требования](#3-предварительные-требования)
4. [Быстрый старт (5 минут)](#4-быстрый-старт-5-минут)
5. [Полная установка](#5-полная-установка)
6. [Конфигурация](#6-конфигурация)
7. [Запуск сервисов](#7-запуск-сервисов)
8. [Проверка работоспособности](#8-проверка-работоспособности)
9. [Мониторинг и логирование](#9-мониторинг-и-логирование)
10. [Troubleshooting](#10-troubleshooting)
11. [Процедура Rollback](#11-процедура-rollback)
12. [Обновление системы](#12-обновление-системы)

---

## 1. Обзор системы

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                     │
│                    Порты: 80 (HTTP), 443 (HTTPS)            │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                      API Gateway                             │
│                   FastAPI (Порт 8000)                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ REST API │ WebSocket │ Health Checks │ Metrics          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────┬───────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  PostgreSQL   │    │     Redis     │    │    Celery     │
│   + PostGIS   │    │    Cache      │    │   Workers     │
│  Порт: 5432   │    │  Порт: 6379   │    │               │
└───────────────┘    └───────────────┘    └───────┬───────┘
                                                  │
                           ┌──────────────────────┼──────────┐
                           │                      │          │
                           ▼                      ▼          ▼
                    ┌───────────┐          ┌───────────┐ ┌────────┐
                    │   OSRM    │          │   VROOM   │ │Webhooks│
                    │ Порт:5000 │          │ Порт:3000 │ │        │
                    └───────────┘          └───────────┘ └────────┘
```

### Компоненты системы

| Компонент | Описание | Порт |
|-----------|----------|------|
| **API** | FastAPI backend с REST и WebSocket | 8000 |
| **Nginx** | Reverse proxy, SSL termination | 80/443 |
| **PostgreSQL** | Основная БД с PostGIS | 5432 |
| **Redis** | Кэш и брокер сообщений | 6379 |
| **Celery** | Фоновые задачи | - |
| **OSRM** | Матрицы расстояний | 5000 |
| **VROOM** | VRP солвер | 3000 |

---

## 2. Системные требования

### Минимальные требования (Beta)

| Ресурс | Минимум | Рекомендуется |
|--------|---------|---------------|
| **CPU** | 4 cores | 8 cores |
| **RAM** | 8 GB | 16 GB |
| **Диск** | 50 GB SSD | 100 GB SSD |
| **ОС** | Ubuntu 20.04+ | Ubuntu 22.04 LTS |

### Требования к ПО

| Программа | Версия | Проверка |
|-----------|--------|----------|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Git | 2.30+ | `git --version` |

### Сетевые требования

| Порт | Протокол | Назначение |
|------|----------|------------|
| 80 | TCP | HTTP (редирект на HTTPS) |
| 443 | TCP | HTTPS (основной) |
| 22 | TCP | SSH (администрирование) |

---

## 3. Предварительные требования

### 3.1 Установка Docker (Ubuntu)

```bash
# Обновление пакетов
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Добавление GPG ключа Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавление репозитория
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Проверка
docker --version
docker compose version
```

### 3.2 Генерация секретных ключей

```bash
# Генерация SECRET_KEY (64 символа)
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"

# Генерация WEBHOOK_SECRET_KEY (32 символа)
python3 -c "import secrets; print('WEBHOOK_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Генерация GEO_ENCRYPTION_KEY (32 символа)
python3 -c "import secrets; print('GEO_ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"

# Генерация пароля БД (32 символа)
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"
```

**Сохраните все ключи в безопасном месте!**

### 3.3 Чеклист предварительных требований

```
[ ] Docker 24.0+ установлен
[ ] Docker Compose 2.20+ установлен
[ ] Пользователь добавлен в группу docker
[ ] Сгенерированы все секретные ключи
[ ] Доступны порты 80, 443
[ ] Настроен firewall (ufw/iptables)
[ ] Есть доступ к серверу по SSH
[ ] Настроен домен (опционально для Beta)
```

---

## 4. Быстрый старт (5 минут)

Для быстрого запуска Beta-версии без SSL:

```bash
# 1. Клонирование репозитория
git clone https://github.com/your-org/SFA-routing.git
cd SFA-routing

# 2. Копирование конфигурации
cp .env.example .env

# 3. Редактирование .env (установите свои ключи!)
nano .env

# 4. Запуск всех сервисов
docker compose up -d

# 5. Проверка статуса
docker compose ps

# 6. Проверка логов
docker compose logs -f api

# 7. Тестирование API
curl http://localhost:8000/health
```

**API доступен на:** `http://localhost:8000`
**Документация:** `http://localhost:8000/api/v1/docs`

---

## 5. Полная установка

### 5.1 Клонирование и настройка

```bash
# Клонирование репозитория
git clone https://github.com/your-org/SFA-routing.git
cd SFA-routing

# Создание директорий для данных
mkdir -p data/postgres data/redis backups logs

# Установка прав
chmod 755 scripts/*.sh
```

### 5.2 Настройка SSL сертификатов

#### Вариант A: Let's Encrypt (рекомендуется)

```bash
# Установка certbot
sudo apt install -y certbot

# Получение сертификата (замените your-domain.com)
sudo certbot certonly --standalone -d your-domain.com

# Копирование сертификатов
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem docker/nginx/ssl/

# Установка прав
sudo chown $USER:$USER docker/nginx/ssl/*.pem
chmod 600 docker/nginx/ssl/*.pem
```

#### Вариант B: Self-signed (только для тестирования)

```bash
# Генерация self-signed сертификата
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/nginx/ssl/privkey.pem \
  -out docker/nginx/ssl/fullchain.pem \
  -subj "/CN=localhost"
```

### 5.3 Создание production конфигурации

```bash
# Копирование шаблона
cp .env.example .env

# Редактирование конфигурации
nano .env
```

**Обязательные изменения в `.env`:**

```bash
# ОБЯЗАТЕЛЬНО ИЗМЕНИТЕ:
ENVIRONMENT=production
POSTGRES_PASSWORD=<ваш_сгенерированный_пароль>
SECRET_KEY=<ваш_сгенерированный_ключ_64_символа>
WEBHOOK_SECRET_KEY=<ваш_сгенерированный_ключ_32_символа>
GEO_ENCRYPTION_KEY=<ваш_сгенерированный_ключ_32_символа>
DEBUG=false

# Настройте CORS для вашего домена:
CORS_ORIGINS=https://your-domain.com,https://app.your-domain.com
```

### 5.4 Загрузка карт для OSRM (опционально)

```bash
# Создание директории для карт
mkdir -p docker/osrm/data

# Скачивание карты Узбекистана
cd docker/osrm/data
wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf

# Подготовка данных (занимает 10-30 минут)
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-partition /data/uzbekistan-latest.osrm
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-customize /data/uzbekistan-latest.osrm

cd ../../..
```

---

## 6. Конфигурация

### 6.1 Переменные окружения

| Переменная | Описание | Обязательно | Пример |
|------------|----------|-------------|--------|
| `ENVIRONMENT` | Тип окружения | Да | `production` |
| `POSTGRES_PASSWORD` | Пароль БД | Да | `<32+ символов>` |
| `SECRET_KEY` | JWT ключ | Да | `<64 символа>` |
| `WEBHOOK_SECRET_KEY` | Ключ вебхуков | Да | `<32 символа>` |
| `GEO_ENCRYPTION_KEY` | Шифрование координат | Да | `<32 символа>` |
| `CORS_ORIGINS` | Разрешённые домены | Да | `https://app.example.com` |
| `SENTRY_DSN` | Sentry для ошибок | Нет | `https://xxx@sentry.io/xxx` |
| `OSRM_URL` | URL OSRM сервиса | Нет | `http://osrm:5000` |
| `VROOM_URL` | URL VROOM сервиса | Нет | `http://vroom:3000` |

### 6.2 Лимиты ресурсов (docker-compose.prod.yml)

| Сервис | CPU | RAM | Рекомендуется |
|--------|-----|-----|---------------|
| API | 2 | 2GB | 4 cores, 4GB |
| Celery | 2 | 2GB | 2 cores, 2GB |
| PostgreSQL | 2 | 4GB | 4 cores, 8GB |
| Redis | 1 | 768MB | 1 core, 1GB |
| OSRM | 2 | 4GB | 4 cores, 8GB |

---

## 7. Запуск сервисов

### 7.1 Запуск в режиме Beta

```bash
# Запуск основных сервисов
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Запуск с OSRM/VROOM (если нужны локальные сервисы)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile with-osrm up -d

# Проверка статуса
docker compose ps
```

### 7.2 Применение миграций БД

```bash
# Применение миграций
docker compose exec api alembic upgrade head

# Проверка статуса миграций
docker compose exec api alembic current
```

### 7.3 Создание администратора (опционально)

```bash
# Вход в контейнер
docker compose exec api python -c "
from app.core.database import sync_engine
from app.models.user import User
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

with Session(sync_engine) as session:
    admin = User(
        email='admin@example.com',
        hashed_password=bcrypt.hash('your-secure-password'),
        is_superuser=True,
        is_active=True
    )
    session.add(admin)
    session.commit()
    print('Admin created successfully')
"
```

---

## 8. Проверка работоспособности

### 8.1 Автоматическая проверка

```bash
# Запуск диагностики
./scripts/diagnose.sh
```

### 8.2 Ручная проверка

```bash
# 1. Проверка всех контейнеров
docker compose ps

# 2. Health check API
curl -s http://localhost:8000/health | jq

# Ожидаемый ответ:
# {
#   "status": "healthy",
#   "version": "1.2.0",
#   "environment": "production"
# }

# 3. Детальный health check
curl -s http://localhost:8000/health/detailed | jq

# 4. Проверка базы данных
docker compose exec db psql -U routeuser -d routes -c "SELECT 1"

# 5. Проверка Redis
docker compose exec redis redis-cli ping
# Ожидается: PONG

# 6. Проверка Celery
docker compose exec celery celery -A app.core.celery_app inspect ping

# 7. Проверка логов на ошибки
docker compose logs --tail=50 api | grep -i error
```

### 8.3 Тестирование API

```bash
# Получение токена
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your-password"}' | jq -r '.access_token')

# Тестовый запрос
curl -s http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" | jq

# Проверка WebSocket
websocat ws://localhost:8000/ws/gps
```

---

## 9. Мониторинг и логирование

### 9.1 Просмотр логов

```bash
# Все логи
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f api
docker compose logs -f celery
docker compose logs -f db

# Последние 100 строк с ошибками
docker compose logs --tail=100 api | grep -E "(ERROR|CRITICAL)"

# Логи за последний час
docker compose logs --since="1h" api
```

### 9.2 Метрики Prometheus

Метрики доступны на: `http://localhost:8000/metrics`

**Ключевые метрики:**

| Метрика | Описание |
|---------|----------|
| `http_requests_total` | Общее количество запросов |
| `http_request_duration_seconds` | Время ответа |
| `optimization_tasks_total` | Задачи оптимизации |
| `active_websocket_connections` | Активные WS соединения |

### 9.3 Настройка Sentry

```bash
# Добавьте в .env:
SENTRY_DSN=https://xxx@sentry.io/xxx

# Перезапустите API
docker compose restart api
```

### 9.4 Проверка состояния системы

```bash
# Использование ресурсов
docker stats

# Состояние дисков
df -h

# Размер базы данных
docker compose exec db psql -U routeuser -d routes -c "
SELECT pg_size_pretty(pg_database_size('routes'));"

# Количество соединений БД
docker compose exec db psql -U routeuser -d routes -c "
SELECT count(*) FROM pg_stat_activity WHERE datname='routes';"
```

---

## 10. Troubleshooting

### 10.1 Частые проблемы

#### API не запускается

```bash
# Проверка логов
docker compose logs api

# Частые причины:
# 1. Неверные переменные окружения
docker compose exec api env | grep -E "(SECRET|PASSWORD|KEY)"

# 2. БД недоступна
docker compose exec api python -c "
from app.core.database import engine
print(engine.url)
"

# 3. Порт занят
sudo lsof -i :8000
```

#### Ошибки подключения к БД

```bash
# Проверка статуса PostgreSQL
docker compose exec db pg_isready

# Проверка логов БД
docker compose logs db

# Сброс подключений
docker compose restart db
sleep 5
docker compose restart api
```

#### Celery задачи не выполняются

```bash
# Проверка воркеров
docker compose exec celery celery -A app.core.celery_app inspect active

# Проверка очереди
docker compose exec celery celery -A app.core.celery_app inspect reserved

# Перезапуск Celery
docker compose restart celery celery-beat
```

#### Высокое потребление памяти

```bash
# Проверка использования памяти
docker stats --no-stream

# Очистка кэша Redis
docker compose exec redis redis-cli FLUSHDB

# Перезапуск с очисткой
docker compose down
docker system prune -f
docker compose up -d
```

### 10.2 Диагностические команды

```bash
# Полная диагностика
./scripts/diagnose.sh

# Проверка конфигурации
docker compose config

# Проверка сети
docker network inspect sfa-routing_route-network

# Проверка volumes
docker volume ls | grep sfa-routing
```

---

## 11. Процедура Rollback

### 11.1 Автоматический Rollback

```bash
# Откат на предыдущую версию
./scripts/rollback.sh
```

### 11.2 Ручной Rollback

```bash
# 1. Остановка сервисов
docker compose down

# 2. Откат к предыдущему образу
docker compose pull  # если нужна конкретная версия
# или
git checkout <previous-tag>

# 3. Восстановление БД из бэкапа (если нужно)
./scripts/backup.sh restore backups/latest.sql.gz

# 4. Запуск
docker compose up -d

# 5. Проверка
curl http://localhost:8000/health
```

### 11.3 Восстановление базы данных

```bash
# Список бэкапов
ls -la backups/

# Восстановление из бэкапа
gunzip -c backups/routes_20260130_120000.sql.gz | \
  docker compose exec -T db psql -U routeuser -d routes
```

---

## 12. Обновление системы

### 12.1 Процедура обновления

```bash
# 1. Создание бэкапа
./scripts/backup.sh

# 2. Получение обновлений
git fetch origin
git checkout main
git pull origin main

# 3. Пересборка образов
docker compose build --no-cache

# 4. Применение миграций (если есть)
docker compose exec api alembic upgrade head

# 5. Перезапуск с новыми образами
docker compose up -d

# 6. Проверка
curl http://localhost:8000/health
docker compose logs --tail=50 api
```

### 12.2 Zero-downtime обновление

```bash
# Обновление с минимальным простоем
docker compose up -d --no-deps --build api
docker compose exec api alembic upgrade head

# Проверка нового инстанса
curl http://localhost:8000/health

# Перезапуск остальных сервисов по очереди
docker compose up -d --no-deps celery
docker compose up -d --no-deps celery-beat
```

---

## Приложение A: Полезные команды

```bash
# Быстрый статус
docker compose ps && echo && docker compose logs --tail=5 api

# Очистка всего
docker compose down -v --remove-orphans
docker system prune -af

# Экспорт логов
docker compose logs > logs/full_logs_$(date +%Y%m%d).txt

# Мониторинг в реальном времени
watch -n 2 'docker compose ps && echo && docker stats --no-stream'

# Бэкап и архивация
./scripts/backup.sh && tar -czf backup_$(date +%Y%m%d).tar.gz backups/ .env
```

---

## Приложение B: Контакты и поддержка

**Техническая поддержка Beta:**
- GitHub Issues: https://github.com/your-org/SFA-routing/issues
- Email: support@your-org.com

**Документация:**
- API Reference: `/api/v1/docs`
- Полная документация: `/docs/`

---

**Версия документа:** 1.0
**Последнее обновление:** Январь 2026
