"""
Smartup ERP integration client.

Smartup is a popular ERP system in Uzbekistan used for:
- Sales management
- Inventory management
- Customer management
- Order processing

This module provides integration to sync:
- Agents (торговые представители)
- Clients (клиенты/торговые точки)
- Orders (заказы)
- Visit reports (отчёты о визитах)
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import httpx

from app.core.config import settings


@dataclass
class ERPAgent:
    """Agent data from ERP."""

    external_id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    territory: Optional[str]
    is_active: bool


@dataclass
class ERPClient:
    """Client data from ERP."""

    external_id: str
    name: str
    address: str
    latitude: Optional[float]
    longitude: Optional[float]
    phone: Optional[str]
    contact_person: Optional[str]
    category: str  # A, B, C
    agent_external_id: Optional[str]
    credit_limit: Optional[Decimal]
    is_active: bool


@dataclass
class ERPOrder:
    """Order data from ERP."""

    external_id: str
    client_external_id: str
    order_date: datetime
    delivery_date: Optional[datetime]
    items: list[dict]
    total_weight_kg: Decimal
    total_amount: Decimal
    status: str
    notes: Optional[str]


@dataclass
class ERPVisitReport:
    """Visit report to send to ERP."""

    agent_external_id: str
    client_external_id: str
    visit_date: datetime
    arrival_time: datetime
    departure_time: datetime
    status: str  # completed, skipped
    notes: Optional[str]
    photos: Optional[list[str]]
    order_created: bool
    order_external_id: Optional[str]


class SmartupERPClient:
    """
    Client for Smartup ERP REST API integration.

    API Documentation: https://smartup.uz/api-docs (example)

    Authentication: API Key or OAuth2 token in headers
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url or getattr(settings, "ERP_BASE_URL", "https://api.smartup.uz/v1")
        self.api_key = api_key or getattr(settings, "ERP_API_KEY", "")
        self.timeout = httpx.Timeout(timeout, connect=10.0)

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Make API request."""
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                json=data,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    # ==================== Agent Sync ====================

    async def get_agents(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ERPAgent]:
        """
        Get agents from ERP.

        Args:
            modified_since: Only return agents modified after this datetime
            limit: Maximum number of records
            offset: Pagination offset

        Returns:
            List of ERPAgent objects
        """
        params = {"limit": limit, "offset": offset}
        if modified_since:
            params["modified_since"] = modified_since.isoformat()

        data = await self._request("GET", "/agents", params=params)

        return [
            ERPAgent(
                external_id=item["id"],
                name=item["name"],
                phone=item.get("phone"),
                email=item.get("email"),
                territory=item.get("territory"),
                is_active=item.get("is_active", True),
            )
            for item in data.get("items", [])
        ]

    # ==================== Client Sync ====================

    async def get_clients(
        self,
        agent_id: Optional[str] = None,
        modified_since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ERPClient]:
        """
        Get clients from ERP.

        Args:
            agent_id: Filter by assigned agent
            modified_since: Only return clients modified after this datetime
            limit: Maximum number of records
            offset: Pagination offset

        Returns:
            List of ERPClient objects
        """
        params = {"limit": limit, "offset": offset}
        if agent_id:
            params["agent_id"] = agent_id
        if modified_since:
            params["modified_since"] = modified_since.isoformat()

        data = await self._request("GET", "/clients", params=params)

        return [
            ERPClient(
                external_id=item["id"],
                name=item["name"],
                address=item.get("address", ""),
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                phone=item.get("phone"),
                contact_person=item.get("contact_person"),
                category=item.get("category", "B"),
                agent_external_id=item.get("agent_id"),
                credit_limit=Decimal(str(item.get("credit_limit", 0))) if item.get("credit_limit") else None,
                is_active=item.get("is_active", True),
            )
            for item in data.get("items", [])
        ]

    # ==================== Order Sync ====================

    async def get_orders(
        self,
        status: Optional[str] = None,
        delivery_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ERPOrder]:
        """
        Get orders from ERP.

        Args:
            status: Filter by order status (pending, confirmed, shipped, etc.)
            delivery_date: Filter by delivery date
            limit: Maximum number of records
            offset: Pagination offset

        Returns:
            List of ERPOrder objects
        """
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if delivery_date:
            params["delivery_date"] = delivery_date.isoformat()

        data = await self._request("GET", "/orders", params=params)

        return [
            ERPOrder(
                external_id=item["id"],
                client_external_id=item["client_id"],
                order_date=datetime.fromisoformat(item["order_date"]),
                delivery_date=datetime.fromisoformat(item["delivery_date"]) if item.get("delivery_date") else None,
                items=item.get("items", []),
                total_weight_kg=Decimal(str(item.get("total_weight", 0))),
                total_amount=Decimal(str(item.get("total_amount", 0))),
                status=item.get("status", "pending"),
                notes=item.get("notes"),
            )
            for item in data.get("items", [])
        ]

    async def update_order_status(
        self,
        order_id: str,
        status: str,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Update order status in ERP.

        Args:
            order_id: ERP order ID
            status: New status (delivered, failed, etc.)
            notes: Optional notes

        Returns:
            Updated order data
        """
        data = {"status": status}
        if notes:
            data["notes"] = notes

        return await self._request("PATCH", f"/orders/{order_id}", data=data)

    # ==================== Visit Reports ====================

    async def submit_visit_report(self, report: ERPVisitReport) -> dict:
        """
        Submit visit report to ERP.

        Args:
            report: Visit report data

        Returns:
            Created report ID and status
        """
        data = {
            "agent_id": report.agent_external_id,
            "client_id": report.client_external_id,
            "visit_date": report.visit_date.isoformat(),
            "arrival_time": report.arrival_time.isoformat(),
            "departure_time": report.departure_time.isoformat(),
            "status": report.status,
            "notes": report.notes,
            "photos": report.photos or [],
            "order_created": report.order_created,
            "order_id": report.order_external_id,
        }

        return await self._request("POST", "/visit-reports", data=data)

    # ==================== Sync Operations ====================

    async def full_sync_agents(self) -> dict[str, int]:
        """
        Perform full sync of agents from ERP.

        Returns:
            Sync statistics (created, updated, deactivated)
        """
        stats = {"created": 0, "updated": 0, "deactivated": 0}
        offset = 0
        limit = 100

        while True:
            agents = await self.get_agents(limit=limit, offset=offset)
            if not agents:
                break

            for agent in agents:
                # Here you would sync with local database
                # This is a placeholder - actual implementation would use
                # the AgentService to create/update records
                stats["updated"] += 1

            offset += limit

        return stats

    async def full_sync_clients(self) -> dict[str, int]:
        """
        Perform full sync of clients from ERP.

        Returns:
            Sync statistics (created, updated, deactivated)
        """
        stats = {"created": 0, "updated": 0, "deactivated": 0}
        offset = 0
        limit = 100

        while True:
            clients = await self.get_clients(limit=limit, offset=offset)
            if not clients:
                break

            for client in clients:
                # Sync with local database
                stats["updated"] += 1

            offset += limit

        return stats

    async def sync_orders_for_delivery(
        self,
        delivery_date: date,
    ) -> list[ERPOrder]:
        """
        Get orders for delivery optimization.

        Args:
            delivery_date: Date for delivery

        Returns:
            List of orders ready for delivery
        """
        return await self.get_orders(
            status="confirmed",
            delivery_date=delivery_date,
        )

    # ==================== Health Check ====================

    async def health_check(self) -> bool:
        """Check if ERP API is available."""
        try:
            await self._request("GET", "/health")
            return True
        except Exception:
            return False


