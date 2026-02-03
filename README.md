# SFA Routing Service 🚛

Enterprise-grade microservice for optimizing routes for field sales representatives (SFA) and delivery transportation in Central Asia.

![Version](https://img.shields.io/badge/Version-1.2.1-blue)
![Status](https://img.shields.io/badge/Status-Production%20Ready-green)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-success)
![PostGIS](https://img.shields.io/badge/PostGIS-15-blue)
![Tests](https://img.shields.io/badge/Tests-200+-success)
![Security](https://img.shields.io/badge/Security-Audited-green)

## 🌟 Key Features

### 1. Advanced Routing & Optimization
- **Smart Solver Selection**: AI-powered solver selection between `VROOM`, `OR-Tools`, `Genetic Algorithm`, or `Greedy+2opt`.
- **Genetic Algorithm Solver**: For large-scale problems (300+ points) with pickup-delivery constraints.
- **FMCG Prioritization**: Routes generated based on stock levels, debt, and "Market Day" logic.
- **Predictive Rerouting**: Proactive route optimization BEFORE delays happen.
- **Dynamic Re-routing**: `POST /delivery/routes/{id}/reoptimize` to handle traffic or order changes on the fly.
- **Constraints**:
  - Vehicle capacity (weight/volume).
  - Time windows & Service times.
  - Driver breaks (Lunch/Prayer times).

### 2. Service Backbone (Integration)
- **Bulk Import API**: High-performance endpoint (`POST /bulk/orders`) for ERP interaction.
- **Event Webhooks**: Subscribe to events like `optimization.completed` via `POST /webhooks`.
- **Idempotency**: Built-in protection against duplicate requests using `Idempotency-Key` header.
- **Real-time Tracking**: WebSocket-based GPS tracking of agents and vehicles.

### 3. Performance & Scalability (v1.2)
- **H3 Spatial Indexing**: Uber H3-based geospatial queries (O(1) radius search).
- **Parallel Matrix Computation**: Concurrent OSRM requests with automatic caching.
- **Cache Warmer**: Proactive cache warming for critical data.
- **Event-Driven Pipeline**: Priority-based async event processing.

### 4. Security & Compliance (v1.2)
- **Coordinate Encryption**: Fernet-based encryption for sensitive location data.
- **Location Anonymization**: Multi-level precision reduction for analytics.
- **Geo Audit Logging**: Complete access trail for compliance.
- **GDPR Compliance**: Right to Erasure, Data Portability support.

### 5. Regional Specifics (Central Asia)
- **Uzbekistan/Kazakhstan Logic**:
  - Friday Prayer break handling.
  - "Bazaar Day" logic for specific markets.
  - Seasonal work hour adjustments (Summer schedule).
  - Traffic-aware ETA with regional multipliers.

---

## 🏗️ Architecture

```mermaid
graph TD
    Client[Mobile App / ERP] -->|HTTPS| Nginx[Nginx Proxy]
    Nginx -->|Proxy| API[FastAPI Backend]

    subgraph "Core Services"
        API -->|Async| Celery[Celery Workers]
        API -->|Read/Write| DB[(PostgreSQL + PostGIS)]
        API -->|Cache| Redis[(Redis)]
    end

    subgraph "Routing Engines"
        Celery -->|HTTP| OSRM[OSRM (Distance Matrix)]
        Celery -->|HTTP| VROOM[VROOM (Optimization)]
        Celery -->|Import| ORTools[Google OR-Tools]
        Celery -->|Native| Genetic[Genetic Algorithm]
    end

    subgraph "v1.2 Services"
        API --> EventPipeline[Event Pipeline]
        API --> H3Index[H3 Spatial Index]
        API --> ParallelMatrix[Parallel Matrix]
        API --> GeoSecurity[Geo Security]
    end

    subgraph "Real-time"
        Client -->|WebSocket| API
        API -->|PubSub| Redis
    end
```

> **Note:** This is a headless API service. All clients (mobile apps, ERP systems) interact via REST API and WebSocket.

---

## 🚀 Getting Started

### Prerequisites
- Docker Engine v24+
- Docker Compose v2+

### Quick Start (Development)

1.  **Clone & Setup**:
    ```bash
    git clone <repo>
    cd sfa-routing
    cp .env.example .env
    ```

2.  **Start Services**:
    ```bash
    docker compose up -d
    ```
    
    - API: [http://localhost:8000](http://localhost:8000)
    - Docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)

3.  **Run Migrations**:
    ```bash
    docker compose exec api alembic upgrade head
    ```

### Production Deployment

See [docs/DEPLOYMENT_GUIDE_RU.md](docs/DEPLOYMENT_GUIDE_RU.md) for detailed instructions on Nginx setup, SSL, and resource tuning.

```bash
# Production Launch
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📚 Documentation

- [**API Reference**](docs/API_REFERENCE.md): Detailed endpoint usage.
- [**Deployment Guide**](docs/DEPLOYMENT_GUIDE_RU.md): Production setup guide.
- [**Technical Audit**](docs/CTO_TECHNICAL_AUDIT.md): Architectural analysis.
- [**FMCG Requirements**](docs/FMCG_REQUIREMENTS.md): Domain logic specification.

## 🛠️ Tech Stack

| Category | Technology | Version |
|----------|------------|---------|
| **Backend** | FastAPI | 0.115.0 |
| | SQLAlchemy | 2.0.36 |
| | Pydantic | 2.9.2 |
| | Celery | 5.4.0 |
| **Database** | PostgreSQL + PostGIS | 15 |
| **Scientific** | NumPy | 2.0.2 |
| | SciPy | 1.14.1 |
| | OR-Tools | 9.11 |
| **Geospatial** | H3 (Uber) | 4.1.1 |
| | OSRM | v5.27.1 |
| **Security** | python-jose | 3.5.0 |
| | bcrypt | 4.2.0 |
| **Infra** | Docker, Nginx, GitHub Actions |

## 🧪 Testing

```bash
# Run All Tests (200+ tests)
docker compose exec api pytest

# Run Unit Tests Only
docker compose exec api pytest -m unit

# Run Integration Tests Only
docker compose exec api pytest -m integration

# Run Specific Module Tests
docker compose exec api pytest tests/test_genetic_solver.py
docker compose exec api pytest tests/test_geo_security.py

# Run Performance Benchmarks
docker compose exec api python scripts/performance_test.py
```

## 🔒 Security (v1.2.1)

All dependencies audited and patched (Feb 2026):

| Package | Fix | CVE |
|---------|-----|-----|
| aiohttp | 3.9.3 → 3.10.10 | CVE-2024-23334 |
| weasyprint | 60.2 → 62.3 | CVE-2024-28184 |
| python-jose | 3.3.0 → 3.5.0 | CVE-2024-33663, CVE-2024-33664 |
| passlib | Replaced with bcrypt | Deprecated |
| h3 | 3.7.7 → 4.1.1 | API migration |
| numpy | 1.26.4 → 2.0.2 | Performance |

## 🆕 What's New in v1.2

| Feature | Module | Description |
|---------|--------|-------------|
| Genetic Algorithm | `genetic_solver.py` | Large-scale VRP solving (300+ points) |
| Smart Selection | `solver_selector.py` | AI-powered solver selection |
| H3 Spatial Index | `spatial_index.py` | O(1) geospatial queries |
| Parallel Matrix | `parallel_matrix.py` | 4x faster OSRM computation |
| Cache Warmer | `cache_warmer.py` | Proactive cache warming |
| Event Pipeline | `event_pipeline.py` | Priority-based async events |
| Geo Security | `geo_security.py` | Encryption, GDPR, Audit |

See [CLAUDE.md](CLAUDE.md) for detailed documentation.

## 📄 License
MIT
