# Route Optimization Service

## 📊 Статус проекта: PRODUCTION READY v1.1 ✅

Микросервис enterprise-уровня для оптимизации маршрутов (SFA/VRP) с интеграцией ERP, вебхуками, real-time трекингом и продвинутой аналитикой.

**Версия 1.1 включает:**
- 🧠 Predictive Rerouting Engine (проактивная оптимизация)
- 📊 Traffic-aware ETA (региональные множители пробок)
- 🎯 Skill-based Assignment (matching агент-клиент)
- 📈 Customer Satisfaction Scoring

---

## 🏗 Архитектура системы

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Load Balancer (Nginx)                         │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTPS / WSS
┌──────────────────────────────────▼──────────────────────────────────┐
│                       BACKEND (FastAPI)                             │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │ REST API: bulk │ webhooks │ planning │ delivery │ health       ││
│  ├────────────────────────────────────────────────────────────────┤│
│  │ Real-time: WebSocket Manager │ GPS Tracker │ Notifier          ││
│  ├────────────────────────────────────────────────────────────────┤│
│  │ Solvers: VROOM │ OR-Tools │ Greedy │ SolverFactory             ││
│  └────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  PostgreSQL │      │    Redis    │      │   Celery    │
│   PostGIS   │      │   Pub/Sub   │      │   Workers   │
└─────────────┘      └─────────────┘      └──────┬──────┘
                                                  │
                           ┌──────────────────────┼──────────────┐
                           ▼                      ▼              ▼
                    ┌───────────┐          ┌───────────┐  ┌───────────┐
                    │   OSRM    │◄─────────│   VROOM   │  │ Webhook   │
                    │(матрицы)  │          │   (VRP)   │  │ Dispatch  │
                    └───────────┘          └───────────┘  └───────────┘
```

---

## 🚀 Новые возможности (v1.0)

### 1. Service Backbone
- **Bulk Import**: Загрузка тысяч заказов через `POST /bulk/orders`.
- **Webhooks**: Подписка на события (`optimization.completed`) для ERP.
- **Idempotency**: Безопасные повторные запросы.

### 2. Реальное время (Real-time)
- **GPS Трекинг**: WebSocket стриминг координат агентов.
- **Уведомления**: Push-сообщения диспетчерам.

### 3. Продвинутая Алгоритмика
- **FMCG Приоритеты**: Учет долгов, стоков, базарных дней.
- **Dynamic Re-routing**: Пересчет маршрута "на лету" (`/reoptimize`).

### 4. DevOps
- **Docker**: Multi-stage сборка (<200MB).
- **CI/CD**: GitHub Actions pipeline.
- **Monitoring**: JSON логи, Health checks.

---

## 🎯 Бизнес-требования

### 1. Планирование торговых представителей (SFA)
| Параметр | Значение |
|----------|----------|
| Клиентов на агента | ~300 |
| Визитов в день | 8-12 (оптимум), макс 15 |
| Рабочие часы | 09:00-18:00 (летом 07:00-17:00) |
| Время визита | 15-20 мин |
| Время в пути | ≤30% от рабочего дня |

**Частота посещений по категориям:**
- **A-класс**: 2-3 раза/неделю (приоритетные, top 20% выручки)
- **B-класс**: 1 раз/неделю (50% базы)
- **C-класс**: 1 раз/2 недели (long tail)

**Приоритизация визитов (FMCG):**
```
Приоритет = f(остатки, долг, промо, категория, риск_оттока)

