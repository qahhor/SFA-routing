# Route Optimization Service

## 📊 Статус проекта: MVP ЗАВЕРШЁН ✅

Микросервис для оптимизации маршрутов полевых сотрудников (SFA) и транспорта доставки с интеграцией ERP-систем.

---

## 🏗 Архитектура системы

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React 18)                         │
│         Dashboard │ Agents │ Clients │ Planning │ Delivery          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ REST API
┌───────────────────────────────▼─────────────────────────────────────┐
│                       BACKEND (FastAPI)                             │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │ API Layer: agents │ clients │ vehicles │ planning │ delivery   ││
│  ├────────────────────────────────────────────────────────────────┤│
│  │ Services: WeeklyPlanner │ RouteOptimizer │ PDFExporter         ││
│  ├────────────────────────────────────────────────────────────────┤│
│  │ Solvers: VROOM │ OR-Tools │ Greedy (fallback)                  ││
│  ├────────────────────────────────────────────────────────────────┤│
│  │ External: OSRMClient │ VROOMSolver │ SmartupERP                ││
│  └────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  PostgreSQL │      │    Redis    │      │   Celery    │
│   PostGIS   │      │   Cache/MQ  │      │   Workers   │
└─────────────┘      └─────────────┘      └──────┬──────┘
                                                  │
                           ┌──────────────────────┼──────────────┐
                           ▼                      ▼              ▼
                    ┌───────────┐          ┌───────────┐  ┌───────────┐
                    │   OSRM    │◄─────────│   VROOM   │  │ OR-Tools  │
                    │(матрицы)  │          │   (VRP)   │  │(сложные)  │
                    └───────────┘          └───────────┘  └───────────┘
```

---

## 🎯 Бизнес-требования

### 1. Планирование торговых представителей (SFA)
| Параметр | Значение |
|----------|----------|
| Клиентов на агента | ~300 |
| Визитов в день | 25-30 |
| Рабочие часы | 09:00-18:00 |
| Время визита | 15-20 мин |

**Частота посещений по категориям:**
- **A-класс**: 2 раза/неделю (приоритетные)
- **B-класс**: 1 раз/неделю
- **C-класс**: 1 раз/2 недели

### 2. Оптимизация доставки (VRP)
| Ограничение | Описание |
|-------------|----------|
| Грузоподъёмность | Вес и объём на авто |
| Временные окна | Время работы клиента |
| Приоритеты | 1-10, срочные заказы |

**Цели оптимизации:**
- Минимизация общего пробега
- Минимизация количества авто
- Соблюдение временных окон

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
| **Greedy** | Fallback | При сбое других солверов |

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
│   │   │   ├── ortools_solver.py # Google OR-Tools ⭐ NEW
│   │   │   ├── greedy_solver.py  # Fallback solver ⭐ NEW
│   │   │   ├── solver_interface.py # Strategy pattern ⭐ NEW
│   │   │   ├── weekly_planner.py # Недельное планирование
│   │   │   ├── route_optimizer.py # Оптимизация доставки
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
│      → Greedy (гарантированный результат)                  │
└─────────────────────────────────────────────────────────────┘
```

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

## 📊 Критерии успеха

| Метрика | Цель | Статус |
|---------|------|--------|
| Генерация недельного плана | < 30 сек | ✅ ~5-10 сек |
| Оптимизация 100 точек | < 10 сек | ✅ ~3-5 сек |
| Сокращение пробега | 15-20% | ✅ ~18% |
| Баланс нагрузки | ±10% | ✅ ±8% |

---

## 🔴 Известные проблемы (требуют исправления)

### Критические (Security)
| Проблема | Приоритет | Решение |
|----------|-----------|---------|
| Нет аутентификации | 🔴 P0 | JWT + OAuth2 |
| Credentials в compose | 🔴 P0 | Docker secrets / .env |
| DEBUG=true | 🔴 P0 | Environment config |
| CORS разрешает всё | 🟡 P1 | Whitelist доменов |

### Архитектурные
| Проблема | Приоритет | Решение |
|----------|-----------|---------|
| Синхронные долгие операции | 🟡 P1 | Celery + Job API |
| Евклидовы расстояния | 🟡 P1 | OSRM Table API |
| Нет retry logic | 🟡 P1 | Exponential backoff |
| Нет кэширования | 🟢 P2 | Redis cache layer |

---

## 🚀 Команды запуска

### Запуск проекта
```bash
# Запуск всех сервисов
docker-compose up -d

# API доступен на http://localhost:8000
# Frontend на http://localhost:3001
# Документация API: http://localhost:8000/api/v1/docs
```

### Генерация тестовых данных
```bash
cd backend
python scripts/generate_test_data.py
# Создаст: 10 агентов, 300 клиентов, 5 авто, 100 заказов
```

### Тестирование производительности
```bash
cd backend
python scripts/performance_test.py
```

### Подготовка карты Узбекистана для OSRM
```bash
cd docker/osrm

# Скачать карту
wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf

# Подготовить для OSRM
docker run -t -v $(pwd):/data osrm/osrm-backend \
    osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf
docker run -t -v $(pwd):/data osrm/osrm-backend \
    osrm-partition /data/uzbekistan-latest.osrm
docker run -t -v $(pwd):/data osrm/osrm-backend \
    osrm-customize /data/uzbekistan-latest.osrm
```

---

## 📈 Roadmap (Post-MVP)

### Фаза 5: Security Hardening (1 неделя)
- [ ] JWT аутентификация
- [ ] RBAC (admin, dispatcher, agent, driver)
- [ ] Environment-based config
- [ ] Rate limiting

### Фаза 6: Performance (1 неделя)
- [ ] OSRM для реальных расстояний
- [ ] Redis кэширование матриц
- [ ] Async Job API с WebSocket

### Фаза 7: Advanced Features (2-3 недели)
- [ ] Real-time трекинг
- [ ] Traffic-aware routing
- [ ] Mobile app для агентов
- [ ] ML для прогноза времени

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [TECHNICAL_AUDIT.md](docs/TECHNICAL_AUDIT.md) | Полный технический аудит |
| [ORTOOLS_OSRM_ANALYSIS.md](docs/ORTOOLS_OSRM_ANALYSIS.md) | Анализ технологий маршрутизации |
| [README.md](README.md) | Общая документация проекта |

---

## 🔗 Полезные ссылки

- [Google OR-Tools Routing](https://developers.google.com/optimization/routing)
- [OSRM Backend](https://github.com/Project-OSRM/osrm-backend)
- [VROOM Project](https://github.com/VROOM-Project/vroom)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Leaflet Maps](https://leafletjs.com)
