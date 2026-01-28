# Route Optimization Service

A microservice for optimizing routes for field sales representatives (SFA) and delivery transportation. Integrates with existing ERP systems.

## Features

### Sales Force Automation (SFA)
- **Weekly Planning**: Automatic generation of weekly visit plans for sales representatives
- **Client Categories**: Support for A/B/C client classification with different visit frequencies
  - Category A: 2 visits per week
  - Category B: 1 visit per week
  - Category C: 1 visit every 2 weeks
- **Geographic Clustering**: K-means clustering for efficient daily route grouping
- **Route Optimization**: TSP-based optimization for daily visit sequences

### Delivery Optimization
- **Vehicle Routing Problem (VRP)**: Multi-vehicle route optimization
- **Capacity Constraints**: Support for weight and volume limits
- **Time Windows**: Delivery time window constraints
- **Priority Handling**: Order priority-based optimization

## Tech Stack

### Backend
- **Python 3.11+** with **FastAPI**
- **PostgreSQL 15** with **PostGIS** for geospatial data
- **Celery + Redis** for background task processing
- **SQLAlchemy 2.0** with async support
- **Alembic** for database migrations

### Optimization Engines
- **VROOM** - Vehicle Routing Open-source Optimization Machine
- **OSRM** - Open Source Routing Machine for distance matrices

### Frontend
- **React 18** with **TypeScript**
- **Leaflet** + **OpenStreetMap** for maps
- **TailwindCSS** for styling
- **Zustand** for state management
- **React Query** for server state

## Project Structure

```
route-optimizer/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # API endpoints
│   │   ├── core/             # Configuration, security, database
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── tasks/            # Celery tasks
│   ├── tests/                # Test suite
│   └── alembic/              # Database migrations
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/            # Page components
│   │   ├── services/         # API client
│   │   └── stores/           # State management
└── docker/
    ├── osrm/                 # OSRM configuration
    └── vroom/                # VROOM configuration
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Running with Docker

```bash
# Clone the repository
git clone <repository-url>
cd route-optimizer

# Start all services
docker-compose up -d

# The API will be available at http://localhost:8000
# The frontend will be available at http://localhost:3001
# API documentation at http://localhost:8000/api/v1/docs
```

### Running with OSRM (for real routing)

```bash
# First, prepare OSRM data (see docker/osrm/README.md)
# Then start with OSRM profile:
docker-compose --profile with-osrm up -d
```

### Local Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/routes"
export REDIS_URL="redis://localhost:6379"

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

### Planning API
- `POST /api/v1/planning/weekly` - Generate weekly plan for an agent
- `GET /api/v1/planning/agent/{agent_id}/week/{date}` - Get weekly plan
- `PUT /api/v1/planning/visit/{visit_id}` - Update visit status

### Delivery API
- `POST /api/v1/delivery/optimize` - Optimize delivery routes
- `GET /api/v1/delivery/routes` - List routes for a date
- `GET /api/v1/delivery/route/{route_id}` - Get route with geometry

### Reference Data API
- `GET /api/v1/agents` - List agents
- `GET /api/v1/clients` - List clients
- `GET /api/v1/vehicles` - List vehicles

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `OSRM_URL` | OSRM service URL | `http://localhost:5000` |
| `VROOM_URL` | VROOM service URL | `http://localhost:3000` |
| `SECRET_KEY` | JWT secret key | - |

## Testing

```bash
cd backend
pytest
```

## OSRM Setup for Uzbekistan

See [docker/osrm/README.md](docker/osrm/README.md) for instructions on setting up OSRM with Uzbekistan map data.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   FastAPI   │────▶│  PostgreSQL │
│   (React)   │     │   Backend   │     │   PostGIS   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Celery    │
                    │   Workers   │
                    └─────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌───────────┐  ┌───────────┐  ┌───────────┐
     │   Redis   │  │   OSRM    │  │   VROOM   │
     │           │  │           │  │           │
     └───────────┘  └───────────┘  └───────────┘
```

## License

MIT
