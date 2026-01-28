# Анализ технологий маршрутизации: OR-Tools + OSRM

## Executive Summary

Изучены две ключевые технологии для оптимизации маршрутов:
- **Google OR-Tools** — библиотека решения задач оптимизации (VRP, TSP)
- **OSRM** — движок маршрутизации на основе OpenStreetMap

**Вывод**: Оптимальная архитектура — **гибридный подход**:
- OSRM для реальных расстояний и времени в пути
- OR-Tools для решения задач оптимизации
- VROOM как быстрый альтернативный солвер

---

## 1. Google OR-Tools — Детальный анализ

### 1.1 Поддерживаемые типы задач

| Тип задачи | Описание | Применение в нашем проекте |
|------------|----------|----------------------------|
| **TSP** | Задача коммивояжёра | Оптимизация порядка визитов для 1 агента |
| **VRP** | Маршрутизация транспорта | Распределение заказов по машинам |
| **CVRP** | VRP с ограничениями вместимости | Учёт грузоподъёмности авто |
| **VRPTW** | VRP с временными окнами | Учёт времени работы клиентов |
| **PDVRP** | Pickup & Delivery | Сбор и доставка товаров |
| **MDVRP** | Multi-depot VRP | Несколько складов |

### 1.2 Архитектура OR-Tools Routing

```
┌─────────────────────────────────────────────────────────────────┐
│                    OR-TOOLS ROUTING FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. СОЗДАНИЕ МОДЕЛИ                                            │
│     ┌─────────────────────────────────────────────────────┐    │
│     │  RoutingIndexManager(                               │    │
│     │      num_locations,    # Количество точек           │    │
│     │      num_vehicles,     # Количество транспорта      │    │
│     │      depot             # Индекс склада/депо         │    │
│     │  )                                                  │    │
│     └─────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  2. РЕГИСТРАЦИЯ CALLBACKS                                      │
│     ┌─────────────────────────────────────────────────────┐    │
│     │  • distance_callback   → Расстояния между точками   │    │
│     │  • demand_callback     → Спрос в каждой точке       │    │
│     │  • time_callback       → Время перемещения          │    │
│     │  • service_callback    → Время обслуживания         │    │
│     └─────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  3. ДОБАВЛЕНИЕ ИЗМЕРЕНИЙ (DIMENSIONS)                          │
│     ┌─────────────────────────────────────────────────────┐    │
│     │  routing.AddDimension("Distance")    # Расстояние   │    │
│     │  routing.AddDimensionWithVehicleCapacity("Capacity")│    │
│     │  routing.AddDimension("Time")        # Время        │    │
│     └─────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  4. НАСТРОЙКА СТРАТЕГИИ ПОИСКА                                 │
│     ┌─────────────────────────────────────────────────────┐    │
│     │  First Solution Strategies:                         │    │
│     │  • PATH_CHEAPEST_ARC      (рекомендуется)          │    │
│     │  • SAVINGS                                          │    │
│     │  • CHRISTOFIDES                                     │    │
│     │  • PARALLEL_CHEAPEST_INSERTION                      │    │
│     │                                                     │    │
│     │  Local Search Metaheuristics:                       │    │
│     │  • GUIDED_LOCAL_SEARCH    (рекомендуется)          │    │
│     │  • SIMULATED_ANNEALING                              │    │
│     │  • TABU_SEARCH                                      │    │
│     └─────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  5. РЕШЕНИЕ И ИЗВЛЕЧЕНИЕ РЕЗУЛЬТАТОВ                           │
│     ┌─────────────────────────────────────────────────────┐    │
│     │  solution = routing.SolveWithParameters(params)     │    │
│     │  for vehicle_id in range(num_vehicles):             │    │
│     │      route = extract_route(solution, vehicle_id)    │    │
│     └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Пример кода: CVRP с временными окнами

```python
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def solve_vrptw_with_capacity(
    distance_matrix: list[list[int]],
    time_matrix: list[list[int]],
    demands: list[int],
    time_windows: list[tuple[int, int]],
    vehicle_capacities: list[int],
    depot: int = 0,
) -> dict:
    """
    Решение VRPTW с ограничениями вместимости.

    Args:
        distance_matrix: Матрица расстояний (метры)
        time_matrix: Матрица времени (секунды)
        demands: Спрос в каждой точке (кг)
        time_windows: Временные окна [(start, end), ...]
        vehicle_capacities: Вместимость каждого авто (кг)
        depot: Индекс депо

    Returns:
        Словарь с маршрутами для каждого транспорта
    """
    num_locations = len(distance_matrix)
    num_vehicles = len(vehicle_capacities)

    # 1. Создание менеджера индексов
    manager = pywrapcp.RoutingIndexManager(
        num_locations,
        num_vehicles,
        depot
    )
    routing = pywrapcp.RoutingModel(manager)

    # 2. Callback для расстояний
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # 3. Добавление измерения расстояния
    routing.AddDimension(
        transit_callback_index,
        0,  # no slack
        3000000,  # max distance per vehicle (3000 km)
        True,
        "Distance"
    )

    # 4. Callback для вместимости
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)

    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # no slack
        vehicle_capacities,
        True,
        "Capacity"
    )

    # 5. Callback для времени с временными окнами
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel_time = time_matrix[from_node][to_node]
        service_time = 300  # 5 минут обслуживания
        return travel_time + service_time

    time_callback_index = routing.RegisterTransitCallback(time_callback)

    routing.AddDimension(
        time_callback_index,
        1800,  # 30 мин slack (ожидание)
        86400,  # 24 часа максимум
        False,
        "Time"
    )

    time_dimension = routing.GetDimensionOrDie("Time")

    # Установка временных окон
    for location_idx, (start, end) in enumerate(time_windows):
        if location_idx == depot:
            continue
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(start, end)

    # 6. Параметры поиска
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 30

    # 7. Решение
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return {"status": "no_solution", "routes": []}

    # 8. Извлечение маршрутов
    routes = []
    for vehicle_id in range(num_vehicles):
        route = []
        index = routing.Start(vehicle_id)
        route_distance = 0
        route_load = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route_load += demands[node]
            time_var = time_dimension.CumulVar(index)

            route.append({
                "location": node,
                "arrival_time": solution.Min(time_var),
                "load": route_load,
            })

            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += distance_matrix[
                manager.IndexToNode(previous_index)
            ][manager.IndexToNode(index)]

        if len(route) > 1:  # Есть посещения кроме депо
            routes.append({
                "vehicle_id": vehicle_id,
                "stops": route,
                "total_distance": route_distance,
                "total_load": route_load,
            })

    return {
        "status": "success",
        "routes": routes,
        "objective": solution.ObjectiveValue(),
    }
