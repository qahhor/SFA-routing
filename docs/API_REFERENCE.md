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
