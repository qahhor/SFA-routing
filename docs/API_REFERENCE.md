# API Reference 📡

This document provides a reference for the key APIs in the SFA-Routing service. For interactive documentation and testing, use the Swagger UI at `/api/v1/docs` when running the service.

> **Status Legend:**
> - ✅ **Implemented** - Ready for use
> - 📋 **Planned** - Service layer exists, REST endpoints coming soon

---

## 1. Health API ✅

### Basic Health Check
**GET** `/api/v1/health`

Returns basic service health status.

**Response:**
```json
{
  "status": "healthy",
  "app": "Route Optimization Service",
  "version": "1.2.1"
}
```

### Detailed Health Check
**GET** `/api/v1/health/detailed`

Returns detailed health status including all dependencies.

**Response:**
```json
{
  "status": "healthy",
  "checks": {
    "api": "healthy",
    "database": "healthy",
    "osrm": "healthy",
    "vroom": "healthy",
    "redis": "healthy"
  }
}
```

---

## 2. TSP API ✅ (Traveling Salesperson Problem)

### Solve TSP
**POST** `/api/v1/tsp`

Generates optimal route for a salesperson visiting multiple points over a 4-week period.

**Request:**
```json
{
  "kind": "auto",
  "depot": {"longitude": 69.279, "latitude": 41.311},
  "points": [
    {"id": "1", "longitude": 69.28, "latitude": 41.32, "visit_intensity": "ONCE_A_WEEK"}
  ],
  "working_hours_start": "09:00",
  "working_hours_end": "18:00",
  "average_service_time_minutes": 15
}
```

**Kinds:**
- `auto` - Generate multiple optimal plans (with clustering)
- `single` - Generate one optimal plan

**Visit Intensities:**
- `THREE_TIMES_A_WEEK` - 3 visits/week (Mon, Wed, Fri)
- `TWO_TIMES_A_WEEK` - 2 visits/week (Mon, Thu)
- `ONCE_A_WEEK` - 1 visit/week
- `ONCE_IN_TWO_WEEKS` - 1 visit/2 weeks
- `ONCE_A_MONTH` - 1 visit/month

---

## 3. VRPC API ✅ (Vehicle Routing Problem with Capacity)

### Solve VRPC
**POST** `/vrpc`

Generates optimal routes for multiple vehicles with capacity constraints.

**Request:**
```json
{
  "depot": {"longitude": 69.279, "latitude": 41.311},
  "vehicles": [
    {"id": "V1", "capacity": 1000}
  ],
  "jobs": [
    {"id": "J1", "longitude": 69.28, "latitude": 41.32, "demand": 100}
  ]
}
```

---

## 4. Authentication

All endpoints (except `/health`) require authentication via `API Key` or `JWT`.

### Headers
```http
Authorization: Bearer <token>
X-API-Key: <your-api-key>
```

---

## 5. Planning API 📋 (SFA)

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

## 6. Delivery API 📋 (VRP) & Dynamic Re-routing

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

### Smart Solver Selection

The system automatically selects the best solver based on problem characteristics:

| Problem Size | Constraints | Selected Solver |
|--------------|-------------|-----------------|
| < 150 jobs | Simple | VROOM |
| < 300 jobs | Complex | OR-Tools |
| > 300 jobs | Any | Genetic Algorithm |
| Fallback | Any failure | Greedy + 2-opt |

---

## 7. Service Backbone 📋 (Integration)

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
  }
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

---

## 8. Real-time API 📋

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

## 9. Event Pipeline API 📋 (v1.2)

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

## 10. Geo Security API 📋 (v1.2)

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

### GDPR Data Deletion
**DELETE** `/api/v1/gdpr/user/{user_id}`

Delete all user data for GDPR compliance (Right to Erasure).

---

## 11. Spatial Index API 📋 (v1.2)

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

## 12. Cache Management API 📋 (v1.2)

### Warm Caches
**POST** `/api/v1/admin/cache/warm`

Trigger proactive cache warming for specific resources.

**Request:**
```json
{
  "targets": ["distance_matrices", "reference_data", "daily_plans"],
  "agent_ids": ["uuid1", "uuid2"]
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

---

## Service Availability Summary

| API | Status | Endpoint |
|-----|--------|----------|
| Health | ✅ Implemented | `/api/v1/health` |
| TSP | ✅ Implemented | `/api/v1/tsp` |
| VRPC | ✅ Implemented | `/vrpc` |
| Planning | 📋 Planned | Service layer ready |
| Delivery | 📋 Planned | Service layer ready |
| Bulk Import | 📋 Planned | Service layer ready |
| Webhooks | 📋 Planned | Service layer ready |
| Real-time | 📋 Planned | WebSocket manager ready |
| Events | 📋 Planned | Event pipeline ready |
| Geo Security | 📋 Planned | Service layer ready |
| Spatial | 📋 Planned | H3 index ready |
| Cache | 📋 Planned | Cache warmer ready |

> **Note:** The service layer for planned endpoints is fully implemented. REST endpoint exposure is pending based on deployment requirements.
