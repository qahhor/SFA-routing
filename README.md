# SFA Routing Service 🚛

Enterprise-grade microservice for optimizing routes for field sales representatives (SFA) and delivery transportation in Central Asia.

![Status](https://img.shields.io/badge/Status-Production%20Ready-green)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-success)
![PostGIS](https://img.shields.io/badge/PostGIS-15-blue)

## 🌟 Key Features

### 1. Advanced Routing & Optimization
- **Hybrid Solver Engine**: Automatically selects between `VROOM` (speed), `OR-Tools` (complex constraints), or `Greedy` (fallback).
- **FMCG Prioritization**: Routes generated based on stock levels, debt, and "Market Day" logic.
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

### 3. Regional Specifics (Central Asia)
- **Uzbekistan/Kazakhstan Logic**:
  - Friday Prayer break handling.
  - "Bazaar Day" logic for specific markets.
  - Seasonal work hour adjustments (Summer schedule).

---

## 🏗️ Architecture

```mermaid
graph TD
    Client[Mobile/Web Client] -->|HTTPS| Nginx[Nginx Proxy]
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
    end
    
    subgraph "Real-time"
        Client -->|WebSocket| API
        API -->|PubSub| Redis
    end
```

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
- **Infra**: Docker, Nginx, GitHub Actions (CI/CD)
- **Observability**: JSON Logging, Health Checks (`/health`)

## 🧪 Testing

```bash
# Run Unit & Integration Tests
docker compose exec api pytest

# Run Performance Benchmarks
docker compose exec api python scripts/performance_test.py
```

## 📄 License
MIT