1. Критические остатки (<3 дней)     +30 баллов
2. День зарплаты + долг              +25 баллов
3. Новый клиент (<30 дней)           +20 баллов
4. Активная промо-акция              +15 баллов
5. Высокий риск оттока (>0.7)        +25 баллов
```

### 2. Оптимизация доставки (VRP)
| Ограничение | Описание |
|-------------|----------|
| Грузоподъёмность | Вес и объём на авто (80-95% загрузка) |
| Временные окна | Время работы клиента |
| Приоритеты | 1-10, срочные заказы |
| Температурный режим | Холодильник для скоропортящихся |

**Цели оптимизации:**
- Минимизация общего пробега
- Минимизация количества авто
- Соблюдение временных окон
- Максимизация ожидаемой выручки (ML)

---

## 🌍 Региональная специфика (Центральная Азия)

### Узбекистан
| Фактор | Учёт в системе |
|--------|----------------|
| **Обеденный перерыв** | 13:00-14:00, избегать визитов |
| **Пятничная молитва** | 12:00-13:30, избегать визитов |
| **Дни зарплаты** | 5-е и 20-е число (±3 дня) |
| **Летний график** | Старт в 07:00 (июнь-август) |
| **Базарные дни** | Чорсу: сб-вс, Алайский: ежедневно |
| **Рамадан** | Сокращённый рабочий день |

### Казахстан
| Фактор | Учёт в системе |
|--------|----------------|
| **Пробки Алматы** | Утро 07:30-10:00, вечер 17:00-20:00 |
| **Дни зарплаты** | 10-е и 25-е число |
| **Региональные расстояния** | Многодневные маршруты |
| **Зимние условия** | Учёт закрытия дорог |

```python
# Пример использования региональных настроек
from app.services import weekly_planner_uz, weekly_planner_kz

# Узбекистан (по умолчанию)
plan = await weekly_planner_uz.generate_weekly_plan(agent, clients, week_start)

# Казахстан
plan = await weekly_planner_kz.generate_weekly_plan(agent, clients, week_start)
```

---

## 🛠 Технический стек

### Backend
| Компонент | Технология | Назначение |
|-----------|------------|------------|
| API | FastAPI | REST endpoints |
| ORM | SQLAlchemy 2.0 | Async database access |
| Миграции | Alembic | Database migrations |
| Очередь | Celery + Redis | Background tasks |
| БД | PostgreSQL + PostGIS | Геоданные |

### Routing Engines (гибридный подход)
| Движок | Роль | Когда использовать |
|--------|------|-------------------|
| **OSRM** | Матрица расстояний | Всегда для реальных расстояний |
| **VROOM** | Быстрый VRP solver | < 100 точек, простые ограничения |
| **OR-Tools** | Продвинутый solver | Сложные ограничения, > 100 точек |
| **Greedy+2opt** | Fallback с оптимизацией | При сбое других солверов, 85-90% качество |

### Frontend
| Компонент | Технология |
|-----------|------------|
| Framework | React 18 + TypeScript |
| State | Zustand + React Query |
| Maps | Leaflet + OpenStreetMap |
| Styles | TailwindCSS |

---

## 📁 Структура проекта

```
route-optimizer/
├── backend/
│   ├── app/
│   │   ├── api/routes/           # API endpoints
│   │   │   ├── agents.py         # CRUD агентов
│   │   │   ├── clients.py        # CRUD клиентов
│   │   │   ├── vehicles.py       # CRUD транспорта
│   │   │   ├── planning.py       # Недельное планирование
│   │   │   ├── delivery.py       # Оптимизация доставки
│   │   │   ├── export.py         # PDF экспорт
│   │   │   └── health.py         # Health checks
│   │   ├── core/
│   │   │   ├── config.py         # Настройки приложения
│   │   │   ├── database.py       # DB connection
│   │   │   ├── security.py       # Auth (TODO)
│   │   │   └── celery_app.py     # Celery config
│   │   ├── models/               # SQLAlchemy models
│   │   │   ├── agent.py
│   │   │   ├── client.py
│   │   │   ├── vehicle.py
│   │   │   ├── visit_plan.py
│   │   │   ├── delivery_order.py
│   │   │   └── delivery_route.py
│   │   ├── schemas/              # Pydantic schemas
│   │   ├── services/             # Бизнес-логика
│   │   │   ├── osrm_client.py    # OSRM API клиент
│   │   │   ├── vroom_solver.py   # VROOM solver
│   │   │   ├── ortools_solver.py # Google OR-Tools
│   │   │   ├── greedy_solver.py  # Fallback solver + 2-opt
│   │   │   ├── solver_interface.py # Strategy pattern
│   │   │   ├── weekly_planner.py # Недельное планирование
│   │   │   ├── route_optimizer.py # Оптимизация доставки
│   │   │   ├── rerouting.py      # Dynamic re-routing
│   │   │   ├── predictive_rerouting.py # Predictive engine ⭐ NEW
│   │   │   ├── analytics.py      # Advanced analytics ⭐ NEW
│   │   │   ├── clustering.py     # OSRM-based clustering
│   │   │   └── pdf_export.py     # PDF генерация
│   │   ├── integrations/
│   │   │   └── smartup_erp.py    # ERP интеграция
│   │   └── tasks/
│   │       └── optimization.py   # Celery tasks
│   ├── scripts/                  # Утилиты
│   │   ├── generate_test_data.py # Генерация тестовых данных
│   │   └── performance_test.py   # Тесты производительности
│   ├── tests/
│   ├── alembic/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/           # React компоненты
│   │   ├── pages/                # Страницы
│   │   ├── services/api.ts       # API клиент
│   │   ├── stores/               # Zustand stores
│   │   └── types/                # TypeScript types
│   └── Dockerfile
├── docker/
│   ├── osrm/                     # OSRM конфигурация
│   └── vroom/                    # VROOM конфигурация
├── docs/                         # Документация
│   ├── TECHNICAL_AUDIT.md        # Технический аудит
│   └── ORTOOLS_OSRM_ANALYSIS.md  # Анализ технологий
└── docker-compose.yml
```

---

## 🔧 Архитектура солверов (Strategy Pattern)

```python
# Автоматический выбор оптимального солвера
from app.services import SolverFactory, SolverType

