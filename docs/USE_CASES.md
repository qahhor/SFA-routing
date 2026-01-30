# SFA-Routing: Use Cases (Сценарии использования)

Документ описывает типичные бизнес-сценарии и их реализацию через API.

---

## 📋 Оглавление

1. [Недельное планирование SFA](#1-недельное-планирование-sfa)
2. [Ежедневная работа агента](#2-ежедневная-работа-агента)
3. [Оптимизация доставки](#3-оптимизация-доставки)
4. [Динамическая переоптимизация](#4-динамическая-переоптимизация)
5. [Интеграция с ERP](#5-интеграция-с-erp)
6. [Мониторинг флота в реальном времени](#6-мониторинг-флота-в-реальном-времени)

---

## 1. Недельное планирование SFA

### Бизнес-задача
Каждую пятницу диспетчер генерирует недельные планы для 20+ торговых представителей, учитывая:
- Категории клиентов (A: 2-3 раза/неделю, B: 1 раз, C: раз в 2 недели)
- Географическую близость точек
- Региональные особенности (обед, пятничная молитва)

### API Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Пятница вечер  │────▶│ POST /planning/ │────▶│  Понедельник    │
│  Диспетчер      │     │     weekly      │     │  Агенты получают│
│  запускает      │     │                 │     │  планы          │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Запросы

```bash
# 1. Генерация плана для агента
POST /api/v1/planning/weekly
{
  "agent_id": "uuid-агента",
  "week_start_date": "2024-02-05",
  "include_high_priority": true,
  "respect_categories": true
}

# Ответ:
{
  "agent_id": "...",
  "week_start": "2024-02-05",
  "week_end": "2024-02-09",
  "daily_plans": [
    {
      "date": "2024-02-05",
      "visits_count": 12,
      "total_distance_km": 35.5,
      "visits": [
        {
          "sequence": 1,
          "client_id": "...",
          "client_name": "Супермаркет Макро",
          "category": "A",
          "planned_time": "09:15",
          "duration_minutes": 25
        },
        ...
      ]
    },
    ...
  ],
  "summary": {
    "total_visits": 58,
    "a_class_visits": 15,
    "b_class_visits": 35,
    "c_class_visits": 8,
    "total_distance_km": 180.5
  }
}

# 2. Получение плана на день (для мобильного приложения агента)
GET /api/v1/planning/agent/{agent_id}/day/2024-02-05

# 3. Экспорт плана в PDF
GET /api/v1/export/daily-plan/{agent_id}/2024-02-05
# → application/pdf
```

---

## 2. Ежедневная работа агента

### Бизнес-задача
Агент выполняет визиты по плану, отмечает результаты, система отслеживает GPS.

### API Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Утро    │───▶│ Визит 1  │───▶│ Визит 2  │───▶│  Вечер   │
│ GET план │    │ PATCH    │    │ PATCH    │    │ Отчёт    │
│          │    │ complete │    │ skip     │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      │               │               │
      ▼               ▼               ▼
   WebSocket GPS updates каждые 30 сек
```

### Запросы

```bash
# 1. Утро: получение плана на сегодня
GET /api/v1/planning/agent/{agent_id}/day/2024-02-05

# 2. WebSocket: стриминг GPS координат
WS /ws/agents/{agent_id}
# Отправка каждые 30 сек:
{
  "type": "gps_update",
  "latitude": 41.315,
  "longitude": 69.285,
  "timestamp": "2024-02-05T10:30:00Z"
}

# 3. Завершение визита
PATCH /api/v1/planning/visits/{visit_id}
{
  "status": "completed",
  "actual_time": "10:45",
  "actual_duration_minutes": 20,
  "notes": "Заказ размещён на 500,000 сум",
  "order_amount": 500000
}

# 4. Пропуск визита (клиент закрыт)
PATCH /api/v1/planning/visits/{visit_id}
{
  "status": "skipped",
  "skip_reason": "client_closed",
  "notes": "Магазин закрыт на ремонт"
}

# 5. Обновление GPS локации агента
PATCH /api/v1/agents/{agent_id}/location
{
  "current_latitude": 41.320,
  "current_longitude": 69.275
}
```

---

## 3. Оптимизация доставки

### Бизнес-задача
Ежедневно в 18:00 система получает заказы на завтра и оптимизирует маршруты для 5 грузовиков.

### API Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 18:00        │     │ 18:05        │     │ 18:10        │
│ Импорт из ERP│────▶│ POST         │────▶│ Маршруты     │
│ POST /bulk   │     │ /optimize    │     │ готовы       │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Запросы

```bash
# 1. Массовый импорт заказов из ERP
POST /api/v1/bulk/orders
Headers:
  Idempotency-Key: erp-import-20240205-1800
{
  "orders": [
    {
      "external_id": "ERP-001",
      "client_external_id": "CLT-001",
      "weight_kg": 150,
      "volume_m3": 1.2,
      "time_window_start": "2024-02-06T09:00:00",
      "time_window_end": "2024-02-06T12:00:00",
      "priority": 8
    },
    {
      "external_id": "ERP-002",
      "client_external_id": "CLT-002",
      "weight_kg": 200,
      ...
    }
  ]
}

# Ответ:
{
  "successful": 45,
  "failed": 2,
  "duplicates": 0,
  "order_ids": ["uuid-1", "uuid-2", ...],
  "errors": [
    {"external_id": "ERP-999", "error": "Client not found"}
  ]
}

# 2. Оптимизация маршрутов
POST /api/v1/delivery/optimize
{
  "order_ids": ["uuid-1", "uuid-2", ...],
  "vehicle_ids": ["veh-1", "veh-2", "veh-3", "veh-4", "veh-5"],
  "date": "2024-02-06",
  "solver": "auto",
  "options": {
    "minimize_vehicles": true,
    "respect_time_windows": true,
    "max_route_duration_minutes": 600
  }
}

# Ответ:
{
  "optimization_id": "opt-123",
  "status": "completed",
  "solver_used": "vroom",
  "computation_time_ms": 1250,
  "routes": [
    {
      "id": "route-1",
      "vehicle_id": "veh-1",
      "vehicle_name": "Газель NN-001",
      "total_distance_km": 45.2,
      "total_duration_minutes": 180,
      "total_weight_kg": 1200,
      "utilization_percent": 80,
      "stops": [
        {
          "sequence": 1,
          "order_id": "uuid-1",
          "client_name": "Супермаркет Макро",
          "address": "ул. Навои 100",
          "planned_arrival": "09:15",
          "planned_departure": "09:30",
          "weight_kg": 150
        },
        ...
      ]
    },
    ...
  ],
  "unassigned": [],
  "summary": {
    "routes_count": 4,
    "orders_assigned": 45,
    "total_distance_km": 180.5,
    "total_duration_minutes": 720,
    "average_utilization_percent": 75
  }
}

# 3. Получение маршрутного листа PDF
GET /api/v1/export/route/{route_id}
# → PDF с картой, списком остановок, контактами клиентов
```

---

## 4. Динамическая переоптимизация

### Бизнес-задача
В 11:00 клиент отменяет заказ. Система автоматически переоптимизирует маршрут.

### API Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 11:00        │     │ Система      │     │ Водитель     │
│ Отмена заказа│────▶│ POST         │────▶│ получает     │
│ от клиента   │     │ /reoptimize  │     │ новый маршрут│
└──────────────┘     └──────────────┘     └──────────────┘
```

### Запросы

```bash
# 1. Отмена заказа (или изменение)
DELETE /api/v1/delivery/orders/{order_id}
# или
PATCH /api/v1/delivery/orders/{order_id}
{
  "status": "cancelled",
  "cancel_reason": "client_request"
}

# 2. Переоптимизация маршрута
POST /api/v1/delivery/routes/{route_id}/reoptimize
{
  "reason": "order_cancelled",
  "excluded_order_ids": ["cancelled-order-id"],
  "current_vehicle_location": {
    "latitude": 41.320,
    "longitude": 69.275
  }
}

# Ответ:
{
  "route_id": "route-1",
  "status": "reoptimized",
  "changes": {
    "stops_removed": 1,
    "stops_reordered": true,
    "distance_saved_km": 5.2,
    "time_saved_minutes": 15
  },
  "new_stops": [...],
  "affected_orders": ["order-2", "order-3"]
}

# 3. Webhook уведомление для ERP
# (автоматически отправляется)
POST https://your-erp.com/webhooks/sfa
{
  "event": "route.updated",
  "timestamp": "2024-02-06T11:05:00Z",
  "data": {
    "route_id": "route-1",
    "reason": "reoptimization",
    "changes": {...}
  }
}
```

---

## 5. Интеграция с ERP

### Бизнес-задача
SmartUp/1C отправляет заказы в SFA-Routing и получает статусы выполнения.

### Webhook Events

| Event | Описание | Когда отправляется |
|-------|----------|-------------------|
| `optimization.completed` | Оптимизация завершена | После POST /optimize |
| `route.updated` | Маршрут изменён | После reoptimize |
| `visit.completed` | Визит выполнен | После PATCH visit |
| `delivery.completed` | Доставка выполнена | После отметки водителя |

### Запросы

```bash
# 1. Подписка на события
POST /api/v1/webhooks/subscribe
{
  "url": "https://erp.company.com/api/sfa-webhooks",
  "events": [
    "optimization.completed",
    "route.updated",
    "delivery.completed"
  ],
  "secret": "webhook-secret-key-min-32-characters"
}

# 2. Пример входящего webhook в ERP
POST https://erp.company.com/api/sfa-webhooks
Headers:
  X-Webhook-Signature: sha256=abc123...
  X-Webhook-Timestamp: 1707220500
{
  "event": "delivery.completed",
  "timestamp": "2024-02-06T14:35:00Z",
  "data": {
    "order_id": "uuid",
    "external_id": "ERP-001",
    "delivered_at": "2024-02-06T14:30:00Z",
    "signature_url": "https://cdn.../signature.png",
    "notes": "Принято полностью"
  }
}

# 3. Верификация подписи (Python)
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## 6. Мониторинг флота в реальном времени

### Бизнес-задача
Диспетчер видит все машины на карте, получает алерты о задержках.

### WebSocket Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Мобильное    │     │ SFA-Routing  │     │ Диспетчер    │
│ приложение   │────▶│ WebSocket    │────▶│ Dashboard    │
│ водителя     │ GPS │ Hub          │push │ (карта)      │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Запросы

```javascript
// 1. Подключение диспетчера к WebSocket
const ws = new WebSocket('wss://api.example.com/ws/dispatcher');

ws.onopen = () => {
  // Подписка на все машины
  ws.send(JSON.stringify({
    type: 'subscribe',
    topics: ['fleet:all', 'alerts:delays']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'gps_update') {
    // Обновить позицию на карте
    updateVehicleMarker(data.vehicle_id, data.latitude, data.longitude);
  }

  if (data.type === 'delay_alert') {
    // Показать алерт
    showAlert(`Задержка: ${data.vehicle_name}, ${data.delay_minutes} мин`);
  }
};

// 2. Отправка GPS от водителя (мобильное приложение)
const driverWs = new WebSocket('wss://api.example.com/ws/driver/{vehicle_id}');

// Каждые 30 секунд
setInterval(() => {
  navigator.geolocation.getCurrentPosition((pos) => {
    driverWs.send(JSON.stringify({
      type: 'gps_update',
      latitude: pos.coords.latitude,
      longitude: pos.coords.longitude,
      speed: pos.coords.speed,
      timestamp: new Date().toISOString()
    }));
  });
}, 30000);
```

### REST API для мониторинга

```bash
# Статус всего флота
GET /api/v1/fleet/status

# Ответ:
{
  "total_vehicles": 10,
  "active": 8,
  "idle": 2,
  "vehicles": [
    {
      "id": "veh-1",
      "name": "Газель NN-001",
      "status": "en_route",
      "current_location": {
        "latitude": 41.320,
        "longitude": 69.275,
        "updated_at": "2024-02-06T11:30:00Z"
      },
      "current_route": {
        "id": "route-1",
        "progress_percent": 45,
        "completed_stops": 3,
        "remaining_stops": 4,
        "eta_completion": "2024-02-06T16:30:00Z"
      },
      "delay_minutes": 0
    },
    ...
  ]
}
```

---

## 📊 Метрики и KPI

### Доступные метрики через API

```bash
GET /api/v1/analytics/kpi?date_from=2024-02-01&date_to=2024-02-29

{
  "period": "2024-02",
  "sfa_metrics": {
    "total_visits_planned": 1200,
    "total_visits_completed": 1080,
    "completion_rate": 90.0,
    "average_visits_per_agent": 12.5,
    "on_time_rate": 85.0
  },
  "delivery_metrics": {
    "total_orders": 2500,
    "total_delivered": 2450,
    "delivery_rate": 98.0,
    "average_route_distance_km": 45.2,
    "average_utilization": 78.5
  },
  "optimization_metrics": {
    "total_optimizations": 150,
    "average_computation_time_ms": 1200,
    "solver_usage": {
      "vroom": 120,
      "ortools": 25,
      "genetic": 5
    }
  }
}
```

---

## 🔗 Связанные документы

- [API Reference](API_REFERENCE.md) - Полный справочник API
- [CLAUDE.md](../CLAUDE.md) - Техническая документация
- [examples/](../examples/) - Готовые примеры кода
