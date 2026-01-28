# FMCG Route Optimization: Requirements and Nuances

## Overview

This document captures domain-specific requirements for route optimization in FMCG (Fast-Moving Consumer Goods) distribution, with focus on Central Asia market specifics.

---

## Part 1: Sales Force Automation (SFA)

### 1.1 Visit Frequency by Client Category

| Category | Frequency | Description |
|----------|-----------|-------------|
| **A** | 2-3 times/week | High-value clients, top 20% revenue |
| **B** | 1 time/week | Medium clients, 50% of base |
| **C** | 1-2 times/month | Low-frequency, long tail |
| **Special** | On-demand | Promo launches, audits, problem resolution |

### 1.2 Time Windows

```
Factors to consider:
├── Store working hours
├── Optimal visit time (morning before customer rush)
├── Lunch breaks (typically 13:00-14:00)
├── Delivery days (avoid visiting on stock delivery days)
└── Standard visit duration: 15-30 minutes
```

### 1.3 Visit Prioritization Algorithm

Priority score calculation:

```python
def calculate_visit_priority(client, context):
    """
    Calculate visit priority score (higher = more urgent).

    Returns: float 0-100
    """
    score = 0

    # 1. Stock levels (critical = high priority)
    if client.stock_days_remaining < 3:
        score += 30  # Critical stock
    elif client.stock_days_remaining < 7:
        score += 15  # Low stock

    # 2. Order history patterns
    if is_expected_order_day(client):
        score += 20

    # 3. Debt/receivables (collect on payday)
    if client.outstanding_debt > 0:
        if is_payday_period():
            score += 25
        else:
            score += 10

    # 4. Active promotions
    if has_active_promo(client):
        score += 15

    # 5. New clients (need more attention)
    if client.age_days < 30:
        score += 20
    elif client.age_days < 90:
        score += 10

    # 6. Seasonality
    score += get_seasonal_boost(client)

    # 7. Churn risk
    if client.churn_risk_score > 0.7:
        score += 25

    return min(score, 100)
```

### 1.4 Load Balancing Rules

| Parameter | Optimal | Maximum | Notes |
|-----------|---------|---------|-------|
| Visits per day | 8-12 | 15 | Dense urban areas allow more |
| Travel time % | 30% | 40% | Rest is actual visit time |
| Buffer time | 15-20% | - | For emergencies |
| Reporting time | 30 min | - | End of day |

### 1.5 Geographic Factors

```yaml
Urban areas:
  - Higher density = more visits possible
  - Traffic peaks: 08:00-09:30, 17:00-19:00
  - Parking availability critical
  - Consider one-way streets

Rural areas:
  - Lower density = fewer visits
  - Road quality varies
  - Fuel availability
  - Mobile coverage gaps
  - Cluster visits by district
```

---

## Part 2: Delivery Optimization

### 2.1 Vehicle Parameters

```python
@dataclass
class VehicleConstraints:
    # Capacity
    max_weight_kg: float
    max_volume_m3: float

    # Temperature
    has_refrigeration: bool
    min_temp_celsius: Optional[float]
    max_temp_celsius: Optional[float]

    # Access
    vehicle_height_m: float  # For low bridges/tunnels
    vehicle_length_m: float  # For tight streets

    # Operations
    requires_loader: bool
    unload_time_minutes: int = 5

    # Driver
    driver_work_start: time
    driver_work_end: time
    max_driving_hours: float = 8
    required_break_after_hours: float = 4
```

### 2.2 Order Characteristics

| Parameter | Type | Impact on Routing |
|-----------|------|-------------------|
| Weight | float | Vehicle capacity |
| Volume | float | Vehicle capacity |
| Fragility | enum | Loading order (fragile on top) |
| Temperature | enum | Vehicle selection |
| Urgency | 1-10 | Priority |
| Time window | range | Hard constraint |

### 2.3 Order Consolidation Rules

```
1. Geographic clustering
   - Group orders by district/zone
   - Cluster radius: 2-5 km urban, 10-20 km rural

2. Vehicle utilization targets
   - Weight: 80-95% capacity
   - Volume: 80-95% capacity
   - Never exceed 100%

3. Multi-tier delivery
   - Warehouse → Regional hub → End point
   - Cross-docking optimization

4. Delivery priority
   ├── Urgent orders
   ├── Perishables (short shelf life)
   ├── Large orders (VIP clients)
   ├── Geographic proximity
   └── Client time windows
```

---

## Part 3: Central Asia Regional Specifics

### 3.1 Uzbekistan Market

#### Infrastructure

| Factor | Challenge | Mitigation |
|--------|-----------|------------|
| Road quality | Variable, especially outside cities | Factor in road type for ETA |
| Traffic (Tashkent) | Heavy 08:00-10:00, 17:00-19:00 | Schedule visits outside peaks |
| GPS coverage | Good in cities, gaps in rural | Offline mode support |
| Mobile data | 3G/4G in cities, limited rural | Batch sync capability |

#### Cultural Factors