```

---

## 2. OSRM — Детальный анализ

### 2.1 Архитектура и сервисы OSRM

```
┌─────────────────────────────────────────────────────────────────┐
│                      OSRM ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 OSRM HTTP API (Port 5000)                │   │
│  └─────────────────────────────────────────────────────────┘   │
│       │         │         │         │         │         │      │
│       ▼         ▼         ▼         ▼         ▼         ▼      │
│  ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐ │
│  │Nearest ││ Route  ││ Table  ││ Match  ││  Trip  ││  Tile  │ │
│  └────────┘└────────┘└────────┘└────────┘└────────┘└────────┘ │
│                                                                 │
│  NEAREST - Ближайшая точка дорожной сети                       │
│  GET /nearest/v1/{profile}/{coordinates}                        │
│  → Снаппинг GPS координат к дороге                             │
│                                                                 │
│  ROUTE - Оптимальный маршрут между точками                     │
│  GET /route/v1/{profile}/{coordinates}                          │
│  → Геометрия маршрута, расстояние, время                       │
│                                                                 │
│  TABLE - Матрица расстояний/времени ⭐ КЛЮЧЕВОЙ ДЛЯ VRP        │
│  GET /table/v1/{profile}/{coordinates}                          │
│  → NxN матрица для всех пар точек                              │
│                                                                 │
│  MATCH - Привязка GPS трека к дороге                           │
│  GET /match/v1/{profile}/{coordinates}                          │
│  → Коррекция шумных GPS данных                                 │
│                                                                 │
│  TRIP - Решение TSP (круговой маршрут)                         │
│  GET /trip/v1/{profile}/{coordinates}                           │
│  → Быстрый greedy TSP solver                                   │
│                                                                 │
│  TILE - Векторные тайлы для визуализации                       │
│  GET /tile/v1/{profile}/{z}/{x}/{y}.mvt                        │
│  → Mapbox Vector Tiles                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Подготовка данных для Узбекистана

