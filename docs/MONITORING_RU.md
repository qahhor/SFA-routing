# Мониторинг SFA-Routing

## Оглавление

1. [Обзор системы мониторинга](#1-обзор-системы-мониторинга)
2. [Метрики приложения](#2-метрики-приложения)
3. [Настройка Prometheus](#3-настройка-prometheus)
4. [Настройка Grafana](#4-настройка-grafana)
5. [Алерты](#5-алерты)
6. [Логирование](#6-логирование)
7. [Health Checks](#7-health-checks)

---

## 1. Обзор системы мониторинга

### 1.1 Архитектура мониторинга

```
┌─────────────────────────────────────────────────────────────────┐
│                         Grafana                                  │
│                    (Визуализация)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Prometheus                                │
│                  (Сбор и хранение метрик)                       │
└─────────────────────────────────────────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐       ┌──────────┐       ┌──────────┐
    │   API    │       │  Celery  │       │  Redis   │
    │ /metrics │       │ Exporter │       │ Exporter │
    └──────────┘       └──────────┘       └──────────┘
```

### 1.2 Типы метрик

| Тип | Описание | Примеры |
|-----|----------|---------|
| **Counter** | Только увеличивается | Количество запросов, ошибок |
| **Gauge** | Может увеличиваться/уменьшаться | Активные соединения, память |
| **Histogram** | Распределение значений | Время ответа, размер запроса |
| **Summary** | Квантили распределения | Задержка P99 |

---

## 2. Метрики приложения

### 2.1 HTTP метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `http_requests_total` | Counter | Общее количество HTTP запросов |
| `http_request_duration_seconds` | Histogram | Время обработки запросов |
| `http_requests_in_progress` | Gauge | Текущие активные запросы |

**Labels (метки):**
- `method`: GET, POST, PUT, DELETE
- `endpoint`: /api/v1/planning, /api/v1/delivery, etc.
- `status_code`: 200, 400, 500, etc.

### 2.2 Метрики солверов

| Метрика | Тип | Описание |
|---------|-----|----------|
| `solver_jobs_total` | Counter | Количество задач оптимизации |
| `solver_duration_seconds` | Histogram | Время выполнения оптимизации |
| `solver_quality_score` | Gauge | Качество найденного решения (0-1) |

**Labels:**
- `solver_type`: vroom, ortools, greedy
- `status`: success, error, timeout

### 2.3 Метрики базы данных

| Метрика | Тип | Описание |
|---------|-----|----------|
| `db_connections_active` | Gauge | Активные соединения с БД |
| `db_connections_idle` | Gauge | Простаивающие соединения |
| `db_query_duration_seconds` | Histogram | Время выполнения запросов |

### 2.4 Метрики кэширования

| Метрика | Тип | Описание |
|---------|-----|----------|
| `cache_hits_total` | Counter | Попадания в кэш |
| `cache_misses_total` | Counter | Промахи кэша |
| `cache_size_bytes` | Gauge | Размер кэша |

### 2.5 Бизнес-метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `routes_optimized_total` | Counter | Оптимизированных маршрутов |
| `visits_planned_total` | Counter | Запланированных визитов |
| `optimization_savings_percent` | Gauge | Экономия от оптимизации (%) |

---

## 3. Настройка Prometheus

### 3.1 Docker Compose конфигурация

Добавьте в `docker-compose.prod.yml`:

```yaml
  prometheus:
    image: prom/prometheus:v2.47.0
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - route-network

volumes:
  prometheus_data:
```

### 3.2 prometheus.yml

Создайте `monitoring/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:
  - "/etc/prometheus/rules/*.yml"

scrape_configs:
  # API метрики
  - job_name: 'sfa-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  # Redis метрики
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # PostgreSQL метрики
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Node метрики (хост)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

### 3.3 Проверка метрик

```bash
# Прямой доступ к метрикам API
curl http://localhost:8000/metrics

# Проверка Prometheus
curl http://localhost:9090/api/v1/targets
```

---

## 4. Настройка Grafana

### 4.1 Docker Compose конфигурация

```yaml
  grafana:
    image: grafana/grafana:10.1.0
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=CHANGE_ME
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    networks:
      - route-network

volumes:
  grafana_data:
```

### 4.2 Рекомендуемые дашборды

#### Dashboard: API Overview

**Панели:**
1. **Request Rate** - Запросов в секунду
   ```promql
   rate(http_requests_total[5m])
   ```

2. **Error Rate** - Процент ошибок
   ```promql
   sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100
   ```

3. **Response Time P95** - 95-й перцентиль времени ответа
   ```promql
   histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
   ```

4. **Active Connections** - Активные соединения
   ```promql
   http_requests_in_progress
   ```

#### Dashboard: Optimization Performance

**Панели:**
1. **Optimization Jobs** - Задач оптимизации
   ```promql
   rate(solver_jobs_total[1h])
   ```

2. **Solver Duration** - Время оптимизации по солверам
   ```promql
   histogram_quantile(0.95, rate(solver_duration_seconds_bucket[5m])) by (solver_type)
   ```

3. **Solution Quality** - Качество решений
   ```promql
   avg(solver_quality_score) by (solver_type)
   ```

4. **Solver Success Rate** - Успешность солверов
   ```promql
   sum(rate(solver_jobs_total{status="success"}[1h])) / sum(rate(solver_jobs_total[1h])) * 100
   ```

---

## 5. Алерты

### 5.1 Правила алертов

Создайте `monitoring/prometheus/rules/alerts.yml`:

```yaml
groups:
  - name: sfa-routing-alerts
    rules:
      # Высокий уровень ошибок
      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Высокий уровень ошибок API"
          description: "Более 5% запросов завершаются ошибкой в течение 5 минут"

      # API не отвечает
      - alert: APIDown
        expr: up{job="sfa-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API сервис недоступен"
          description: "SFA-Routing API не отвечает более 1 минуты"

      # Медленные ответы
      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Медленное время ответа API"
          description: "P95 время ответа превышает 5 секунд"

      # Высокое использование памяти
      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Высокое использование памяти"
          description: "Контейнер использует более 90% доступной памяти"

      # База данных перегружена
      - alert: DatabaseConnectionsHigh
        expr: db_connections_active > 180
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Много активных соединений с БД"
          description: "Более 180 активных соединений (лимит 200)"

      # Очередь Celery переполнена
      - alert: CeleryQueueBacklog
        expr: celery_queue_length > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Большая очередь задач Celery"
          description: "В очереди более 100 задач в течение 10 минут"
```

### 5.2 Настройка уведомлений (Alertmanager)

```yaml
# monitoring/alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'telegram'

receivers:
  - name: 'telegram'
    telegram_configs:
      - bot_token: 'YOUR_BOT_TOKEN'
        chat_id: YOUR_CHAT_ID
        message: |
          {{ range .Alerts }}
          🚨 *{{ .Labels.alertname }}*
          Severity: {{ .Labels.severity }}
          {{ .Annotations.description }}
          {{ end }}
```

---

## 6. Логирование

### 6.1 Структура логов

Все логи в JSON формате для удобного парсинга:

```json
{
  "timestamp": "2025-01-29T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.api.routes.planning",
  "message": "Weekly plan generated",
  "request_id": "abc-123-def",
  "agent_id": "agent-456",
  "duration_ms": 1523,
  "visits_count": 45
}
```

### 6.2 Просмотр логов

```bash
# Все логи API
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api

# Фильтрация по уровню
docker compose logs api 2>&1 | jq 'select(.level == "ERROR")'

# Поиск по request_id
docker compose logs api 2>&1 | jq 'select(.request_id == "abc-123-def")'

# Последние 100 ошибок
docker compose logs api 2>&1 | jq 'select(.level == "ERROR")' | tail -100
```

### 6.3 Интеграция с ELK Stack (опционально)

Для централизованного логирования добавьте Filebeat:

```yaml
  filebeat:
    image: elastic/filebeat:8.10.0
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./monitoring/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
    environment:
      - ELASTICSEARCH_HOST=elasticsearch:9200
```

---

## 7. Health Checks

### 7.1 Эндпоинты проверки здоровья

| Эндпоинт | Описание |
|----------|----------|
| `GET /api/v1/health` | Базовая проверка (fast) |
| `GET /api/v1/health/detailed` | Детальная проверка всех компонентов |

### 7.2 Пример ответа /health/detailed

```json
{
  "status": "healthy",
  "timestamp": "2025-01-29T10:30:45.123Z",
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 5
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1
    },
    "celery": {
      "status": "healthy",
      "workers": 4,
      "queued_tasks": 2
    },
    "osrm": {
      "status": "healthy",
      "latency_ms": 45
    },
    "vroom": {
      "status": "healthy",
      "latency_ms": 12
    }
  }
}
```

### 7.3 Внешний мониторинг

Рекомендуемые сервисы для внешнего мониторинга:
- **UptimeRobot** (бесплатно до 50 мониторов)
- **Pingdom**
- **StatusCake**

Настройка:
1. URL: `https://api.yourdomain.com/api/v1/health`
2. Интервал: 1-5 минут
3. Ожидаемый ответ: `{"status":"healthy"}`
4. Уведомления: Email, Telegram, Slack

---

## Чеклист мониторинга

- [ ] Prometheus собирает метрики
- [ ] Grafana дашборды настроены
- [ ] Алерты сконфигурированы
- [ ] Уведомления работают (Telegram/Email)
- [ ] Логи доступны и парсятся
- [ ] Внешний мониторинг настроен
- [ ] Health check эндпоинты отвечают

---

*Документация актуальна для версии 1.0.0*
