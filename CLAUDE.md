# Route Optimization Service MVP

## Контекст проекта
Создать микросервис для оптимизации маршрутов полевых сотрудников (SFA) и транспорта доставки. Интеграция с существующей ERP-системой.

## Бизнес-требования

### 1. Планирование торговых представителей (SFA)
- У каждого торгового представителя ~300 закреплённых клиентов
- Ежедневно нужно посетить 25-30 клиентов
- Недельный план = 5 рабочих дней × 25-30 визитов = 125-150 визитов
- Частота посещения клиентов: A-класс (2 раза/нед), B-класс (1 раз/нед), C-класс (1 раз/2 нед)
- Учёт рабочего времени: 09:00-18:00, среднее время визита 15-20 мин
- Учёт времени на перемещение между точками

### 2. Оптимизация маршрутов доставки
- Входные данные: список заказов с адресами и объёмами
- Ограничения: грузоподъёмность авто, временные окна доставки
- Выход: оптимальный маршрут для каждого авто
- Минимизация: общий пробег, количество авто, время доставки

## Технический стек (Open Source)

### Backend
- **Python 3.11+ / FastAPI** — REST API
- **Celery + Redis** — фоновые задачи расчёта маршрутов
- **PostgreSQL 15+ с PostGIS** — хранение геоданных

### Routing Engine (выбрать один)
- **VROOM** (Vehicle Routing Open-source Optimization Machine) — рекомендуется
- **Google OR-Tools** — для сложной оптимизации
- **OSRM** (Open Source Routing Machine) — матрица расстояний

### Frontend
- **React + TypeScript** или **Vue 3**
- **Leaflet + OpenStreetMap** — карты
- **TailwindCSS** — стили

## Структура проекта
```
route-optimizer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── agents.py      # CRUD торговых представителей
│   │   │   │   ├── clients.py     # CRUD клиентов
│   │   │   │   ├── planning.py    # Генерация недельного плана
│   │   │   │   ├── delivery.py    # Оптимизация доставки
│   │   │   │   └── routes.py      # Получение маршрутов
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── agent.py           # Торговый представитель
│   │   │   ├── client.py          # Клиент с геолокацией
│   │   │   ├── visit_plan.py      # План визитов
│   │   │   ├── vehicle.py         # Транспорт
│   │   │   └── delivery_route.py  # Маршрут доставки
│   │   ├── services/
│   │   │   ├── osrm_client.py     # Клиент OSRM API
│   │   │   ├── vroom_solver.py    # Решатель VRP через VROOM
│   │   │   ├── weekly_planner.py  # Алгоритм недельного планирования
│   │   │   └── route_optimizer.py # Оптимизация маршрутов
│   │   ├── tasks/
│   │   │   └── optimization.py    # Celery tasks
│   │   └── main.py
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   ├── WeeklyPlan/
│   │   │   ├── RouteList/
│   │   │   └── DeliveryOptimizer/
│   │   ├── pages/
│   │   ├── services/
│   │   └── stores/
│   └── Dockerfile
├── docker/
│   ├── osrm/                      # OSRM с картой Узбекистана
│   └── vroom/
└── docker-compose.yml
```

## Модели данных
```python
# models/client.py
class Client(Base):
    id: UUID
    external_id: str              # ID из ERP
    name: str
    address: str
    latitude: Decimal(9,6)
    longitude: Decimal(9,6)
    category: Enum['A', 'B', 'C'] # Частота посещений
    visit_duration_minutes: int = 15
    time_window_start: Time       # Окно работы клиента
    time_window_end: Time
    agent_id: UUID                # Закреплённый агент
    
# models/agent.py  
class Agent(Base):
    id: UUID
    external_id: str
    name: str
    start_latitude: Decimal       # Точка старта (офис/дом)
    start_longitude: Decimal
    work_start: Time = "09:00"
    work_end: Time = "18:00"
    max_visits_per_day: int = 30
    
# models/visit_plan.py
class VisitPlan(Base):
    id: UUID
    agent_id: UUID
    client_id: UUID
    planned_date: Date
    planned_time: Time
    sequence_number: int          # Порядок в маршруте
    status: Enum['planned', 'completed', 'skipped']
    
# models/vehicle.py
class Vehicle(Base):
    id: UUID
    name: str
    capacity_kg: Decimal
    capacity_volume: Decimal
    start_location: Point
    
# models/delivery_order.py
class DeliveryOrder(Base):
    id: UUID
    client_id: UUID
    weight_kg: Decimal
    volume: Decimal
    time_window_start: DateTime
    time_window_end: DateTime
    priority: int
```

## Ключевые алгоритмы

### 1. Недельное планирование SFA
```python
# services/weekly_planner.py

class WeeklyPlanner:
    """
    Алгоритм планирования недели для торгового представителя
    
    Логика:
    1. Получить всех клиентов агента
    2. Распределить по дням недели учитывая:
       - Категорию клиента (A=2 визита/нед, B=1, C=0.5)
       - Географическую близость (кластеризация)
       - Временные окна клиентов
    3. Для каждого дня оптимизировать порядок визитов (TSP)
    """
    
    def generate_weekly_plan(
        self, 
        agent_id: UUID, 
        week_start: date
    ) -> List[DailyPlan]:
        # 1. Загрузить клиентов агента
        clients = self.get_agent_clients(agent_id)
        
        # 2. Определить необходимые визиты на неделю
        required_visits = self.calculate_required_visits(clients)
        
        # 3. Кластеризация по географии (K-means или DBSCAN)
        clusters = self.cluster_by_geography(clients, n_clusters=5)
        
        # 4. Распределение по дням с балансировкой нагрузки
        daily_assignments = self.assign_to_days(
            required_visits, 
            clusters,
            max_per_day=30
        )
        
        # 5. Оптимизация порядка для каждого дня (TSP через VROOM)
        optimized_plans = []
        for day, clients in daily_assignments.items():
            route = self.optimize_day_route(agent_id, clients)
            optimized_plans.append(route)
            
        return optimized_plans
```