# Автовыбор на основе характеристик задачи
solver = SolverFactory.get_solver(SolverType.AUTO, problem)

# Или явный выбор
solver = SolverFactory.get_solver(SolverType.ORTOOLS)

# Решение с fallback chain
result = await SolverFactory.solve_with_fallback(
    problem=problem,
    preferred=SolverType.VROOM
)
# Порядок: VROOM → OR-Tools → Greedy
```

**Логика выбора солвера:**
```
┌─────────────────────────────────────────────────────────────┐
│  IF points < 100 AND simple_constraints:                    │
│      → VROOM (быстро, 95-98% качество)                     │
│  ELIF pickup_delivery OR multi_depot OR points > 500:       │
│      → OR-Tools (медленнее, 98-99% качество)               │
│  ELIF all_solvers_fail:                                     │
│      → Greedy+2opt (85-90% качество, гарантия)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧠 Продвинутая аналитика (v1.1)

### Модуль `analytics.py`

#### 1. Динамическое время визита (ServiceTimeCalculator)
```python
from app.services.analytics import ServiceTimeCalculator

# Вместо фиксированных 15 минут
duration = ServiceTimeCalculator.calculate(
    category="A",           # A:25, B:15, C:10 мин базовое
    expected_sku_count=25,  # +3 мин за каждые 10 SKU
    is_new_client=True,     # x1.5 множитель
    has_active_promo=True,  # x1.2 множитель
    outstanding_debt=5000,  # x1.3 если >1000
)
# → 45 минут (вместо 15)
```

#### 2. Skill-based Assignment (SkillBasedAssignment)
```python
from app.services.analytics import SkillBasedAssignment, AgentSkills

# Профиль агента
agent = AgentSkills(
    agent_id=uuid,
    negotiation_level=4,      # 1-5
    product_knowledge=5,
    handles_key_accounts=True,
    debt_collection_certified=True,
)

# Расчёт fit score для A-клиента
score = SkillBasedAssignment.calculate_fit_score(
    agent=agent,
    client_category="A",
    has_debt=True,
)
# → 0.87 (высокий fit)
```

