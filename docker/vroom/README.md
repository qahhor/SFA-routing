# VROOM Setup

VROOM (Vehicle Routing Open-source Optimization Machine) is used for solving
Vehicle Routing Problems (VRP).

## Configuration

VROOM connects to OSRM for routing calculations. The docker-compose.yml
is configured to connect VROOM to the OSRM service.

## API Usage

VROOM accepts POST requests with JSON body:

```bash
curl -X POST http://localhost:3000 \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [69.2401, 41.2995],
        "end": [69.2401, 41.2995],
        "capacity": [1000]
      }
    ],
    "jobs": [
      {
        "id": 1,
        "location": [69.2787, 41.3123],
        "amount": [50],
        "service": 300
      },
      {
        "id": 2,
        "location": [69.2500, 41.3000],
        "amount": [30],
        "service": 300
      }
    ]
  }'
```

## Response

VROOM returns optimized routes with:
- Route sequence
- Total distance and duration
- Arrival times at each stop
- Unassigned jobs (if any)

## Documentation

See full VROOM API documentation at:
https://github.com/VROOM-Project/vroom/blob/master/docs/API.md
