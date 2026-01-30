"""
Tests for bulk, export, and webhook API endpoints.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import date, time


class TestBulkImportEndpoint:
    """Tests for /api/v1/bulk/orders endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_import_success(self, client, auth_headers, sample_client_data):
        """Test successful bulk order import."""
        # First create a client to reference
        client_response = await client.post(
            "/api/v1/clients",
            json=sample_client_data,
            headers=auth_headers
        )
        assert client_response.status_code == 201
        client_ext_id = sample_client_data["external_id"]

        # Now import orders
        orders = [
            {
                "external_id": "ORD-001",
                "client_external_id": client_ext_id,
                "weight_kg": 10.5,
                "volume_m3": 0.5,
                "order_value": 150000,
                "delivery_date": str(date.today()),
                "priority": 2,
            },
            {
                "external_id": "ORD-002",
                "client_external_id": client_ext_id,
                "weight_kg": 5.0,
                "delivery_date": str(date.today()),
                "priority": 1,
            },
        ]

        response = await client.post(
            "/api/v1/bulk/orders",
            json=orders,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_processed"] == 2
        assert data["success_count"] == 2
        assert data["error_count"] == 0

    @pytest.mark.asyncio
    async def test_bulk_import_partial_failure(self, client, auth_headers, sample_client_data):
        """Test bulk import with some invalid orders."""
        # Create a client
        await client.post(
            "/api/v1/clients",
            json=sample_client_data,
            headers=auth_headers
        )
        client_ext_id = sample_client_data["external_id"]

        orders = [
            {
                "external_id": "ORD-003",
                "client_external_id": client_ext_id,
                "weight_kg": 10.0,
                "delivery_date": str(date.today()),
            },
            {
                "external_id": "ORD-004",
                "client_external_id": "NON_EXISTENT_CLIENT",
                "weight_kg": 5.0,
                "delivery_date": str(date.today()),
            },
        ]

        response = await client.post(
            "/api/v1/bulk/orders",
            json=orders,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_processed"] == 2
        assert data["success_count"] == 1
        assert data["error_count"] == 1
        assert "NON_EXISTENT_CLIENT" in data["errors"][0]["error"]

    @pytest.mark.asyncio
    async def test_bulk_import_empty_list(self, client, auth_headers):
        """Test bulk import with empty order list."""
        response = await client.post(
            "/api/v1/bulk/orders",
            json=[],
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_processed"] == 0
        assert data["success_count"] == 0

    @pytest.mark.asyncio
    async def test_bulk_import_unauthorized(self, client):
        """Test bulk import without authentication."""
        response = await client.post(
            "/api/v1/bulk/orders",
            json=[{"external_id": "X", "client_external_id": "Y", "weight_kg": 1, "delivery_date": "2024-01-01"}]
        )
        assert response.status_code == 401


class TestWebhookEndpoints:
    """Tests for /api/v1/webhooks endpoints."""

    @pytest.mark.asyncio
    async def test_create_webhook(self, client, auth_headers):
        """Test creating a webhook subscription."""
        webhook_data = {
            "name": "ERP Integration",
            "url": "https://erp.example.com/webhook",
            "secret": "whsec_test_secret_key_12345",
            "events": ["optimization.completed", "route.started"],
            "description": "Notify ERP when optimization completes"
        }

        response = await client.post(
            "/api/v1/webhooks",
            json=webhook_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == webhook_data["name"]
        assert data["url"] == webhook_data["url"]
        assert data["events"] == webhook_data["events"]
        assert data["is_active"] is True
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_webhooks(self, client, auth_headers):
        """Test listing webhooks."""
        # Create a webhook first
        webhook_data = {
            "name": "Test Hook",
            "url": "https://test.example.com/hook",
            "secret": "secret123",
            "events": ["order.created"],
        }
        await client.post("/api/v1/webhooks", json=webhook_data, headers=auth_headers)

        # List webhooks
        response = await client.get("/api/v1/webhooks", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_delete_webhook(self, client, auth_headers):
        """Test deleting a webhook."""
        # Create a webhook
        webhook_data = {
            "name": "To Delete",
            "url": "https://delete.example.com/hook",
            "secret": "secret",
            "events": ["test.event"],
        }
        create_response = await client.post(
            "/api/v1/webhooks",
            json=webhook_data,
            headers=auth_headers
        )
        webhook_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/api/v1/webhooks/{webhook_id}",
            headers=auth_headers
        )
        assert response.status_code == 204

        # Verify it's gone
        list_response = await client.get("/api/v1/webhooks", headers=auth_headers)
        webhook_ids = [w["id"] for w in list_response.json()]
        assert webhook_id not in webhook_ids

    @pytest.mark.asyncio
    async def test_delete_nonexistent_webhook(self, client, auth_headers):
        """Test deleting a webhook that doesn't exist."""
        fake_id = str(uuid4())
        response = await client.delete(
            f"/api/v1/webhooks/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_webhook_unauthorized(self, client):
        """Test webhook endpoints without authentication."""
        response = await client.get("/api/v1/webhooks")
        assert response.status_code == 401


class TestExportEndpoints:
    """Tests for /api/v1/export endpoints."""

    @pytest.mark.asyncio
    async def test_export_daily_plan_not_found(self, client, auth_headers):
        """Test export for non-existent agent/date."""
        fake_agent_id = str(uuid4())
        response = await client.get(
            f"/api/v1/export/daily-plan/{fake_agent_id}/2024-01-15",
            headers=auth_headers
        )
        # Should return 404 or empty PDF
        assert response.status_code in [404, 200]

    @pytest.mark.asyncio
    async def test_export_weekly_plan_not_found(self, client, auth_headers):
        """Test weekly export for non-existent agent."""
        fake_agent_id = str(uuid4())
        response = await client.get(
            f"/api/v1/export/weekly-plan/{fake_agent_id}/2024-01-15",
            headers=auth_headers
        )
        assert response.status_code in [404, 200]

    @pytest.mark.asyncio
    async def test_export_delivery_route_not_found(self, client, auth_headers):
        """Test route export for non-existent route."""
        fake_route_id = str(uuid4())
        response = await client.get(
            f"/api/v1/export/delivery-route/{fake_route_id}",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_export_unauthorized(self, client):
        """Test export endpoints without authentication."""
        response = await client.get(f"/api/v1/export/daily-plan/{uuid4()}/2024-01-15")
        assert response.status_code == 401