# Singleton instance (configured from settings)
smartup_client = SmartupERPClient()


# ==================== Sync Tasks ====================


async def sync_from_erp():
    """
    Background task to sync data from ERP.

    Should be scheduled to run periodically (e.g., every hour).
    """
    client = SmartupERPClient()

    # Check connection
    if not await client.health_check():
        print("ERP API is not available")
        return

    # Sync agents
    agent_stats = await client.full_sync_agents()
    print(f"Agent sync: {agent_stats}")

    # Sync clients
    client_stats = await client.full_sync_clients()
    print(f"Client sync: {client_stats}")


async def export_visit_reports_to_erp(
    visit_plans: list[dict],
) -> dict[str, int]:
    """
    Export completed visit reports to ERP.

    Args:
        visit_plans: List of completed visit plans

    Returns:
        Export statistics
    """
    client = SmartupERPClient()
    stats = {"success": 0, "failed": 0}

    for plan in visit_plans:
        if plan.get("status") not in ["completed", "skipped"]:
            continue

        report = ERPVisitReport(
            agent_external_id=plan["agent_external_id"],
            client_external_id=plan["client_external_id"],
            visit_date=plan["visit_date"],
            arrival_time=plan.get("actual_arrival_time") or plan["planned_time"],
            departure_time=plan.get("actual_departure_time") or plan["planned_time"],
            status=plan["status"],
            notes=plan.get("notes"),
            photos=None,
            order_created=False,
            order_external_id=None,
        )

        try:
            await client.submit_visit_report(report)
            stats["success"] += 1
        except Exception as e:
            print(f"Failed to export visit report: {e}")
            stats["failed"] += 1

    return stats