#### 3. Предиктивная частота визитов (PredictiveVisitFrequency)
```python
from app.services.analytics import PredictiveVisitFrequency, ClientVisitFeatures

features = ClientVisitFeatures(
    client_id=uuid,
    category="B",
    stock_days_remaining=2,   # Критично!
    churn_risk_score=0.8,     # Высокий риск
    days_since_last_order=10,
)

frequency = PredictiveVisitFrequency.predict(features)
# → 2.5 визита/неделю (вместо 1.0 по категории)
```

#### 4. Traffic-aware ETA (TrafficAwareETA)
```python
from app.services.analytics import TrafficAwareETA
from datetime import time

# Регионы: tashkent, almaty, samarkand, default
adjusted = TrafficAwareETA.adjust_duration(
    osrm_duration_seconds=1800,  # 30 мин по OSRM
    departure_time=time(8, 30),  # Утренний пик
    region="almaty",             # Алматы: x2.0 утром
)
# → 3600 секунд (60 мин с учётом пробок)
```

**Traffic Multipliers:**
| Регион | Утро (07:30-10:00) | Обед | Вечер (17:00-20:00) |
|--------|-------------------|------|---------------------|
| Ташкент | 1.6x | 1.2x | 1.7x |
| Алматы | 2.0x | 1.2x | 2.2x |
| Самарканд | 1.3x | 1.2x | 1.4x |

#### 5. Visit Outcome Feedback (VisitFeedbackProcessor)
```python
from app.services.analytics import VisitFeedbackProcessor, VisitFeedback, VisitOutcome

feedback = VisitFeedback(
    visit_id=uuid,
    client_id=client_uuid,
    agent_id=agent_uuid,
    outcome=VisitOutcome.COMPETITOR_PRESENT,
    competitor_name="Coca-Cola",
)

updates = VisitFeedbackProcessor.process(feedback)
# → {
#     "client_updates": {"frequency_adjustment": +0.5, "churn_risk_adjustment": +0.15},
#     "planning_hints": {"competitor_alert": True}
# }
```

#### 6. Customer Satisfaction Score
```python
from app.services.analytics import CustomerSatisfactionScore, ClientSatisfactionInputs

inputs = ClientSatisfactionInputs(
    client_id=uuid,
    total_visits=20,
    on_time_visits=18,
    successful_orders=14,
    complaints_count=1,
)

score = CustomerSatisfactionScore.calculate(inputs)
risk = CustomerSatisfactionScore.get_risk_level(score)
suggestions = CustomerSatisfactionScore.get_improvement_suggestions(inputs)
# → score=75.5, risk="medium", suggestions=["Improve conversion rate..."]
```

---

## 🔮 Предиктивная маршрутизация (v1.1)

### Модуль `predictive_rerouting.py`

**Proactive vs Reactive:**
```
Reactive (старое):  GPS deviation → Re-route (post-factum)
Proactive (новое):  Predict delay → Re-route BEFORE it happens
```

#### Мониторинг флота
```python
from app.services.predictive_rerouting import predictive_engine

# Проверка одного агента
check = await predictive_engine.check_schedule_feasibility(
    db=db,
    agent_id=agent_id,
    current_location=(41.311, 69.279),
)
# → ScheduleFeasibilityCheck(
#     is_feasible=False,
#     at_risk_visits=[uuid1, uuid2],
#     predicted_delays={uuid1: 25, uuid2: 40},
#     total_predicted_delay_minutes=65,
#     recommendations=["Proactive re-optimization recommended..."]
# )

# Автоматическая переоптимизация при пороге
result = await predictive_engine.check_and_trigger_proactive_reroute(
    db=db,
    agent_id=agent_id,
)
# → RerouteResult if delay > 20 min threshold

# Статус всего флота
status = await predictive_engine.get_fleet_status(db)
# → {
#     "total_agents": 25,
#     "on_track": 20,
#     "at_risk": 3,
#     "critical": 2,
#     "total_predicted_delay_minutes": 145
# }
```