```bash
#!/bin/bash
# Скрипт подготовки OSRM для Узбекистана

# 1. Скачивание карты
wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf

# 2. Извлечение графа дорог (профиль: автомобиль)
docker run -t -v $(pwd):/data osrm/osrm-backend \
    osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf

# 3. Разбиение на ячейки (для MLD алгоритма)
docker run -t -v $(pwd):/data osrm/osrm-backend \
    osrm-partition /data/uzbekistan-latest.osrm

# 4. Кастомизация весов
docker run -t -v $(pwd):/data osrm/osrm-backend \
    osrm-customize /data/uzbekistan-latest.osrm

# 5. Запуск сервера
docker run -d -p 5000:5000 -v $(pwd):/data osrm/osrm-backend \
    osrm-routed --algorithm mld /data/uzbekistan-latest.osrm
```

### 2.3 API вызовы для нашего проекта

```python
"""
OSRM API клиент с расширенными возможностями.
"""
import httpx
from typing import Optional
from dataclasses import dataclass


@dataclass
class OSRMConfig:
    """Конфигурация OSRM."""
    base_url: str = "http://localhost:5000"
    profile: str = "car"  # car, bike, foot
    timeout: float = 30.0


class EnhancedOSRMClient:
    """Расширенный клиент OSRM."""

    def __init__(self, config: Optional[OSRMConfig] = None):
        self.config = config or OSRMConfig()
        self.base_url = f"{self.config.base_url}/{self.config.profile}"

    async def get_distance_matrix(
        self,
        coordinates: list[tuple[float, float]],
        sources: Optional[list[int]] = None,
        destinations: Optional[list[int]] = None,
    ) -> dict:
        """
        Получение матрицы расстояний/времени.

        OSRM Table API — ключевой endpoint для VRP!
        Возвращает матрицу времени в секундах и расстояний в метрах.

        Args:
            coordinates: Список (longitude, latitude)
            sources: Индексы точек-источников (опционально)
            destinations: Индексы точек-назначений (опционально)

        Returns:
            {
                "durations": [[0, 120, 300], [120, 0, 200], ...],
                "distances": [[0, 1500, 3000], [1500, 0, 2500], ...],
            }
        """
        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self.base_url}/table/v1/{coords_str}"

        params = {
            "annotations": "duration,distance",
        }

        if sources:
            params["sources"] = ";".join(map(str, sources))
        if destinations:
            params["destinations"] = ";".join(map(str, destinations))

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM error: {data.get('message')}")

        return {
            "durations": data["durations"],  # секунды
            "distances": data["distances"],   # метры
        }

    async def get_route(
        self,
        coordinates: list[tuple[float, float]],
        overview: str = "full",  # full, simplified, false
        steps: bool = True,
        geometries: str = "geojson",  # geojson, polyline, polyline6
    ) -> dict:
        """
        Получение маршрута между точками.

        Args:
            coordinates: Список точек маршрута
            overview: Уровень детализации геометрии
            steps: Включать пошаговые инструкции
            geometries: Формат геометрии

        Returns:
            {
                "distance": 15000,  # метры
                "duration": 1200,   # секунды
                "geometry": {...},  # GeoJSON
                "legs": [...]       # Сегменты маршрута
            }
        """
        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self.base_url}/route/v1/{coords_str}"

        params = {
            "overview": overview,
            "steps": str(steps).lower(),
            "geometries": geometries,
        }

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM error: {data.get('message')}")

        route = data["routes"][0]
        return {
            "distance": route["distance"],
            "duration": route["duration"],
            "geometry": route["geometry"],
            "legs": route["legs"],
        }

    async def solve_tsp(
        self,
        coordinates: list[tuple[float, float]],
        source: int = 0,
        roundtrip: bool = True,
    ) -> dict:
        """
        Решение TSP через OSRM Trip API.

        Использует greedy-эвристику — быстро, но не оптимально.
        Для лучшего качества используйте OR-Tools.

        Args:
            coordinates: Точки для посещения
            source: Индекс стартовой точки
            roundtrip: Возвращаться в начало

        Returns:
            {
                "waypoints": [...],  # Упорядоченные точки
                "trips": [...]       # Маршруты
            }
        """
        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self.base_url}/trip/v1/{coords_str}"

        params = {
            "source": "first" if source == 0 else "any",
            "roundtrip": str(roundtrip).lower(),
            "geometries": "geojson",
        }

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM error: {data.get('message')}")

        return {
            "waypoints": data["waypoints"],
            "trips": data["trips"],
        }
```

---

## 3. Интеграция OR-Tools + OSRM

