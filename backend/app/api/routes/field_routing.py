"""
Field Team Routing API Endpoints.

API для маршрутизации полевых команд с планированием на несколько дней.
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.rate_limit import limiter
from app.schemas.field_routing import FieldRoutingRequest, FieldRoutingResponse
from app.services.planning.field_routing import FieldRoutingService, field_routing_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/field-routing", tags=["Field Routing"])


class FieldRoutingError(BaseModel):
    """Модель ошибки."""

    detail: str
    error_code: Optional[str] = None


def get_field_routing_service() -> FieldRoutingService:
    """Dependency injection для сервиса маршрутизации."""
    return field_routing_service


@router.post(
    "/plan",
    response_model=FieldRoutingResponse,
    status_code=status.HTTP_200_OK,
    summary="Планирование маршрута полевой команды",
    description="""
    Планирует оптимальный маршрут для полевой команды на указанное количество рабочих дней.

    ## Возможности

    - **Многодневное планирование**: Распределение визитов на несколько рабочих дней
    - **Учёт приоритетов**: Визиты с высоким приоритетом планируются первыми
    - **Временные окна**: Учёт времени доступности клиентов
    - **Режимы передвижения**: Поддержка автомобиля и пешей навигации
    - **Автоматический выбор солвера**: VROOM для малых задач, OR-Tools/Genetic для больших

    ## Алгоритм

    1. Точки сортируются по приоритету (1 = наивысший)
    2. Для каждого дня создаётся оптимальный маршрут
    3. Учитываются ограничения: max_visits_per_day, working_hours
    4. Возвращается детализированное расписание с временами прибытия

    ## Лимиты

    - Максимум 1000 точек визита за один запрос
    - Максимум 14 рабочих дней для планирования
    - Максимум 50 визитов в день
    """,
    responses={
        200: {
            "description": "Маршрут успешно спланирован",
            "model": FieldRoutingResponse,
        },
        400: {
            "description": "Некорректные входные данные",
            "model": FieldRoutingError,
        },
        422: {
            "description": "Ошибка валидации",
        },
        500: {
            "description": "Внутренняя ошибка сервера",
            "model": FieldRoutingError,
        },
    },
)
@limiter.limit("30/minute")
async def plan_field_route(
    request: FieldRoutingRequest,
    start_date: Optional[date] = Query(
        default=None,
        description="Дата начала планирования (по умолчанию завтра)",
        examples=["2024-02-05"],
    ),
    service: FieldRoutingService = Depends(get_field_routing_service),
) -> FieldRoutingResponse:
    """
    Планирует маршрут для полевой команды.

    Принимает список точек визита с параметрами и возвращает
    оптимизированный маршрут на указанное количество дней.
    """
    try:
        logger.info(
            f"Field routing request: {len(request.visits)} visits, "
            f"{request.working_days} days, mode={request.routing_mode}"
        )

        response = await service.plan_route(
            request=request,
            plan_start_date=start_date,
        )

        logger.info(
            f"Field routing completed: {response.total_visits} visits scheduled, "
            f"{len(response.unassigned_visits)} unassigned, "
            f"solver={response.solver_used}, time={response.computation_time_ms}ms"
        )

        return response

    except ValueError as e:
        logger.warning(f"Field routing validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Field routing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при планировании маршрута. Попробуйте позже.",
        )


@router.post(
    "/validate",
    status_code=status.HTTP_200_OK,
    summary="Валидация входных данных",
    description="Проверяет корректность входных данных без выполнения планирования.",
)
async def validate_field_routing_request(
    request: FieldRoutingRequest,
) -> dict:
    """
    Валидирует входные данные для планирования маршрута.

    Проверяет:
    - Корректность координат
    - Непротиворечивость временных окон
    - Уникальность ID точек
    - Достаточность дней для всех визитов
    """
    errors = []
    warnings = []

    # Проверка уникальности ID
    visit_ids = [v.id for v in request.visits]
    if len(visit_ids) != len(set(visit_ids)):
        duplicates = [id for id in visit_ids if visit_ids.count(id) > 1]
        errors.append(f"Дублирующиеся ID точек: {set(duplicates)}")

    # Проверка достаточности дней
    max_possible_visits = request.working_days * request.max_visits_per_day
    if len(request.visits) > max_possible_visits:
        warnings.append(
            f"Запрошено {len(request.visits)} визитов, но максимум возможно "
            f"{max_possible_visits} ({request.working_days} дней × {request.max_visits_per_day} визитов/день)"
        )

    # Проверка временных окон
    for visit in request.visits:
        if visit.available_hours.start >= visit.available_hours.end:
            errors.append(f"Точка {visit.id}: время начала >= времени окончания доступности")

        # Проверка пересечения с рабочими часами
        if visit.available_hours.start > request.working_hours.end:
            errors.append(
                f"Точка {visit.id}: время доступности ({visit.available_hours.start}) "
                f"позже окончания рабочего дня ({request.working_hours.end})"
            )
        if visit.available_hours.end < request.working_hours.start:
            errors.append(
                f"Точка {visit.id}: время доступности заканчивается ({visit.available_hours.end}) "
                f"до начала рабочего дня ({request.working_hours.start})"
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "total_visits": len(request.visits),
            "working_days": request.working_days,
            "max_visits_per_day": request.max_visits_per_day,
            "max_possible_visits": max_possible_visits,
            "routing_mode": request.routing_mode,
        },
    }