#### Фоновый мониторинг
```python
# Запуск непрерывного мониторинга (каждые 30 мин)
await predictive_engine.start_monitoring(
    db_session_factory=get_db,
    check_interval_minutes=30,
)
```

**Пороги:**
| Порог | Значение | Действие |
|-------|----------|----------|
| WARNING | 15 мин | Alert диспетчеру |
| CRITICAL | 30 мин | Критический alert |
| AUTO_REROUTE | 20 мин | Автоматическая переоптимизация |

---

## 📊 Ожидаемые бизнес-результаты

| Метрика | До оптимизации | После | Улучшение |
|---------|----------------|-------|-----------|
| Точность ETA | ±20% | ±8% | +60% |
| Качество Greedy fallback | 70-75% | 85-90% | +15% |
| Визитов/день/агент | 8-10 | 12-14 | +40% |
| Опоздания | baseline | -25% | -25% |
| Travel ratio | 32% | 25% | -22% |
| A-client conversion | baseline | +10% | +10% |

---

## 🗄 Модели данных

### Основные сущности

```python
# Agent - Торговый представитель
class Agent:
    id: UUID
    external_id: str          # ID из ERP
    name: str
    start_latitude: Decimal   # Точка старта
    start_longitude: Decimal
    work_start: Time = "09:00"
    work_end: Time = "18:00"
    max_visits_per_day: int = 30

# Client - Клиент/торговая точка
class Client:
    id: UUID
    external_id: str
    name: str
    address: str
    latitude: Decimal
    longitude: Decimal
    category: Enum['A', 'B', 'C']  # Частота визитов
    visit_duration_minutes: int = 15
    time_window_start: Time
    time_window_end: Time
    agent_id: UUID  # Закреплённый агент

# Vehicle - Транспорт
class Vehicle:
    id: UUID
    name: str
    license_plate: str
    capacity_kg: Decimal
    capacity_volume_m3: Decimal
    work_start: Time = "08:00"
    work_end: Time = "20:00"

# VisitPlan - План визита
class VisitPlan:
    id: UUID
    agent_id: UUID
    client_id: UUID
    planned_date: Date
    planned_time: Time
    sequence_number: int
    status: Enum['planned', 'completed', 'skipped']

# DeliveryOrder - Заказ на доставку
class DeliveryOrder:
    id: UUID
    client_id: UUID
    weight_kg: Decimal
    time_window_start: DateTime
    time_window_end: DateTime
    priority: int = 1
    status: Enum['pending', 'assigned', 'delivered', 'failed']

# DeliveryRoute - Маршрут доставки
class DeliveryRoute:
    id: UUID
    vehicle_id: UUID
    route_date: Date
    total_distance_km: Decimal
    total_duration_minutes: int
    total_stops: int
    geometry: JSON  # GeoJSON
    status: Enum['draft', 'planned', 'in_progress', 'completed']
```

---

## 🌐 API Endpoints

### Planning API
```http
POST /api/v1/planning/weekly
  Body: { agent_id, week_start_date, week_number }
  → Генерация недельного плана

GET /api/v1/planning/agent/{id}/week/{date}
  → Получить план на неделю

PUT /api/v1/planning/visit/{id}
  Body: { status, notes }
  → Обновить статус визита
```

### Delivery API
```http
POST /api/v1/delivery/optimize
  Body: { order_ids, vehicle_ids, date }
  → Оптимизация маршрутов

GET /api/v1/delivery/routes?date=2024-01-15
  → Список маршрутов на дату

GET /api/v1/delivery/route/{id}
  → Маршрут с геометрией
```

