# SFA-Routing: Примеры использования

Эта папка содержит готовые примеры для быстрого старта с API.

## 📁 Структура

```
examples/
├── postman/                          # Postman коллекция
│   └── SFA-Routing-API.postman_collection.json
├── python/                           # Python примеры
│   ├── sfa_client.py                 # SDK клиент
│   ├── example_weekly_planning.py    # Недельное планирование
│   ├── example_delivery_optimization.py  # Оптимизация доставки
│   └── example_erp_integration.py    # Интеграция с ERP
└── README.md                         # Этот файл
```

---

## 🚀 Быстрый старт

### 1. Postman

1. Откройте Postman
2. Import → File → `postman/SFA-Routing-API.postman_collection.json`
3. Настройте переменную `base_url` (по умолчанию `http://localhost:8000`)
4. Выполните запрос **Login** для получения токена
5. Тестируйте остальные endpoints

### 2. Python SDK

```bash
# Установка зависимостей
pip install httpx

# Запуск примеров
cd examples/python
python example_weekly_planning.py
python example_delivery_optimization.py
python example_erp_integration.py
```

---

## 📋 Описание примеров

### `example_weekly_planning.py`
**Сценарий: Недельное планирование торгового представителя**

- Создание агента
- Создание клиентов категорий A/B/C
- Генерация недельного плана
- Просмотр плана по дням
- Отметка выполнения визитов

### `example_delivery_optimization.py`
**Сценарий: Оптимизация маршрутов доставки (VRP)**

- Создание транспорта с ограничениями
- Создание заказов с временными окнами
- Запуск оптимизации
- Анализ результатов
- Переоптимизация при отмене заказа

### `example_erp_integration.py`
**Сценарий: Интеграция с ERP системой**

- Регистрация webhook
- Массовый импорт заказов
- Пример обработчика webhook
- Синхронизация статусов

---

## 🔧 SDK Client (`sfa_client.py`)

```python
from sfa_client import SFAClient

# Инициализация
client = SFAClient("http://localhost:8000")
client.login("dispatcher", "password")

# Агенты
agents = client.agents.list()
agent = client.agents.create(name="Алишер", ...)
client.agents.update_location(agent_id, lat, lon)

# Клиенты
clients = client.clients.list(category="A")
client = client.clients.create(name="Магазин", ...)

# Планирование
plan = client.planning.generate_weekly(agent_id, "2024-02-05")
daily = client.planning.get_daily_plan(agent_id, "2024-02-05")
client.planning.update_visit(visit_id, status="completed")

# Доставка
order = client.delivery.create_order(client_id, weight_kg=100, ...)
routes = client.delivery.optimize(order_ids, vehicle_ids, date)
client.delivery.reoptimize(route_id, reason="order_cancelled")

# Массовый импорт
result = client.bulk.import_orders(orders, idempotency_key="key")
```

---

## 📊 Postman коллекция

Включает все endpoints:

| Категория | Endpoints |
|-----------|-----------|
| **Health** | Health Check, Detailed |
| **Auth** | Register, Login, Refresh, Me |
| **Agents** | List, Create, Get, Update Location |
| **Clients** | List, Create, Get, Filter |
| **Vehicles** | List, Create, Get |
| **Planning** | Generate Weekly, Get Plan, Update Visit |
| **Delivery** | Create Order, Optimize, Get Route, Reoptimize |
| **Bulk** | Import Orders |
| **Webhooks** | Subscribe, List |
| **Export** | Daily Plan PDF, Route Sheet PDF |

**Автоматизация:**
- Токены сохраняются автоматически после Login
- ID сущностей сохраняются для последующих запросов
- Idempotency-Key генерируется автоматически

---

## 🔗 Полезные ссылки

- [API Documentation](http://localhost:8000/api/v1/docs) - Swagger UI
- [CLAUDE.md](../CLAUDE.md) - Полная документация проекта
- [API Reference](../docs/API_REFERENCE.md) - Справочник API