### 3.1 Рекомендуемая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                  HYBRID ROUTING ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Route Optimizer                       │   │
│  │  (Оркестратор оптимизации)                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│              ┌───────────────┴───────────────┐                 │
│              ▼                               ▼                 │
│  ┌─────────────────────┐       ┌─────────────────────┐        │
│  │  Distance Provider  │       │   Problem Solver    │        │
│  │                     │       │                     │        │
│  │  ┌───────────────┐  │       │  ┌───────────────┐  │        │
│  │  │     OSRM      │  │       │  │   OR-Tools    │  │        │
│  │  │  (Table API)  │  │       │  │ (CVRP/VRPTW)  │  │        │
│  │  └───────────────┘  │       │  └───────────────┘  │        │
│  │         │           │       │         │           │        │
│  │  ┌───────────────┐  │       │  ┌───────────────┐  │        │
│  │  │   Fallback:   │  │       │  │   Fallback:   │  │        │
│  │  │   Haversine   │  │       │  │     VROOM     │  │        │
│  │  └───────────────┘  │       │  └───────────────┘  │        │
│  └─────────────────────┘       └─────────────────────┘        │
│                                                                 │
│  WORKFLOW:                                                      │
│  1. Получить координаты точек                                  │
│  2. Запросить матрицу расстояний из OSRM                       │
│  3. Построить модель OR-Tools с реальными расстояниями         │
│  4. Решить VRP/TSP                                             │
│  5. Обогатить результат геометрией маршрутов (OSRM Route)      │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Полный пример интеграции