### Export API
```http
GET /api/v1/export/daily-plan/{agent_id}/{date}
  → PDF дневного плана

GET /api/v1/export/weekly-plan/{agent_id}/{date}
  → PDF недельного плана

GET /api/v1/export/delivery-route/{route_id}
  → PDF маршрутного листа
```

### Reference Data API
```http
GET/POST /api/v1/agents
GET/POST /api/v1/clients
GET/POST /api/v1/vehicles
```

---

## 🐳 Docker Compose

```yaml
version: '3.8'
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://user:pass@db:5432/routes
      REDIS_URL: redis://redis:6379
      OSRM_URL: http://osrm:5000
      VROOM_URL: http://vroom:3000
    depends_on: [db, redis, osrm, vroom]

  celery:
    build: ./backend
    command: celery -A app.core.celery_app worker -l info

  db:
    image: postgis/postgis:15-3.3

  redis:
    image: redis:7-alpine

  osrm:
    image: osrm/osrm-backend
    command: osrm-routed --algorithm mld /data/map.osrm

  vroom:
    image: vroomvrp/vroom-docker:v1.13.0
    environment:
      VROOM_ROUTER: osrm
      OSRM_URL: http://osrm:5000

  frontend:
    build: ./frontend
    ports: ["3001:3000"]
```

---

## 📈 Roadmap (Выполнено)

### Фаза 1-2: Core & Refactoring ✅
- [x] Архитектура солверов
- [x] OSRM/VROOM интеграция

### Фаза 3: Service Backbone ✅
- [x] Bulk Import API
- [x] Webhook System
- [x] Idempotency Middleware

### Фаза 4: Algo Refinement ✅
- [x] Advanced Priority (Stock/Debt)
- [x] Dynamic Re-routing
- [x] Market constraints

### Фаза 5-6: Real-time & Observability ✅
- [x] WebSocket GPS Tracking
- [x] Structured Logging
- [x] Health Checks

### Фаза 7: DevOps ✅
- [x] Production Dockerfile
- [x] Nginx Proxy
- [x] CI/CD Pipeline

### Фаза 8: Strategic Analytics ✅ NEW
- [x] Динамическое время визита (ServiceTimeCalculator)
- [x] Skill-based Assignment (agent-client matching)
- [x] Предиктивная частота визитов
- [x] Traffic-aware ETA (региональные множители)
- [x] ETA Calibration (обучение на истории)
- [x] Greedy solver + 2-opt improvement
- [x] Predictive Rerouting Engine
- [x] Visit Outcome Feedback Loop
- [x] Customer Satisfaction Scoring

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [README.md](README.md) | Главная страница |
| [docs/DEPLOYMENT_GUIDE_RU.md](docs/DEPLOYMENT_GUIDE_RU.md) | Руководство по развертыванию |
| [docs/MONITORING_RU.md](docs/MONITORING_RU.md) | Настройка мониторинга |
| [docs/TROUBLESHOOTING_RU.md](docs/TROUBLESHOOTING_RU.md) | Устранение неполадок |
| [docs/PREFLIGHT_CHECKLIST.md](docs/PREFLIGHT_CHECKLIST.md) | Чеклист перед запуском |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Справочник API |
| [docs/TECHNICAL_AUDIT.md](docs/TECHNICAL_AUDIT.md) | Технический аудит |

---

## 🔗 Полезные ссылки

**Технологии:**
- [Google OR-Tools Routing](https://developers.google.com/optimization/routing)
- [OSRM Backend](https://github.com/Project-OSRM/osrm-backend)
- [VROOM Project](https://github.com/VROOM-Project/vroom)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Leaflet Maps](https://leafletjs.com)

**Конкуренты (для изучения):**
- [Relog](https://getrelog.com) — SaaS для B2B доставки (СНГ)
- [Logist.uno](https://logist.uno) — TMS для дистрибуции (Россия)
- [1С:TMS Логистика](https://solutions.1c.ru/catalog/tms/features) — Интеграция с 1С
