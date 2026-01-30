"""
Field Team Routing Service.

Сервис для маршрутизации полевых команд с планированием на несколько дней.
Использует солверы VROOM/OR-Tools/Genetic для оптимизации маршрутов.
"""

import logging
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from app.schemas.field_routing import (
    DailySummary,
    FieldRoutingRequest,
    FieldRoutingResponse,
    RoutingMode,
    ScheduledVisit,
    UnassignedVisit,
)
from app.services.routing.osrm_client import OSRMClient, osrm_client
from app.services.solvers.solver_interface import (
    Job,
    Location,
    RoutingProblem,
    SolverFactory,
    SolverType,
    TimeWindow,
    TransportMode,
    VehicleConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class DayPlan:
    """План на один день."""

    day_number: int
    visits: list[ScheduledVisit]
    total_distance_km: float
    total_duration_minutes: int
    start_time: time
    end_time: time


class FieldRoutingService:
    """
    Сервис маршрутизации полевых команд.

    Планирует оптимальные маршруты для заданных точек визита
    на указанное количество рабочих дней с учётом:
    - Приоритетов визитов
    - Временных окон доступности клиентов
    - Рабочих часов агента
    - Времени обслуживания и приёмки
    """

    def __init__(self, osrm: Optional[OSRMClient] = None):
        self.osrm = osrm or osrm_client

    async def plan_route(
        self,
        request: FieldRoutingRequest,
        plan_start_date: Optional[date] = None,
    ) -> FieldRoutingResponse:
        """
        Планирует маршрут для полевой команды.

        Args:
            request: Параметры планирования
            plan_start_date: Дата начала планирования (по умолчанию завтра)

        Returns:
            FieldRoutingResponse с оптимизированным маршрутом
        """
        start_time = time_module.time()

        if plan_start_date is None:
            plan_start_date = date.today() + timedelta(days=1)

        # Преобразуем точки визита в формат солвера
        problem = self._build_routing_problem(request, plan_start_date)

        # Выбираем и запускаем солвер
        solver_type = self._select_solver(len(request.visits))
        solver_used = solver_type.value

        try:
            solution = await SolverFactory.solve_with_fallback(problem, preferred=solver_type)
        except Exception as e:
            logger.error(f"Solver failed: {e}")
            # Fallback к простому распределению по приоритетам
            solution = self._greedy_fallback(request, plan_start_date)
            solver_used = "greedy_fallback"

        # Формируем ответ
        computation_time_ms = int((time_module.time() - start_time) * 1000)

        return self._build_response(
            solution=solution,
            request=request,
            plan_start_date=plan_start_date,
            solver_used=solver_used,
            computation_time_ms=computation_time_ms,
        )

    def _build_routing_problem(
        self,
        request: FieldRoutingRequest,
        plan_start_date: date,
    ) -> RoutingProblem:
        """Строит задачу маршрутизации для солвера."""

        # Создаём виртуальные транспортные средства (по одному на день)
        vehicles = []
        for day in range(request.working_days):
            day_date = plan_start_date + timedelta(days=day)

            # Начало и конец рабочего дня
            work_start = datetime.combine(day_date, request.working_hours.start)
            work_end = datetime.combine(day_date, request.working_hours.end)

            # Стартовая локация
            if request.start_location:
                start_loc = Location(
                    latitude=request.start_location.latitude,
                    longitude=request.start_location.longitude,
                )
            else:
                # Используем первую точку как стартовую
                start_loc = Location(
                    latitude=request.visits[0].location.latitude,
                    longitude=request.visits[0].location.longitude,
                )

            vehicle = VehicleConfig(
                id=f"day_{day + 1}",
                capacity_kg=float("inf"),  # Неограниченная вместимость
                capacity_volume=float("inf"),
                start_location=start_loc,
                end_location=start_loc,  # Возврат в начальную точку
                time_window=TimeWindow(start=work_start, end=work_end),
                max_stops=request.max_visits_per_day,
            )
            vehicles.append(vehicle)

        # Создаём задания (jobs) для каждой точки визита
        jobs = []
        for visit in request.visits:
            # Общее время обслуживания = service_time + manager_acceptance_time
            total_service_time = (visit.service_time or 15) + (visit.manager_acceptance_time or 0)

            # Временное окно доступности (для всех дней)
            # Солвер сам выберет подходящий день
            job = Job(
                id=visit.id,
                location=Location(
                    latitude=visit.location.latitude,
                    longitude=visit.location.longitude,
                ),
                service_duration_minutes=total_service_time,
                priority=visit.priority,
                # Временные окна будут проверяться при распределении по дням
                time_window=TimeWindow(
                    start=datetime.combine(plan_start_date, visit.available_hours.start),
                    end=datetime.combine(plan_start_date, visit.available_hours.end),
                ),
            )
            jobs.append(job)

        # Определяем режим транспорта
        transport_mode = TransportMode.CAR if request.routing_mode == RoutingMode.CAR else TransportMode.WALKING

        return RoutingProblem(
            jobs=jobs,
            vehicles=vehicles,
            transport_mode=transport_mode,
        )

    def _select_solver(self, num_visits: int) -> SolverType:
        """Выбирает оптимальный солвер на основе количества точек."""
        if num_visits <= 100:
            return SolverType.VROOM
        elif num_visits <= 300:
            return SolverType.ORTOOLS
        else:
            return SolverType.GENETIC

    def _greedy_fallback(
        self,
        request: FieldRoutingRequest,
        plan_start_date: date,
    ) -> dict:
        """
        Простой greedy алгоритм как fallback.

        Распределяет визиты по дням согласно приоритетам,
        без оптимизации маршрута внутри дня.
        """
        # Сортируем по приоритету (1 = наивысший)
        sorted_visits = sorted(request.visits, key=lambda v: v.priority)

        routes = []
        unassigned = []

        visits_per_day = request.max_visits_per_day
        current_day = 1
        day_visits = []

        for visit in sorted_visits:
            if current_day > request.working_days:
                # Больше нет дней, визит не распределён
                unassigned.append({"id": visit.id, "reason": "no_available_days"})
                continue

            day_visits.append(visit)

            if len(day_visits) >= visits_per_day:
                routes.append({"day": current_day, "visits": day_visits})
                day_visits = []
                current_day += 1

        # Добавляем оставшиеся визиты последнего дня
        if day_visits and current_day <= request.working_days:
            routes.append({"day": current_day, "visits": day_visits})

        return {
            "routes": routes,
            "unassigned": unassigned,
            "is_fallback": True,
        }

    def _build_response(
        self,
        solution: dict,
        request: FieldRoutingRequest,
        plan_start_date: date,
        solver_used: str,
        computation_time_ms: int,
    ) -> FieldRoutingResponse:
        """Строит ответ API из решения солвера."""

        scheduled_visits: list[ScheduledVisit] = []
        daily_summaries: list[DailySummary] = []
        unassigned_visits: list[UnassignedVisit] = []

        total_distance = 0.0
        total_duration = 0

        # Обрабатываем решение солвера
        if solution.get("is_fallback"):
            # Fallback решение - простое распределение
            scheduled_visits, daily_summaries = self._process_fallback_solution(
                solution, request, plan_start_date
            )
        else:
            # Решение от солвера
            scheduled_visits, daily_summaries = self._process_solver_solution(
                solution, request, plan_start_date
            )

        # Обрабатываем нераспределённые визиты
        if solution.get("unassigned"):
            for item in solution["unassigned"]:
                unassigned_visits.append(
                    UnassignedVisit(
                        visit_id=item.get("id", str(item)),
                        reason=item.get("reason", "could_not_fit_in_schedule"),
                    )
                )

        # Подсчитываем общую статистику
        for summary in daily_summaries:
            total_distance += summary.total_distance_km
            total_duration += summary.total_duration_minutes

        return FieldRoutingResponse(
            total_visits=len(scheduled_visits),
            total_distance=round(total_distance, 2),
            total_duration=total_duration,
            days_used=len(daily_summaries),
            daily_summary=daily_summaries,
            scheduled_visits=scheduled_visits,
            unassigned_visits=unassigned_visits,
            solver_used=solver_used,
            computation_time_ms=computation_time_ms,
        )

    def _process_fallback_solution(
        self,
        solution: dict,
        request: FieldRoutingRequest,
        plan_start_date: date,
    ) -> tuple[list[ScheduledVisit], list[DailySummary]]:
        """Обрабатывает fallback решение."""

        scheduled_visits = []
        daily_summaries = []

        # Создаём словарь точек для быстрого доступа
        visits_map = {v.id: v for v in request.visits}

        for route_data in solution.get("routes", []):
            day_number = route_data["day"]
            day_visits = route_data["visits"]
            day_date = plan_start_date + timedelta(days=day_number - 1)

            # Начинаем с начала рабочего дня
            current_time = datetime.combine(day_date, request.working_hours.start)
            day_distance = 0.0
            sequence = 1

            for i, visit in enumerate(day_visits):
                if isinstance(visit, dict):
                    visit_id = visit.get("id")
                    visit_data = visits_map.get(visit_id)
                else:
                    visit_data = visit
                    visit_id = visit.id

                if not visit_data:
                    continue

                service_time = (visit_data.service_time or 15) + (visit_data.manager_acceptance_time or 0)
                visit_end = current_time + timedelta(minutes=service_time)

                # Оценка расстояния до следующей точки (упрощённо)
                distance_to_next = None
                travel_time_to_next = None

                if i < len(day_visits) - 1:
                    next_visit = day_visits[i + 1]
                    if isinstance(next_visit, dict):
                        next_visit_data = visits_map.get(next_visit.get("id"))
                    else:
                        next_visit_data = next_visit

                    if next_visit_data:
                        # Примерная оценка расстояния (Haversine)
                        distance_to_next = self._haversine_distance(
                            visit_data.location.latitude,
                            visit_data.location.longitude,
                            next_visit_data.location.latitude,
                            next_visit_data.location.longitude,
                        )
                        # Примерное время в пути (40 км/ч для авто, 5 км/ч для пешком)
                        speed = 40 if request.routing_mode == RoutingMode.CAR else 5
                        travel_time_to_next = int((distance_to_next / speed) * 60)
                        day_distance += distance_to_next

                scheduled_visits.append(
                    ScheduledVisit(
                        visit_id=visit_id,
                        day_number=day_number,
                        sequence_number=sequence,
                        scheduled_start=current_time,
                        scheduled_end=visit_end,
                        distance_to_next=round(distance_to_next, 2) if distance_to_next else None,
                        travel_time_to_next=travel_time_to_next,
                    )
                )

                # Переходим к следующему визиту
                current_time = visit_end + timedelta(minutes=travel_time_to_next or 10)
                sequence += 1

            # Статистика дня
            if day_visits:
                end_time = scheduled_visits[-1].scheduled_end if scheduled_visits else current_time
                day_start = datetime.combine(day_date, request.working_hours.start)
                duration = int((end_time - day_start).total_seconds() / 60)

                daily_summaries.append(
                    DailySummary(
                        day_number=day_number,
                        visits_count=len(day_visits),
                        total_distance_km=round(day_distance, 2),
                        total_duration_minutes=duration,
                        start_time=request.working_hours.start,
                        end_time=end_time.time(),
                    )
                )

        return scheduled_visits, daily_summaries

    def _process_solver_solution(
        self,
        solution: dict,
        request: FieldRoutingRequest,
        plan_start_date: date,
    ) -> tuple[list[ScheduledVisit], list[DailySummary]]:
        """Обрабатывает решение от солвера."""

        # Если солвер вернул SolutionResult
        if hasattr(solution, "routes"):
            routes = solution.routes
        else:
            routes = solution.get("routes", [])

        scheduled_visits = []
        daily_summaries = []
        visits_map = {v.id: v for v in request.visits}

        for route in routes:
            # Извлекаем номер дня из vehicle_id (формат "day_N")
            if hasattr(route, "vehicle_id"):
                vehicle_id = route.vehicle_id
            else:
                vehicle_id = route.get("vehicle_id", "day_1")

            try:
                day_number = int(vehicle_id.split("_")[1])
            except (IndexError, ValueError):
                day_number = 1

            day_date = plan_start_date + timedelta(days=day_number - 1)

            # Обрабатываем шаги маршрута
            if hasattr(route, "steps"):
                steps = route.steps
            else:
                steps = route.get("steps", [])

            day_distance = 0.0
            day_duration = 0
            sequence = 1
            first_time = None
            last_time = None

            for i, step in enumerate(steps):
                if hasattr(step, "job_id"):
                    job_id = step.job_id
                else:
                    job_id = step.get("job_id") or step.get("id")

                if not job_id or job_id.startswith("depot"):
                    continue

                visit_data = visits_map.get(job_id)
                if not visit_data:
                    continue

                # Время визита
                if hasattr(step, "arrival_time"):
                    arrival = step.arrival_time
                    departure = step.departure_time
                else:
                    arrival = datetime.combine(day_date, request.working_hours.start) + timedelta(minutes=sequence * 30)
                    service_time = (visit_data.service_time or 15) + (visit_data.manager_acceptance_time or 0)
                    departure = arrival + timedelta(minutes=service_time)

                if first_time is None:
                    first_time = arrival
                last_time = departure

                # Расстояние до следующей точки
                distance_to_next = None
                travel_time_to_next = None

                if hasattr(step, "distance_to_next"):
                    distance_to_next = step.distance_to_next / 1000  # м в км
                    travel_time_to_next = step.duration_to_next // 60 if hasattr(step, "duration_to_next") else None

                if distance_to_next:
                    day_distance += distance_to_next

                scheduled_visits.append(
                    ScheduledVisit(
                        visit_id=job_id,
                        day_number=day_number,
                        sequence_number=sequence,
                        scheduled_start=arrival,
                        scheduled_end=departure,
                        distance_to_next=round(distance_to_next, 2) if distance_to_next else None,
                        travel_time_to_next=travel_time_to_next,
                    )
                )

                sequence += 1

            # Статистика дня
            if steps and first_time and last_time:
                day_duration = int((last_time - first_time).total_seconds() / 60)

                daily_summaries.append(
                    DailySummary(
                        day_number=day_number,
                        visits_count=sequence - 1,
                        total_distance_km=round(day_distance, 2),
                        total_duration_minutes=day_duration,
                        start_time=first_time.time(),
                        end_time=last_time.time(),
                    )
                )

        return scheduled_visits, daily_summaries

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Вычисляет расстояние между двумя точками в км (формула Haversine)."""
        from math import asin, cos, radians, sin, sqrt

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        # Радиус Земли в км
        r = 6371
        return c * r


# Singleton instance
field_routing_service = FieldRoutingService()