```python
"""
Интегрированный оптимизатор: OSRM + OR-Tools.
"""
import asyncio
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


@dataclass
class DeliveryPoint:
    """Точка доставки."""
    id: UUID
    name: str
    latitude: float
    longitude: float
    demand_kg: float
    time_window_start: int  # секунды от полуночи
    time_window_end: int
    service_time: int = 300  # 5 минут


@dataclass
class Vehicle:
    """Транспортное средство."""
    id: UUID
    name: str
    capacity_kg: float
    depot_lat: float
    depot_lon: float
    work_start: int  # секунды от полуночи
    work_end: int


class IntegratedRouteOptimizer:
    """
    Интегрированный оптимизатор маршрутов.

    Использует:
    - OSRM для реальных расстояний по дорогам
    - OR-Tools для решения VRP с ограничениями
    """

    def __init__(self, osrm_url: str = "http://localhost:5000"):
        self.osrm_url = osrm_url

    async def optimize(
        self,
        deliveries: list[DeliveryPoint],
        vehicles: list[Vehicle],
        time_limit_seconds: int = 30,
    ) -> dict:
        """
        Оптимизация маршрутов доставки.

        Args:
            deliveries: Список точек доставки
            vehicles: Список транспорта
            time_limit_seconds: Лимит времени на оптимизацию

        Returns:
            Оптимизированные маршруты для каждого транспорта
        """
        if not deliveries or not vehicles:
            return {"routes": [], "unassigned": []}

        # 1. Собираем все координаты (депо + точки доставки)
        coordinates = []

        # Депо (предполагаем одно для всех)
        depot = vehicles[0]
        coordinates.append((depot.depot_lon, depot.depot_lat))

        # Точки доставки
        for d in deliveries:
            coordinates.append((d.longitude, d.latitude))

        # 2. Получаем матрицу расстояний из OSRM
        try:
            matrices = await self._get_osrm_matrix(coordinates)
            distance_matrix = matrices["distances"]
            duration_matrix = matrices["durations"]
        except Exception as e:
            # Fallback на Haversine
            print(f"OSRM unavailable, using Haversine: {e}")
            distance_matrix = self._compute_haversine_matrix(coordinates)
            duration_matrix = [[int(d / 8.33) for d in row] for row in distance_matrix]

        # 3. Подготавливаем данные для OR-Tools
        demands = [0] + [int(d.demand_kg) for d in deliveries]  # 0 для депо
        time_windows = [(depot.work_start, depot.work_end)]  # депо
        time_windows += [(d.time_window_start, d.time_window_end) for d in deliveries]

        vehicle_capacities = [int(v.capacity_kg) for v in vehicles]

        # 4. Решаем OR-Tools
        result = self._solve_with_ortools(
            distance_matrix=distance_matrix,
            duration_matrix=duration_matrix,
            demands=demands,
            time_windows=time_windows,
            vehicle_capacities=vehicle_capacities,
            time_limit=time_limit_seconds,
        )

        # 5. Обогащаем результат информацией о точках
        routes = []
        assigned_indices = set()

        for route_data in result.get("routes", []):
            vehicle_id = route_data["vehicle_id"]
            vehicle = vehicles[vehicle_id]

            stops = []
            for stop in route_data["stops"]:
                location_idx = stop["location"]
                if location_idx == 0:  # Депо
                    continue

                delivery_idx = location_idx - 1
                delivery = deliveries[delivery_idx]
                assigned_indices.add(delivery_idx)

                stops.append({
                    "delivery_id": str(delivery.id),
                    "name": delivery.name,
                    "latitude": delivery.latitude,
                    "longitude": delivery.longitude,
                    "arrival_time": stop["arrival_time"],
                    "load_after": stop["load"],
                })

            if stops:
                routes.append({
                    "vehicle_id": str(vehicle.id),
                    "vehicle_name": vehicle.name,
                    "stops": stops,
                    "total_distance_m": route_data["total_distance"],
                    "total_load_kg": route_data["total_load"],
                })

        # 6. Определяем неназначенные заказы
        unassigned = [
            str(deliveries[i].id)
            for i in range(len(deliveries))
            if i not in assigned_indices
        ]

        return {
            "routes": routes,
            "unassigned": unassigned,
            "total_distance_m": sum(r["total_distance_m"] for r in routes),
            "vehicles_used": len(routes),
        }

    async def _get_osrm_matrix(
        self,
        coordinates: list[tuple[float, float]],
    ) -> dict:
        """Получение матрицы из OSRM."""
        import httpx

        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self.osrm_url}/table/v1/car/{coords_str}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params={
                "annotations": "duration,distance"
            })
            response.raise_for_status()
            data = response.json()

        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM error: {data.get('message')}")

        return {
            "durations": data["durations"],
            "distances": data["distances"],
        }

    def _compute_haversine_matrix(
        self,
        coordinates: list[tuple[float, float]],
    ) -> list[list[int]]:
        """Fallback: матрица на основе формулы Haversine."""
        import math

        def haversine(lon1, lat1, lon2, lat2):
            R = 6371000  # Радиус Земли в метрах
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
            return int(2 * R * math.asin(math.sqrt(a)))

        n = len(coordinates)
        matrix = [[0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = haversine(
                        coordinates[i][0], coordinates[i][1],
                        coordinates[j][0], coordinates[j][1]
                    )

        return matrix

    def _solve_with_ortools(
        self,
        distance_matrix: list[list[int]],
        duration_matrix: list[list[int]],
        demands: list[int],
        time_windows: list[tuple[int, int]],
        vehicle_capacities: list[int],
        time_limit: int,
    ) -> dict:
        """Решение VRP с помощью OR-Tools."""

        num_locations = len(distance_matrix)
        num_vehicles = len(vehicle_capacities)
        depot = 0

        # Менеджер индексов
        manager = pywrapcp.RoutingIndexManager(
            num_locations, num_vehicles, depot
        )
        routing = pywrapcp.RoutingModel(manager)

        # Distance callback
        def distance_callback(from_idx, to_idx):
            from_node = manager.IndexToNode(from_idx)
            to_node = manager.IndexToNode(to_idx)
            return distance_matrix[from_node][to_node]

        transit_idx = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        # Capacity dimension
        def demand_callback(from_idx):
            from_node = manager.IndexToNode(from_idx)
            return demands[from_node]

        demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_idx, 0, vehicle_capacities, True, "Capacity"
        )

        # Time dimension
        def time_callback(from_idx, to_idx):
            from_node = manager.IndexToNode(from_idx)
            to_node = manager.IndexToNode(to_idx)
            return duration_matrix[from_node][to_node] + 300  # +5 мин обслуживание

        time_idx = routing.RegisterTransitCallback(time_callback)
        routing.AddDimension(time_idx, 1800, 86400, False, "Time")

        time_dim = routing.GetDimensionOrDie("Time")
        for i, (start, end) in enumerate(time_windows):
            if i == depot:
                continue
            idx = manager.NodeToIndex(i)
            time_dim.CumulVar(idx).SetRange(start, end)

        # Search parameters
        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_params.time_limit.seconds = time_limit

        # Solve
        solution = routing.SolveWithParameters(search_params)

        if not solution:
            return {"routes": []}

        # Extract routes
        routes = []
        for v in range(num_vehicles):
            index = routing.Start(v)
            stops = []
            route_dist = 0
            route_load = 0

            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                route_load += demands[node]
                time_var = time_dim.CumulVar(index)

                stops.append({
                    "location": node,
                    "arrival_time": solution.Min(time_var),
                    "load": route_load,
                })

                prev = index
                index = solution.Value(routing.NextVar(index))
                from_n = manager.IndexToNode(prev)
                to_n = manager.IndexToNode(index)
                route_dist += distance_matrix[from_n][to_n]

            if len(stops) > 1:
                routes.append({
                    "vehicle_id": v,
                    "stops": stops,
                    "total_distance": route_dist,
                    "total_load": route_load,
                })

        return {"routes": routes}
```

