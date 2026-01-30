"""
SFA-Routing Python Client

Простой клиент для работы с API оптимизации маршрутов.

Использование:
    from sfa_client import SFAClient

    client = SFAClient("http://localhost:8000")
    client.login("dispatcher", "password")

    # Создание агента
    agent = client.agents.create(name="Алишер", ...)

    # Генерация недельного плана
    plan = client.planning.generate_weekly(agent_id, "2024-02-05")

    # Оптимизация доставки
    routes = client.delivery.optimize(order_ids, vehicle_ids)
"""

import httpx
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SFAClientError(Exception):
    """Base exception for SFA Client errors."""

    def __init__(self, message: str, status_code: int = None, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AgentsAPI:
    """API для работы с агентами (торговыми представителями)."""

    def __init__(self, client: "SFAClient"):
        self._client = client

    def list(self, skip: int = 0, limit: int = 100) -> list[dict]:
        """Получить список агентов."""
        return self._client._get("/agents", params={"skip": skip, "limit": limit})

    def get(self, agent_id: str | UUID) -> dict:
        """Получить агента по ID."""
        return self._client._get(f"/agents/{agent_id}")

    def create(
        self,
        name: str,
        external_id: str,
        start_latitude: float,
        start_longitude: float,
        phone: str = None,
        email: str = None,
        work_start: str = "09:00",
        work_end: str = "18:00",
        max_visits_per_day: int = 15,
    ) -> dict:
        """Создать нового агента."""
        data = {
            "name": name,
            "external_id": external_id,
            "start_latitude": start_latitude,
            "start_longitude": start_longitude,
            "work_start": work_start,
            "work_end": work_end,
            "max_visits_per_day": max_visits_per_day,
        }
        if phone:
            data["phone"] = phone
        if email:
            data["email"] = email
        return self._client._post("/agents", data)

    def update_location(self, agent_id: str | UUID, latitude: float, longitude: float) -> dict:
        """Обновить текущую локацию агента (GPS)."""
        return self._client._patch(
            f"/agents/{agent_id}/location",
            {"current_latitude": latitude, "current_longitude": longitude},
        )


class ClientsAPI:
    """API для работы с клиентами (торговыми точками)."""

    def __init__(self, client: "SFAClient"):
        self._client = client

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        category: str = None,
        agent_id: str = None,
    ) -> list[dict]:
        """Получить список клиентов с фильтрацией."""
        params = {"skip": skip, "limit": limit}
        if category:
            params["category"] = category
        if agent_id:
            params["agent_id"] = agent_id
        return self._client._get("/clients", params=params)

    def get(self, client_id: str | UUID) -> dict:
        """Получить клиента по ID."""
        return self._client._get(f"/clients/{client_id}")

    def create(
        self,
        name: str,
        external_id: str,
        address: str,
        latitude: float,
        longitude: float,
        category: str = "B",
        agent_id: str = None,
        visit_duration_minutes: int = 15,
        time_window_start: str = "09:00",
        time_window_end: str = "18:00",
        contact_person: str = None,
        phone: str = None,
    ) -> dict:
        """Создать нового клиента."""
        data = {
            "name": name,
            "external_id": external_id,
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "category": category,
            "visit_duration_minutes": visit_duration_minutes,
            "time_window_start": time_window_start,
            "time_window_end": time_window_end,
        }
        if agent_id:
            data["agent_id"] = agent_id
        if contact_person:
            data["contact_person"] = contact_person
        if phone:
            data["phone"] = phone
        return self._client._post("/clients", data)


class VehiclesAPI:
    """API для работы с транспортом."""

    def __init__(self, client: "SFAClient"):
        self._client = client

    def list(self, skip: int = 0, limit: int = 100) -> list[dict]:
        """Получить список транспорта."""
        return self._client._get("/vehicles", params={"skip": skip, "limit": limit})

    def get(self, vehicle_id: str | UUID) -> dict:
        """Получить транспорт по ID."""
        return self._client._get(f"/vehicles/{vehicle_id}")

    def create(
        self,
        name: str,
        license_plate: str,
        capacity_kg: float,
        capacity_volume_m3: float,
        start_latitude: float,
        start_longitude: float,
        work_start: str = "08:00",
        work_end: str = "20:00",
        is_refrigerated: bool = False,
        driver_name: str = None,
        driver_phone: str = None,
    ) -> dict:
        """Создать новый транспорт."""
        data = {
            "name": name,
            "license_plate": license_plate,
            "capacity_kg": capacity_kg,
            "capacity_volume_m3": capacity_volume_m3,
            "start_latitude": start_latitude,
            "start_longitude": start_longitude,
            "work_start": work_start,
            "work_end": work_end,
            "is_refrigerated": is_refrigerated,
        }
        if driver_name:
            data["driver_name"] = driver_name
        if driver_phone:
            data["driver_phone"] = driver_phone
        return self._client._post("/vehicles", data)


