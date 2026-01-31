"""
Schemas for Field Team Routing API.

API для маршрутизации полевых команд с планированием на несколько дней.
"""

from datetime import datetime, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RoutingMode(str, Enum):
    """Режим передвижения."""

    CAR = "car"
    WALKING = "walking"


class WorkingHours(BaseModel):
    """Временной диапазон рабочего дня."""

    start: time = Field(..., description="Начало рабочего дня", examples=["09:00"])
    end: time = Field(..., description="Окончание рабочего дня", examples=["17:00"])

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("end must be after start")
        return v


class AvailableHours(BaseModel):
    """Время доступности клиента."""

    start: time = Field(..., description="Начало доступности", examples=["09:00"])
    end: time = Field(..., description="Окончание доступности", examples=["18:00"])


class Location(BaseModel):
    """GPS-координаты точки."""

    latitude: float = Field(..., ge=-90, le=90, description="Широта", examples=[41.311081])
    longitude: float = Field(..., ge=-180, le=180, description="Долгота", examples=[69.279737])


class VisitPoint(BaseModel):
    """Точка визита для планирования."""

    id: str = Field(..., min_length=1, description="Уникальный идентификатор точки", examples=["POINT-001"])
    location: Location = Field(..., description="GPS-координаты точки")
    available_hours: AvailableHours = Field(..., description="Время доступности клиента")
    service_time: Optional[int] = Field(
        default=15, ge=1, le=480, description="Предполагаемая длительность визита в минутах", examples=[15]
    )
    manager_acceptance_time: Optional[int] = Field(
        default=0, ge=0, le=120, description="Время на приемку менеджером в минутах", examples=[5]
    )
    priority: int = Field(..., ge=1, le=10, description="Приоритет визита (1 — наивысший)", examples=[1])


class FieldRoutingRequest(BaseModel):
    """
    Запрос на планирование маршрута полевой команды.

    Планирует оптимальный маршрут для заданных точек визита
    на указанное количество рабочих дней.
    """

    working_days: int = Field(
        ..., ge=1, le=14, description="Количество рабочих дней для планирования", examples=[4]
    )
    working_hours: WorkingHours = Field(..., description="Временной диапазон рабочего дня")
    max_visits_per_day: int = Field(
        ..., ge=1, le=50, description="Максимальное количество визитов в день", examples=[12]
    )
    routing_mode: RoutingMode = Field(..., description="Режим передвижения: car или walking")
    start_location: Optional[Location] = Field(
        default=None, description="Начальная точка маршрута (депо/офис). Если не указана, начинается с первой точки"
    )
    visits: list[VisitPoint] = Field(
        ..., min_length=1, max_length=1000, description="Массив точек визита для планирования"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "working_days": 4,
                "working_hours": {"start": "09:00", "end": "17:00"},
                "max_visits_per_day": 12,
                "routing_mode": "car",
                "start_location": {"latitude": 41.311081, "longitude": 69.279737},
                "visits": [
                    {
                        "id": "POINT-001",
                        "location": {"latitude": 41.328, "longitude": 69.255},
                        "available_hours": {"start": "09:00", "end": "18:00"},
                        "service_time": 20,
                        "manager_acceptance_time": 5,
                        "priority": 1,
                    },
                    {
                        "id": "POINT-002",
                        "location": {"latitude": 41.295, "longitude": 69.220},
                        "available_hours": {"start": "10:00", "end": "16:00"},
                        "service_time": 15,
                        "priority": 2,
                    },
                ],
            }
        }
    }


class ScheduledVisit(BaseModel):
    """Запланированный визит в маршруте."""

    visit_id: str = Field(..., description="Идентификатор точки визита")
    day_number: int = Field(..., ge=1, description="Номер рабочего дня")
    sequence_number: int = Field(..., ge=1, description="Порядковый номер визита в маршруте дня")
    scheduled_start: datetime = Field(..., description="Запланированное время начала визита")
    scheduled_end: datetime = Field(..., description="Запланированное время окончания визита")
    distance_to_next: Optional[float] = Field(
        default=None, ge=0, description="Расстояние до следующей точки в километрах"
    )
    travel_time_to_next: Optional[int] = Field(
        default=None, ge=0, description="Время в пути до следующей точки в минутах"
    )


class DailySummary(BaseModel):
    """Статистика маршрута за день."""

    day_number: int = Field(..., description="Номер рабочего дня")
    visits_count: int = Field(..., description="Количество визитов в этот день")
    total_distance_km: float = Field(..., description="Общее расстояние за день в км")
    total_duration_minutes: int = Field(..., description="Общая длительность маршрута за день в минутах")
    start_time: time = Field(..., description="Время начала маршрута")
    end_time: time = Field(..., description="Время окончания маршрута")


class UnassignedVisit(BaseModel):
    """Нераспределённый визит."""

    visit_id: str = Field(..., description="Идентификатор точки визита")
    reason: str = Field(..., description="Причина, почему визит не был распределён")


class FieldRoutingResponse(BaseModel):
    """
    Ответ с оптимизированным маршрутом полевой команды.

    Содержит общую статистику, детализацию по визитам
    и информацию о нераспределённых точках.
    """

    # Общая статистика маршрута
    total_visits: int = Field(..., description="Общее количество запланированных визитов")
    total_distance: float = Field(..., description="Общее расстояние в километрах")
    total_duration: int = Field(..., description="Общая длительность маршрута в минутах")

    # Статистика по дням
    days_used: int = Field(..., description="Количество использованных дней")
    daily_summary: list[DailySummary] = Field(..., description="Статистика по каждому дню")

    # Детализация по визитам
    scheduled_visits: list[ScheduledVisit] = Field(..., description="Массив запланированных визитов")

    # Нераспределённые визиты
    unassigned_visits: list[UnassignedVisit] = Field(
        default_factory=list, description="Визиты, которые не удалось распределить"
    )

    # Метаданные
    solver_used: str = Field(..., description="Использованный алгоритм оптимизации")
    computation_time_ms: int = Field(..., description="Время вычисления в миллисекундах")

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_visits": 45,
                "total_distance": 120.5,
                "total_duration": 1920,
                "days_used": 4,
                "daily_summary": [
                    {
                        "day_number": 1,
                        "visits_count": 12,
                        "total_distance_km": 32.5,
                        "total_duration_minutes": 480,
                        "start_time": "09:00",
                        "end_time": "17:00",
                    }
                ],
                "scheduled_visits": [
                    {
                        "visit_id": "POINT-001",
                        "day_number": 1,
                        "sequence_number": 1,
                        "scheduled_start": "2024-02-05T09:15:00",
                        "scheduled_end": "2024-02-05T09:35:00",
                        "distance_to_next": 3.2,
                        "travel_time_to_next": 12,
                    }
                ],
                "unassigned_visits": [],
                "solver_used": "vroom",
                "computation_time_ms": 1250,
            }
        }
    }