---

## 4. Рекомендации по улучшению проекта

### 4.1 Немедленные действия

| Приоритет | Действие | Ожидаемый результат |
|-----------|----------|---------------------|
| 🔴 Высокий | Заменить евклидовы расстояния на OSRM | +20-30% точности маршрутов |
| 🔴 Высокий | Интегрировать OR-Tools для сложных задач | Лучшее качество решений |
| 🟡 Средний | Кэширование матриц OSRM в Redis | -50% нагрузки на OSRM |
| 🟡 Средний | Предварительный расчёт матриц ночью | Быстрее ответ днём |

### 4.2 Сравнение подходов

```
┌────────────────────────────────────────────────────────────────────┐
│              ТЕКУЩИЙ vs РЕКОМЕНДУЕМЫЙ ПОДХОД                       │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ТЕКУЩИЙ ПОДХОД:                                                   │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐           │
│  │  Клиенты   │ ──── │   VROOM    │ ──── │  Маршруты  │           │
│  │ (lat/lon)  │      │(евклидово) │      │(неточные)  │           │
│  └────────────┘      └────────────┘      └────────────┘           │
│                                                                    │
│  Проблемы:                                                         │
│  • Расстояния "по прямой", не по дорогам                          │
│  • Не учитывает одностороннее движение                            │
│  • Не учитывает типы дорог и ограничения                          │
│                                                                    │
│  ════════════════════════════════════════════════════════════════ │
│                                                                    │
│  РЕКОМЕНДУЕМЫЙ ПОДХОД:                                            │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐           │
│  │  Клиенты   │ ──── │    OSRM    │ ──── │  Матрица   │           │
│  │ (lat/lon)  │      │  (Table)   │      │ расстояний │           │
│  └────────────┘      └────────────┘      └─────┬──────┘           │
│                                                 │                  │
│                                                 ▼                  │
│                      ┌────────────┐      ┌────────────┐           │
│                      │  OR-Tools  │ ──── │  Маршруты  │           │
│                      │ (VRP/TSP)  │      │ (точные)   │           │
│                      └────────────┘      └─────┬──────┘           │
│                                                 │                  │
│                                                 ▼                  │
│                      ┌────────────┐      ┌────────────┐           │
│                      │    OSRM    │ ──── │ Геометрия  │           │
│                      │  (Route)   │      │   + ETA    │           │
│                      └────────────┘      └────────────┘           │
│                                                                    │
│  Преимущества:                                                     │
│  • Реальные расстояния по дорогам (+20-30% точности)              │
│  • Учёт всех дорожных ограничений                                 │
│  • Точное время прибытия (ETA)                                    │
│  • Геометрия маршрута для карты                                   │
└────────────────────────────────────────────────────────────────────┘
```

---

## 5. Заключение

### Ключевые выводы:

1. **OSRM** — идеальный источник реальных расстояний
   - Table API для матрицы NxN за один запрос
   - Route API для геометрии маршрута
   - Trip API для быстрого TSP (но низкое качество)

2. **OR-Tools** — лучший солвер для сложных VRP
   - CVRP с вместимостью
   - VRPTW с временными окнами
   - Гибкие стратегии поиска

3. **Гибридный подход** — оптимальное решение
   - OSRM для расстояний → OR-Tools для оптимизации
   - VROOM как быстрый fallback
   - Greedy для гарантированного результата

### План внедрения:

| Неделя | Задача |
|--------|--------|
| 1 | Интеграция OSRM Table API для матриц |
| 2 | Замена евклидовых расстояний на OSRM |
| 3 | A/B тестирование OR-Tools vs VROOM |
| 4 | Кэширование матриц в Redis |

---

*Документ подготовлен на основе официальной документации*
*Google OR-Tools: https://developers.google.com/optimization/routing*
*OSRM: https://github.com/Project-OSRM/osrm-backend*
