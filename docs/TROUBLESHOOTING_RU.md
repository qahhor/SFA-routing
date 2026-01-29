# Руководство по устранению неполадок SFA-Routing

## Оглавление

1. [Общие проблемы](#1-общие-проблемы)
2. [Проблемы с Docker](#2-проблемы-с-docker)
3. [Проблемы с базой данных](#3-проблемы-с-базой-данных)
4. [Проблемы с API](#4-проблемы-с-api)
5. [Проблемы с оптимизацией](#5-проблемы-с-оптимизацией)
6. [Проблемы с Celery](#6-проблемы-с-celery)
7. [Проблемы с производительностью](#7-проблемы-с-производительностью)
8. [Диагностические команды](#8-диагностические-команды)

---

## 1. Общие проблемы

### 1.1 Сервисы не запускаются

**Симптомы:**
- `docker compose up` завершается с ошибкой
- Контейнеры постоянно перезапускаются

**Диагностика:**
```bash
# Проверка статуса контейнеров
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -a

# Просмотр логов проблемного сервиса
docker compose logs --tail=100 api

# Проверка использования ресурсов
docker stats --no-stream
```

**Решения:**

| Причина | Решение |
|---------|---------|
| Недостаточно памяти | Увеличьте RAM или уменьшите лимиты в docker-compose.prod.yml |
| Порт занят | `lsof -i :8000` - найти процесс, `kill PID` или изменить порт |
| Ошибка в .env | Проверьте синтаксис и значения в backend/.env |
| Образ не собрался | `docker compose build --no-cache api` |

### 1.2 Ошибка "Permission denied"

**Симптомы:**
- Контейнер не может писать в volumes
- Ошибки доступа к файлам

**Решения:**
```bash
# Проверка владельца директорий
ls -la backups/ logs/

# Исправление прав
sudo chown -R 1000:1000 backups logs
chmod 755 backups logs

# Для PostgreSQL volumes
docker compose down
docker volume rm sfa-routing_postgres_data_prod
docker compose up -d
```

### 1.3 Сеть Docker не работает

**Симптомы:**
- Контейнеры не могут соединиться друг с другом
- "Connection refused" между сервисами

**Решения:**
```bash
# Пересоздание сети
docker compose down
docker network rm sfa-routing_route-network
docker compose up -d

# Проверка сети
docker network inspect sfa-routing_route-network

# Проверка DNS внутри контейнера
docker compose exec api ping db
docker compose exec api nslookup redis
```

---

## 2. Проблемы с Docker

### 2.1 "No space left on device"

**Диагностика:**
```bash
# Проверка места на диске
df -h

# Проверка использования Docker
docker system df
```

**Решения:**
```bash
# Очистка неиспользуемых ресурсов (ОСТОРОЖНО!)
docker system prune -a --volumes

# Только образы
docker image prune -a

# Только volumes (ПОТЕРЯ ДАННЫХ!)
docker volume prune

# Очистка логов контейнеров
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### 2.2 "Cannot connect to Docker daemon"

**Решения:**
```bash
# Проверка статуса Docker
sudo systemctl status docker

# Перезапуск Docker
sudo systemctl restart docker

# Проверка прав пользователя
groups $USER  # должна быть группа docker
sudo usermod -aG docker $USER
newgrp docker
```

### 2.3 Образ не собирается

**Симптомы:**
- Ошибки при `docker compose build`
- Зависание на определенном шаге

**Решения:**
```bash
# Сборка без кэша
docker compose build --no-cache api

# Сборка с выводом
docker compose build --progress=plain api

# Проверка Dockerfile
docker build -f backend/Dockerfile -t test ./backend

# Очистка BuildKit кэша
docker builder prune -a
```

---

## 3. Проблемы с базой данных

### 3.1 "Connection refused" к PostgreSQL

**Диагностика:**
```bash
# Проверка статуса контейнера
docker compose ps db

# Проверка логов
docker compose logs db

# Проверка доступности изнутри сети
docker compose exec api pg_isready -h db -U routeuser
```

**Решения:**

| Причина | Решение |
|---------|---------|
| Контейнер не запущен | `docker compose up -d db` |
| Неверные credentials | Проверьте POSTGRES_USER, POSTGRES_PASSWORD в .env |
| База не инициализирована | Пересоздайте volume: см. ниже |

```bash
# Пересоздание базы данных (ПОТЕРЯ ДАННЫХ!)
docker compose down
docker volume rm sfa-routing_postgres_data_prod
docker compose up -d db
# Дождитесь инициализации
sleep 10
docker compose up -d
docker compose exec api alembic upgrade head
```

### 3.2 Ошибки миграций Alembic

**Симптомы:**
- "Target database is not up to date"
- "Can't locate revision"

**Решения:**
```bash
# Просмотр текущей версии
docker compose exec api alembic current

# Просмотр истории
docker compose exec api alembic history

# Откат на одну версию назад
docker compose exec api alembic downgrade -1

# Откат до конкретной версии
docker compose exec api alembic downgrade abc123

# Применение всех миграций
docker compose exec api alembic upgrade head

# Пометка версии как текущей (без выполнения)
docker compose exec api alembic stamp head
```

### 3.3 Медленные запросы к БД

**Диагностика:**
```bash
# Включение логирования медленных запросов (уже в prod конфиге)
# log_min_duration_statement=1000  (1 секунда)

# Просмотр логов
docker compose logs db | grep "duration:"

# Анализ запроса
docker compose exec db psql -U routeuser -d routes -c "EXPLAIN ANALYZE SELECT ..."
```

**Решения:**
```bash
# Обновление статистики
docker compose exec db psql -U routeuser -d routes -c "ANALYZE;"

# Перестроение индексов
docker compose exec db psql -U routeuser -d routes -c "REINDEX DATABASE routes;"

# Проверка индексов
docker compose exec db psql -U routeuser -d routes -c "\di+"
```

---

## 4. Проблемы с API

### 4.1 "502 Bad Gateway"

**Причины и решения:**

| Причина | Диагностика | Решение |
|---------|-------------|---------|
| API не запущен | `docker compose ps api` | `docker compose restart api` |
| API упал с ошибкой | `docker compose logs api` | Исправить ошибку, перезапустить |
| Nginx неправильно настроен | `docker compose logs nginx` | Проверить conf.d/default.conf |
| Таймаут соединения | Запрос выполняется > 60с | Увеличить proxy_read_timeout |

### 4.2 "500 Internal Server Error"

**Диагностика:**
```bash
# Подробные логи API
docker compose logs --tail=200 api

# Поиск traceback
docker compose logs api 2>&1 | grep -A 20 "Traceback"

# Проверка с конкретным запросом
curl -v http://localhost/api/v1/health/detailed
```

**Частые причины:**
- Неверная конфигурация в .env
- Отсутствует подключение к Redis/PostgreSQL
- Ошибка в коде (проверьте traceback)

### 4.3 "401 Unauthorized" / "403 Forbidden"

**Проверки:**
```bash
# Проверка токена
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost/api/v1/agents

# Проверка срока действия токена
# JWT токены имеют expiry - проверьте ACCESS_TOKEN_EXPIRE_MINUTES

# Проверка прав пользователя
# Зависит от реализации RBAC в системе
```

### 4.4 CORS ошибки

**Симптомы:**
- "Access-Control-Allow-Origin" ошибки в браузере
- Запросы с фронтенда блокируются

**Решения:**
```bash
# Проверьте CORS_ORIGINS в .env
# Должен содержать домен фронтенда
CORS_ORIGINS=["https://app.yourdomain.com"]

# Перезапустите API
docker compose restart api
```

---

## 5. Проблемы с оптимизацией

### 5.1 OSRM не отвечает

**Диагностика:**
```bash
# Проверка контейнера
docker compose --profile with-osrm ps osrm

# Проверка логов
docker compose --profile with-osrm logs osrm

# Тестовый запрос
curl "http://localhost:5001/route/v1/driving/69.2401,41.3111;69.2797,41.3123"
```

**Решения:**

| Проблема | Решение |
|----------|---------|
| Контейнер не запущен | `docker compose --profile with-osrm up -d osrm` |
| Файлы .osrm отсутствуют | Подготовьте данные (см. DEPLOYMENT_GUIDE) |
| Недостаточно памяти | OSRM требует ~2-4GB RAM для страны |

### 5.2 VROOM возвращает ошибки

**Диагностика:**
```bash
# Логи VROOM
docker compose --profile with-osrm logs vroom

# Тестовый запрос
curl -X POST http://localhost:3000 \
  -H "Content-Type: application/json" \
  -d '{"vehicles":[{"id":1,"start":[69.24,41.31]}],"jobs":[{"id":1,"location":[69.28,41.31]}]}'
```

**Частые ошибки:**

| Ошибка | Причина | Решение |
|--------|---------|---------|
| "No route found" | Точка вне карты | Проверьте координаты |
| "Internal error" | OSRM недоступен | Проверьте OSRM_URL |
| Timeout | Слишком много точек | Уменьшите количество или используйте OR-Tools |

### 5.3 OR-Tools timeout

**Симптомы:**
- Оптимизация не завершается
- Возврат suboptimal решения

**Решения:**
```bash
# Проверьте настройки таймаута в коде
# backend/app/services/ortools_solver.py
# TIME_LIMIT_SECONDS = 30  (по умолчанию)

# Для больших задач используйте Celery
# Задачи >100 точек автоматически уходят в фоновый режим
```

---

## 6. Проблемы с Celery

### 6.1 Задачи не выполняются

**Диагностика:**
```bash
# Статус worker'ов
docker compose exec celery celery -A app.core.celery_app inspect active

# Проверка очередей
docker compose exec celery celery -A app.core.celery_app inspect reserved

# Логи Celery
docker compose logs --tail=100 celery
```

**Решения:**

| Причина | Решение |
|---------|---------|
| Worker не запущен | `docker compose restart celery` |
| Redis недоступен | Проверьте Redis: `docker compose exec redis redis-cli ping` |
| Задача в DLQ | Проверьте failed tasks в Redis |

### 6.2 Celery Beat не запускает задачи

**Диагностика:**
```bash
# Логи Beat
docker compose logs celery-beat

# Проверка расписания
docker compose exec celery-beat celery -A app.core.celery_app inspect scheduled
```

**Решения:**
```bash
# Убедитесь, что только один beat запущен
docker compose ps | grep beat

# Перезапуск beat
docker compose restart celery-beat
```

### 6.3 Задачи застревают (stuck)

**Диагностика:**
```bash
# Проверка активных задач
docker compose exec celery celery -A app.core.celery_app inspect active

# Проверка reserved
docker compose exec celery celery -A app.core.celery_app inspect reserved
```

**Решения:**
```bash
# Отмена всех задач (ОСТОРОЖНО!)
docker compose exec celery celery -A app.core.celery_app purge

# Перезапуск worker'ов
docker compose restart celery
```

---

## 7. Проблемы с производительностью

### 7.1 Высокое использование CPU

**Диагностика:**
```bash
# Статистика контейнеров
docker stats

# Top процессов внутри контейнера
docker compose exec api top
```

**Решения:**
- Увеличьте количество workers в gunicorn
- Проверьте бесконечные циклы в коде
- Добавьте кэширование для частых запросов

### 7.2 Высокое использование памяти

**Диагностика:**
```bash
# Память контейнеров
docker stats --format "table {{.Name}}\t{{.MemUsage}}"

# Детальная информация
docker compose exec api cat /proc/meminfo
```

**Решения:**
- Проверьте memory leaks (особенно в Celery tasks)
- Уменьшите concurrency Celery worker'ов
- Настройте `max-tasks-per-child` для Celery

### 7.3 Медленные ответы API

**Диагностика:**
```bash
# Проверка времени ответа
curl -w "@-" -o /dev/null -s http://localhost/api/v1/health << 'EOF'
time_namelookup:  %{time_namelookup}s\n
time_connect:     %{time_connect}s\n
time_appconnect:  %{time_appconnect}s\n
time_pretransfer: %{time_pretransfer}s\n
time_redirect:    %{time_redirect}s\n
time_starttransfer: %{time_starttransfer}s\n
time_total:       %{time_total}s\n
EOF
```

**Решения:**
- Включите кэширование в Redis
- Добавьте индексы в БД
- Используйте async endpoints
- Проверьте N+1 queries

---

## 8. Диагностические команды

### 8.1 Быстрая диагностика системы

```bash
#!/bin/bash
# scripts/diagnose.sh

echo "=== Docker Status ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

echo -e "\n=== Resource Usage ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

echo -e "\n=== Health Checks ==="
curl -s http://localhost/api/v1/health/detailed | jq .

echo -e "\n=== Recent Errors ==="
docker compose logs --tail=20 api 2>&1 | grep -i error || echo "No errors found"

echo -e "\n=== Disk Space ==="
df -h | head -5

echo -e "\n=== Database Connections ==="
docker compose exec -T db psql -U routeuser -d routes -c "SELECT count(*) as connections FROM pg_stat_activity;"

echo -e "\n=== Redis Info ==="
docker compose exec -T redis redis-cli info | grep -E "connected_clients|used_memory_human"
```

### 8.2 Полезные однострочники

```bash
# Перезапуск всех сервисов
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart

# Просмотр логов в реальном времени
docker compose logs -f api celery

# Проверка сетевых соединений
docker compose exec api ss -tlnp

# Экспорт логов в файл
docker compose logs --no-color > /tmp/logs_$(date +%Y%m%d).txt

# Проверка конфигурации nginx
docker compose exec nginx nginx -t

# Перезагрузка nginx без остановки
docker compose exec nginx nginx -s reload
```

### 8.3 Контакты поддержки

При неразрешимых проблемах:
1. Соберите диагностику: `./scripts/diagnose.sh > diagnosis.txt`
2. Экспортируйте логи: `docker compose logs > logs.txt`
3. Создайте issue в репозитории с приложенными файлами

---

*Документация актуальна для версии 1.0.0*
