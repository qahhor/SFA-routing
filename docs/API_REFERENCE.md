# API Reference 📡

This document provides a reference for the key APIs in the SFA-Routing service. For interactive documentation and testing, use the Swagger UI at `/api/v1/docs` when running the service.

## 1. Authentication

All endpoints (except `/health`) require authentication via `API Key` or `JWT`.

### Headers
```http
Authorization: Bearer <token>
X-API-Key: <your-api-key>
```

---

## 2. Planning API (SFA)

### Generate Weekly Plan
**POST** `/api/v1/planning/weekly`

Generates an optimized visit plan for a sales agent for the specified week, respecting client categories and frequencies.

**Request:**
```json
{
  "agent_id": "uuid",
  "week_start_date": "2023-10-23",
  "week_number": 43
}
```

**Response:**
Returns a `WeeklyPlanResponse` containing `daily_plans` with sequenced visits.

---

## 3. Delivery API (VRP) & Dynamic Re-routing

### Optimize Routes
**POST** `/api/v1/delivery/optimize`

Creates optimal routes for a set of orders and vehicles using the configured solver (VROOM/OR-Tools).

**Request:**
```json
{
  "order_ids": ["uuid1", "uuid2"],
  "vehicle_ids": ["uuidV1", "uuidV2"],
  "route_date": "2023-10-24"
}
```

### Re-optimize Active Route (Dynamic)
**POST** `/api/v1/delivery/routes/{route_id}/reoptimize`

Recalculates an existing `PLANNED` route. Useful if orders are added/removed or traffic conditions change significantly. The system preserves completed stops and re-sequences the remainder.

---

## 4. Service Backbone (Integration)

### Bulk Order Import
**POST** `/api/v1/bulk/orders`

High-performance endpoint for verifying and loading thousands of orders from ERP.

**Request:**
```json
[
  {
    "external_id": "ORD-001",
    "client_external_id": "CL-100",
    "weight_kg": 50.5,
    "delivery_date": "2023-10-25"
  },
  ...
]
```

### Webhook Subscriptions
**POST** `/api/v1/webhooks`

Subscribe to system events.

**Request:**
```json
{
  "name": "ERP Sync",
  "url": "https://erp.example.com/webhooks/sfa",
  "events": ["optimization.completed"],
  "secret": "my-shared-secret"
}
```

### Health Checks
- **GET** `/api/v1/health`: Returns 200 OK (Generic).
- **GET** `/api/v1/health/detailed`: Checks Database, Redis, OSRM, and VROOM connections.

---

## 5. Real-time API

### WebSocket Connection
**WS** `/ws?token=<jwt_token>`

Establishes a persistent connection for real-time updates.

**Events (Server -> Client):**
- `gps_update`: Location update of an agent/vehicle.
- `route_update`: Notification of route changes.
- `notification`: System alerts.

### Send Notification
**POST** `/api/v1/realtime/notify`

Broadcasts a message to connected clients (dispatchers/agents).

**Request:**
```json
{
  "user_id": "uuid",
  "title": "Route Changed",
  "message": "New urgent order added to your route.",
  "priority": "high"
}
```

---

## 6. Solver Selection API (v1.2)

### Smart Solver Selection
**POST** `/api/v1/delivery/optimize`

The system automatically selects the best solver based on problem characteristics:

| Problem Size | Constraints | Selected Solver |
|--------------|-------------|-----------------|
| < 150 jobs | Simple | VROOM |
| < 300 jobs | Complex | OR-Tools |
| > 300 jobs | Any | Genetic Algorithm |
| Fallback | Any failure | Greedy + 2-opt |

**Request with solver hint:**
```json
{
  "order_ids": ["uuid1", "uuid2"],
  "vehicle_ids": ["uuidV1"],
  "route_date": "2024-01-24",
  "solver_preference": "auto"  // or "vroom", "ortools", "genetic"
}
```

---

## 7. Event Pipeline API (v1.2)

### Submit Event
**POST** `/api/v1/events`

Submit events to the event-driven processing pipeline.

**Request:**
```json
{
  "event_type": "gps_update",
  "agent_id": "uuid",
  "latitude": 41.311,
  "longitude": 69.279,
  "priority": "normal"
}
```

**Event Types:**
| Type | Priority | Description |
|------|----------|-------------|
| `gps_update` | normal | Agent location update |
| `traffic_alert` | high | Traffic condition change |
| `order_cancel` | high | Order cancellation |
| `visit_complete` | normal | Visit status update |

---

## 8. Geo Security API (v1.2)

### Anonymize Location
**POST** `/api/v1/geo/anonymize`

Anonymize coordinates for analytics or sharing.

**Request:**
```json
{
  "latitude": 41.311081,
  "longitude": 69.279737,
  "level": "medium"
}
```

**Response:**
```json
{
  "anonymized_latitude": 41.31,
  "anonymized_longitude": 69.28,
  "precision_meters": 1000
}
```

**Levels:** `low` (3 decimals, ~100m), `medium` (2 decimals, ~1km), `high` (1 decimal, ~10km)

### GDPR Data Export
**GET** `/api/v1/gdpr/export/{user_id}`

Export all user data for GDPR compliance (Data Portability).

**Response:**
```json
{
  "user_id": "uuid",
  "export_date": "2024-01-24T10:00:00Z",
  "data": {
    "visits": [...],
    "locations": [...],
    "audit_logs": [...]
  }
}
```

### GDPR Data Deletion
**DELETE** `/api/v1/gdpr/user/{user_id}`

Delete all user data for GDPR compliance (Right to Erasure).

---

## 9. Spatial Index API (v1.2)

### Query Nearby Entities
**GET** `/api/v1/spatial/nearby`

Find entities within a radius using H3 spatial indexing.

**Query Parameters:**
- `lat` (float): Center latitude
- `lon` (float): Center longitude
- `radius_meters` (int): Search radius (default: 1000)
- `entity_type` (string): "agent", "client", or "all"

**Response:**
```json
{
  "center": {"lat": 41.311, "lon": 69.279},
  "radius_meters": 1000,
  "results": [
    {"id": "uuid", "type": "client", "distance_m": 250},
    {"id": "uuid", "type": "agent", "distance_m": 500}
  ]
}
```

---

## 10. Cache Management API (v1.2)

### Warm Caches
**POST** `/api/v1/admin/cache/warm`

Trigger proactive cache warming for specific resources.

**Request:**
```json
{
  "targets": ["distance_matrices", "reference_data", "daily_plans"],
  "agent_ids": ["uuid1", "uuid2"]  // optional
}
```

### Invalidate Cache
**DELETE** `/api/v1/admin/cache/invalidate`

Invalidate specific cache entries.

**Request:**
```json
{
  "patterns": ["agent:*", "matrix:*:uuid"],
  "reason": "data_update"
}
```