```yaml
Daily schedule impacts:
  lunch_break: "13:00-14:00"
  friday_prayer: "12:00-13:30"  # Many stores close

Seasonal considerations:
  ramadan:
    - Shorter work hours
    - Evening shopping peak
    - Adjust visit times to 09:00-12:00 or 16:00-18:00

  navruz_period:  # March 21-23
    - Store closures
    - No deliveries planned

  summer_heat:  # June-August
    - Early morning visits preferred (07:00-11:00)
    - Afternoon rest period
    - Cold chain critical
```

#### Business Patterns

```python
UZBEKISTAN_PATTERNS = {
    # Payday typically 5th and 20th of month
    "payday_dates": [5, 20],
    "payday_window_days": 3,  # Increased demand ±3 days

    # Market (bazaar) days vary by region
    "market_days": {
        "chorsu": ["saturday", "sunday"],
        "alaysky": ["daily"],  # Always busy
        "regional_markets": ["thursday", "sunday"],
    },

    # Seasonal peaks
    "seasonal_peaks": {
        "march": 1.3,  # Navruz preparation
        "december": 1.4,  # New Year
        "ramadan_end": 1.5,  # Eid celebration
    }
}
```

### 3.2 Kazakhstan Specifics

```yaml
Almaty considerations:
  traffic: "Severe, especially center"
  best_delivery_hours: "06:00-09:00, 20:00-22:00"

Regional distances:
  - Long distances between cities
  - Multi-day routes common
  - Regional warehouse strategy important

Weather:
  winter: "Severe, road closures possible"
  spring_floods: "Access issues in some regions"
```

---

## Part 4: KPI Framework

### 4.1 Sales Representative KPIs

#### Efficiency Metrics

| KPI | Target | Formula |
|-----|--------|---------|
| Visits per day | 10 | count(completed_visits) |
| Plan completion | >90% | completed / planned |
| Travel/Visit ratio | 30/70 | travel_time / total_time |
| Visit-to-order conversion | >70% | orders / visits |
| Avg ticket per visit | varies | total_revenue / visits |
| Territory coverage | >95% | visited_clients / total_clients |

#### Quality Metrics

| KPI | Target | Notes |
|-----|--------|-------|
| On-time arrival | >85% | Within 30 min of scheduled |
| Task completion | 100% | Merchandising, audit tasks |
| Customer satisfaction | >4.0/5 | From feedback |
| Photo compliance | 100% | Required photos taken |

### 4.2 Delivery KPIs

#### Operational

| KPI | Target | Formula |
|-----|--------|---------|
| Vehicle utilization | >80% | actual_load / max_capacity |
| Orders per route | 15-25 | depends on area |
| Km per order | <5 urban | total_km / orders |
| On-time delivery | >95% | on_time / total |
| First-attempt success | >90% | successful / attempts |

#### Financial

| KPI | Target | Formula |
|-----|--------|---------|
| Cost per delivery | <$3 | total_cost / deliveries |
| Fuel per 100km | <12L | fuel / (distance/100) |
| Cost per km | <$0.50 | total_cost / total_km |
| Revenue per route | varies | depends on orders |

---

## Part 5: Algorithm Requirements

### 5.1 Core VRP Variants Needed

```
Required algorithms:
├── CVRP: Capacitated VRP (weight + volume)
├── VRPTW: VRP with Time Windows
├── MDVRP: Multi-Depot VRP (multiple warehouses)
├── PDVRP: Pickup-Delivery VRP (returns handling)
└── DVRP: Dynamic VRP (real-time adjustments)
```

### 5.2 Dynamic Factors for ML

```python
# Input features for ML-based optimization
DYNAMIC_FEATURES = {
    # Historical
    "avg_travel_time_by_hour": "Historical travel times",
    "avg_service_time_by_client": "Time spent at each client",
    "success_probability": "Likelihood of successful visit",

    # Real-time
    "current_traffic": "Live traffic data",
    "weather": "Weather conditions",
    "client_availability": "Is contact person present",

    # Business
    "stock_levels": "Client inventory data",
    "order_probability": "ML prediction of order",
    "order_size_prediction": "ML prediction of order value",
    "churn_risk": "Client churn probability",
}
```

### 5.3 Real-time Adjustments

```yaml
Trigger events:
  - New urgent order
  - Visit cancellation
  - Traffic incident
  - Vehicle breakdown
  - Client unavailable
  - Weather change

Response actions:
  - Re-route remaining visits
  - Reassign to nearby vehicle
  - Reschedule to next available slot
  - Notify affected parties
```

---

## Part 6: Smartup Integration Points

### 6.1 Data Sources for Optimization

```
Sales Module:
├── Order history
├── Average ticket by client
├── Order frequency
├── Client category
└── Sales targets

Warehouse Module:
├── Product availability
├── Stock levels
├── Expiry dates
├── Reserved inventory
└── Picking times

Finance Module:
├── Outstanding debt
├── Payment discipline
├── Credit limits
├── Payment terms
└── Collection priorities

Visits Module:
├── GPS coordinates
├── Actual visit times
├── Visit outcomes
├── Photos/evidence
└── Agent feedback
```