class PlanningAPI:
    """API для недельного планирования (SFA)."""

    def __init__(self, client: "SFAClient"):
        self._client = client

    def generate_weekly(
        self,
        agent_id: str | UUID,
        week_start_date: str | date,
        include_high_priority: bool = True,
        respect_categories: bool = True,
    ) -> dict:
        """
        Сгенерировать недельный план для агента.

        Args:
            agent_id: ID агента
            week_start_date: Дата начала недели (понедельник)
            include_high_priority: Включать приоритетных клиентов
            respect_categories: Учитывать категории A/B/C

        Returns:
            Недельный план с ежедневными маршрутами
        """
        if isinstance(week_start_date, date):
            week_start_date = week_start_date.isoformat()

        return self._client._post(
            "/planning/weekly",
            {
                "agent_id": str(agent_id),
                "week_start_date": week_start_date,
                "include_high_priority": include_high_priority,
                "respect_categories": respect_categories,
            },
        )

    def get_weekly_plan(self, agent_id: str | UUID, week_start_date: str | date) -> dict:
        """Получить существующий недельный план."""
        if isinstance(week_start_date, date):
            week_start_date = week_start_date.isoformat()
        return self._client._get(f"/planning/agent/{agent_id}/week/{week_start_date}")

    def get_daily_plan(self, agent_id: str | UUID, plan_date: str | date) -> dict:
        """Получить план на конкретный день."""
        if isinstance(plan_date, date):
            plan_date = plan_date.isoformat()
        return self._client._get(f"/planning/agent/{agent_id}/day/{plan_date}")

    def update_visit(
        self,
        visit_id: str | UUID,
        status: str,
        actual_time: str = None,
        actual_duration_minutes: int = None,
        notes: str = None,
    ) -> dict:
        """
        Обновить статус визита.

        Args:
            visit_id: ID визита
            status: "planned", "completed", "skipped"
            actual_time: Фактическое время визита
            actual_duration_minutes: Фактическая длительность
            notes: Заметки агента
        """
        data = {"status": status}
        if actual_time:
            data["actual_time"] = actual_time
        if actual_duration_minutes:
            data["actual_duration_minutes"] = actual_duration_minutes
        if notes:
            data["notes"] = notes
        return self._client._patch(f"/planning/visits/{visit_id}", data)


class DeliveryAPI:
    """API для оптимизации доставки (VRP)."""

    def __init__(self, client: "SFAClient"):
        self._client = client

    def create_order(
        self,
        client_id: str | UUID,
        weight_kg: float,
        time_window_start: str | datetime,
        time_window_end: str | datetime,
        external_id: str = None,
        volume_m3: float = None,
        priority: int = 5,
    ) -> dict:
        """Создать заказ на доставку."""
        if isinstance(time_window_start, datetime):
            time_window_start = time_window_start.isoformat()
        if isinstance(time_window_end, datetime):
            time_window_end = time_window_end.isoformat()

        data = {
            "client_id": str(client_id),
            "weight_kg": weight_kg,
            "time_window_start": time_window_start,
            "time_window_end": time_window_end,
            "priority": priority,
        }
        if external_id:
            data["external_id"] = external_id
        if volume_m3:
            data["volume_m3"] = volume_m3
        return self._client._post("/delivery/orders", data)

    def list_orders(
        self,
        status: str = None,
        date_from: str = None,
        date_to: str = None,
    ) -> list[dict]:
        """Получить список заказов."""
        params = {}
        if status:
            params["status"] = status
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._client._get("/delivery/orders", params=params)

    def optimize(
        self,
        order_ids: list[str | UUID],
        vehicle_ids: list[str | UUID],
        route_date: str | date,
        solver: str = "auto",
        minimize_vehicles: bool = True,
        respect_time_windows: bool = True,
    ) -> dict:
        """
        Оптимизировать маршруты доставки.

        Args:
            order_ids: Список ID заказов
            vehicle_ids: Список ID транспорта
            route_date: Дата маршрута
            solver: "auto", "vroom", "ortools", "genetic"
            minimize_vehicles: Минимизировать количество авто
            respect_time_windows: Соблюдать временные окна

        Returns:
            Оптимизированные маршруты
        """
        if isinstance(route_date, date):
            route_date = route_date.isoformat()

        return self._client._post(
            "/delivery/optimize",
            {
                "order_ids": [str(oid) for oid in order_ids],
                "vehicle_ids": [str(vid) for vid in vehicle_ids],
                "date": route_date,
                "solver": solver,
                "options": {
                    "minimize_vehicles": minimize_vehicles,
                    "respect_time_windows": respect_time_windows,
                },
            },
        )

    def get_route(self, route_id: str | UUID) -> dict:
        """Получить детали маршрута."""
        return self._client._get(f"/delivery/routes/{route_id}")

    def reoptimize(
        self,
        route_id: str | UUID,
        reason: str = "manual",
        excluded_order_ids: list[str] = None,
    ) -> dict:
        """Переоптимизировать существующий маршрут."""
        data = {"reason": reason}
        if excluded_order_ids:
            data["excluded_order_ids"] = excluded_order_ids
        return self._client._post(f"/delivery/routes/{route_id}/reoptimize", data)