### 2. Оптимизация доставки (VRP)
```python
# services/vroom_solver.py

class VROOMSolver:
    """
    Решение Vehicle Routing Problem через VROOM
    
    VROOM API формат:
    - vehicles: список авто с capacity и start/end location
    - jobs: список точек доставки с amount и time windows
    - matrix: матрица расстояний (опционально, VROOM может сам)
    """
    
    async def solve_delivery_routes(
        self,
        orders: List[DeliveryOrder],
        vehicles: List[Vehicle],
        date: date
    ) -> List[DeliveryRoute]:
        
        # 1. Подготовить VROOM request
        vroom_request = {
            "vehicles": [
                {
                    "id": v.id,
                    "start": [v.start_lon, v.start_lat],
                    "end": [v.start_lon, v.start_lat],
                    "capacity": [v.capacity_kg],
                    "time_window": [work_start, work_end]
                }
                for v in vehicles
            ],
            "jobs": [
                {
                    "id": o.id,
                    "location": [o.client.longitude, o.client.latitude],
                    "amount": [o.weight_kg],
                    "time_windows": [[o.time_window_start, o.time_window_end]],
                    "service": 300  # 5 минут на разгрузку
                }
                for o in orders
            ]
        }
        
        # 2. Вызвать VROOM solver
        result = await self.vroom_client.solve(vroom_request)
        
        # 3. Преобразовать результат в маршруты
        return self.parse_vroom_response(result)
```

## API Endpoints
```yaml
# Planning API
POST /api/v1/planning/weekly
  - Генерация недельного плана для агента
  - Body: { agent_id, week_start_date }
  - Response: { plans: [...], total_distance_km, total_visits }

GET /api/v1/planning/agent/{agent_id}/week/{date}
  - Получить план на неделю

PUT /api/v1/planning/visit/{visit_id}
  - Обновить статус визита

# Delivery API  
POST /api/v1/delivery/optimize
  - Оптимизация маршрутов доставки
  - Body: { order_ids: [...], vehicle_ids: [...], date }
  - Response: { routes: [...], unassigned: [...], metrics }

GET /api/v1/delivery/route/{route_id}
  - Получить маршрут с геометрией для карты

# Reference API
GET /api/v1/agents
GET /api/v1/clients?agent_id=...
GET /api/v1/vehicles
```

## Docker Compose
```yaml
version: '3.8'
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/routes
      - REDIS_URL=redis://redis:6379
      - OSRM_URL=http://osrm:5000
      - VROOM_URL=http://vroom:3000
    depends_on:
      - db
      - redis
      - osrm
      - vroom

  celery:
    build: ./backend
    command: celery -A app.tasks worker -l info
    depends_on:
      - redis

  db:
    image: postgis/postgis:15-3.3
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  osrm:
    image: osrm/osrm-backend
    volumes:
      - ./docker/osrm/uzbekistan-latest.osrm:/data/map.osrm
    command: osrm-routed --algorithm mld /data/map.osrm

  vroom:
    image: vroomvrp/vroom-docker:v1.13.0
    environment:
      - VROOM_ROUTER=osrm
      - OSRM_URL=http://osrm:5000

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
```

## Подготовка карты Узбекистана для OSRM
```bash
# Скачать карту
wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf

# Подготовить для OSRM
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-partition /data/uzbekistan-latest.osrm
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-customize /data/uzbekistan-latest.osrm
```

## Этапы разработки MVP

### Фаза 1 (1-2 недели)
- [ ] Настройка инфраструктуры (Docker, OSRM, VROOM)
- [ ] Базовые модели и миграции
- [ ] CRUD API для агентов, клиентов, транспорта
- [ ] Интеграция с OSRM (матрица расстояний)

### Фаза 2 (2-3 недели)  
- [ ] Алгоритм недельного планирования SFA
- [ ] Интеграция с VROOM для оптимизации
- [ ] API планирования визитов
- [ ] Базовый UI с картой

### Фаза 3 (1-2 недели)
- [ ] Оптимизация маршрутов доставки (VRP)
- [ ] UI для доставки
- [ ] Экспорт маршрутов (PDF, мобильное приложение)

### Фаза 4 (1 неделя)
- [ ] Интеграция с Smartup ERP (REST API)
- [ ] Тестирование на реальных данных
- [ ] Документация

## Тестовые данные

Сгенерировать 300 клиентов в Ташкенте:
- Координаты в пределах города (41.2-41.4 lat, 69.1-69.4 lon)
- Распределение категорий: A=20%, B=50%, C=30%
- Случайные временные окна работы

## Критерии успеха MVP
1. Генерация недельного плана < 30 секунд
2. Оптимизация маршрута доставки 100 точек < 10 секунд
3. Сокращение общего пробега на 15-20% vs ручное планирование
4. Баланс нагрузки между днями ±10%

## Дополнительные улучшения (post-MVP)
- Учёт пробок (traffic-aware routing)
- Мобильное приложение для агентов
- Real-time трекинг и перепланирование
- ML для прогноза времени визита
- Интеграция с Yandex Maps API как альтернатива