### 6.2 Smart Order Integration

```python
# Combine predictions with routing
async def optimize_with_predictions(agent_id, date):
    # Get ML predictions for all clients
    predictions = await smart_order_service.predict_orders(
        agent_id=agent_id,
        date=date
    )

    # Prioritize clients by predicted order value
    clients = []
    for client_id, prediction in predictions.items():
        clients.append({
            "client_id": client_id,
            "predicted_order_value": prediction.value,
            "predicted_probability": prediction.probability,
            "priority": calculate_visit_priority(
                client_id,
                prediction
            )
        })

    # Optimize route with weighted priorities
    route = await route_optimizer.optimize(
        agent_id=agent_id,
        clients=clients,
        date=date,
        objective="maximize_expected_value"
    )

    return route
```

---

## Part 7: Special Scenarios

### 7.1 Promotional Campaigns

```yaml
Pre-promotion (1 week before):
  - Increase visit frequency
  - Distribute promo materials
  - Train store staff
  - Ensure adequate stock

During promotion:
  - Daily monitoring visits for A-clients
  - 2x/week for B-clients
  - Stock replenishment priority
  - Competitor monitoring

Post-promotion:
  - Audit visits (promo compliance)
  - Collect feedback
  - Remove expired materials
  - Return to normal frequency
```

### 7.2 New Client Onboarding

```
Week 1-2: 3 visits/week
  - Initial setup
  - Product training
  - Merchandising setup

Week 3-4: 2 visits/week
  - Performance check
  - Adjustments
  - Address issues

Month 2-3: 1 visit/week
  - Stabilization
  - Routine established

Month 4+: Category-based frequency
```

### 7.3 Debt Collection Routes

```python
def plan_collection_route(region, date):
    """
    Special route for debt collection.
    Best executed on/near payday dates.
    """
    # Get debtors in region
    debtors = get_clients_with_debt(region)

    # Filter by collectability
    collectible = [
        d for d in debtors
        if d.debt_age_days < 90  # Not too old
        and d.payment_probability > 0.3
    ]

    # Sort by amount * probability
    collectible.sort(
        key=lambda x: x.debt_amount * x.payment_probability,
        reverse=True
    )

    # Plan route with top candidates
    # Limit to max 8-10 collection visits per day
    return optimize_route(
        clients=collectible[:10],
        objective="maximize_collection"
    )
```

---

## Part 8: Implementation Roadmap

### Phase 1: Data Collection (1-2 months)

- [ ] GPS tracking for all visits
- [ ] Record actual visit start/end times
- [ ] Log delays and reasons
- [ ] Track visit outcomes
- [ ] Collect client feedback

### Phase 2: Pattern Analysis (1 month)

- [ ] Identify optimal routes per agent
- [ ] Determine best time windows per client
- [ ] Classify clients (recency, frequency, monetary)
- [ ] Segment by geography
- [ ] Baseline current performance

### Phase 3: Pilot (2-3 months)

- [ ] Test on one region/team
- [ ] A/B test: optimized vs standard routes
- [ ] Gather agent feedback
- [ ] Tune algorithms
- [ ] Document learnings

### Phase 4: Scale (ongoing)

- [ ] Gradual rollout by region
- [ ] Train users
- [ ] Monitor KPIs
- [ ] Continuous improvement
- [ ] Add ML components

---

## Appendix A: Sample Daily Schedule (Uzbekistan)

```
07:00 - 07:30  Agent starts, reviews route in app
07:30 - 08:30  First 2 visits (early openers)
08:30 - 09:00  Travel (avoid traffic buildup)
09:00 - 12:30  Main visits (6-8 clients)
12:30 - 13:30  Lunch break
13:30 - 17:00  Afternoon visits (4-6 clients)
17:00 - 17:30  Travel back, avoid evening traffic
17:30 - 18:00  Reporting, sync, plan tomorrow
```

## Appendix B: Cost Estimation Formula

```python
def estimate_route_cost(route, vehicle, fuel_price_per_liter):
    """Estimate total cost of a delivery route."""

    # Distance cost
    distance_km = route.total_distance_km
    fuel_consumption_per_100km = vehicle.fuel_consumption
    fuel_cost = (distance_km / 100) * fuel_consumption_per_100km * fuel_price_per_liter

    # Time cost
    total_hours = route.total_duration_minutes / 60
    driver_hourly_rate = vehicle.driver.hourly_rate
    labor_cost = total_hours * driver_hourly_rate

    # Vehicle depreciation
    depreciation_per_km = vehicle.depreciation_rate
    depreciation_cost = distance_km * depreciation_per_km

    # Total
    total_cost = fuel_cost + labor_cost + depreciation_cost
    cost_per_delivery = total_cost / len(route.orders)

    return {
        "total_cost": total_cost,
        "fuel_cost": fuel_cost,
        "labor_cost": labor_cost,
        "depreciation_cost": depreciation_cost,
        "cost_per_delivery": cost_per_delivery,
        "cost_per_km": total_cost / distance_km,
    }
```
