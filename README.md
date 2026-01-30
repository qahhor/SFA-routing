# SFA Routing Service 🚛

Enterprise-grade microservice for optimizing routes for field sales representatives (SFA) and delivery transportation in Central Asia.

![Version](https://img.shields.io/badge/Version-1.2-blue)
![Status](https://img.shields.io/badge/Status-Production%20Ready-green)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-success)
![PostGIS](https://img.shields.io/badge/PostGIS-15-blue)
![Tests](https://img.shields.io/badge/Tests-200+-success)

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

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions on Nginx setup, SSL, and resource tuning.

```bash
# Production Launch
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📚 Documentation

- [**API Reference**](docs/API_REFERENCE.md): Detailed endpoint usage.
- [**Deployment Guide**](docs/DEPLOYMENT.md): Production setup guide.
- [**Technical Audit**](docs/TECHNICAL_AUDIT.md): Architectural analysis.
- [**FMCG Requirements**](docs/FMCG_REQUIREMENTS.md): Domain logic specification.

## 🛠️ Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0 (Async)
- **Database**: PostgreSQL 15 + PostGIS
- **Queue**: Celery + Redis
- **Solvers**: VROOM, OR-Tools, Genetic Algorithm, Greedy+2opt
- **Geo**: H3 (Uber), OSRM, Parallel Matrix
- **Security**: Fernet Encryption, GDPR Compliance
- **Infra**: Docker, Nginx, GitHub Actions (CI/CD)
- **Observability**: JSON Logging, Health Checks (`/health`)

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