class BulkAPI:
    """API для массового импорта."""

    def __init__(self, client: "SFAClient"):
        self._client = client

    def import_orders(self, orders: list[dict], idempotency_key: str = None) -> dict:
        """
        Массовый импорт заказов.

        Args:
            orders: Список заказов
            idempotency_key: Ключ идемпотентности

        Returns:
            Результат импорта с количеством успешных/неуспешных
        """
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return self._client._post("/bulk/orders", {"orders": orders}, headers=headers)


class SFAClient:
    """
    Клиент для работы с SFA-Routing API.

    Примеры использования:

        # Инициализация
        client = SFAClient("http://localhost:8000")
        client.login("dispatcher", "password")

        # Работа с агентами
        agents = client.agents.list()
        agent = client.agents.create(name="Алишер", ...)

        # Планирование
        plan = client.planning.generate_weekly(agent["id"], "2024-02-05")

        # Оптимизация доставки
        order = client.delivery.create_order(client_id, weight_kg=100, ...)
        routes = client.delivery.optimize([order["id"]], [vehicle["id"]])
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_prefix: str = "/api/v1"):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix
        self._tokens: Optional[AuthTokens] = None
        self._http = httpx.Client(timeout=60.0)

        # API modules
        self.agents = AgentsAPI(self)
        self.clients = ClientsAPI(self)
        self.vehicles = VehiclesAPI(self)
        self.planning = PlanningAPI(self)
        self.delivery = DeliveryAPI(self)
        self.bulk = BulkAPI(self)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{self.api_prefix}{path}"

    def _headers(self, extra: dict = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._tokens:
            headers["Authorization"] = f"Bearer {self._tokens.access_token}"
        if extra:
            headers.update(extra)
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = {"detail": response.text}
            raise SFAClientError(
                message=error_data.get("detail", "Unknown error"),
                status_code=response.status_code,
                details=error_data,
            )
        if response.status_code == 204:
            return None
        return response.json()

    def _get(self, path: str, params: dict = None) -> Any:
        response = self._http.get(self._url(path), headers=self._headers(), params=params)
        return self._handle_response(response)

    def _post(self, path: str, data: dict = None, headers: dict = None) -> Any:
        response = self._http.post(
            self._url(path),
            headers=self._headers(headers),
            json=data,
        )
        return self._handle_response(response)

    def _patch(self, path: str, data: dict) -> Any:
        response = self._http.patch(self._url(path), headers=self._headers(), json=data)
        return self._handle_response(response)

    def _delete(self, path: str) -> Any:
        response = self._http.delete(self._url(path), headers=self._headers())
        return self._handle_response(response)

    def login(self, username: str, password: str) -> AuthTokens:
        """
        Аутентификация пользователя.

        Args:
            username: Имя пользователя
            password: Пароль

        Returns:
            AuthTokens с access и refresh токенами
        """
        response = self._http.post(
            self._url("/auth/login"),
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = self._handle_response(response)
        self._tokens = AuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data.get("token_type", "bearer"),
        )
        return self._tokens

    def refresh_token(self) -> AuthTokens:
        """Обновить access токен используя refresh токен."""
        if not self._tokens:
            raise SFAClientError("Not authenticated")
        response = self._http.post(
            self._url("/auth/refresh"),
            json={"refresh_token": self._tokens.refresh_token},
        )
        data = self._handle_response(response)
        self._tokens = AuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
        )
        return self._tokens

    def health_check(self) -> dict:
        """Проверка работоспособности API."""
        response = self._http.get(self._url("/health"))
        return self._handle_response(response)

    def close(self):
        """Закрыть HTTP соединение."""
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
