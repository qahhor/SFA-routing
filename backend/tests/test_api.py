"""
API endpoint tests.

Note: CRUD endpoints for agents, clients, and vehicles are documented
in CLAUDE.md but not yet implemented. Tests for these endpoints are
marked as skipped until implementation is complete.
"""
import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test basic health check."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.skip(reason="Agent CRUD endpoints not yet implemented - documented in CLAUDE.md roadmap")
class TestAgentEndpoints:
    """Tests for agent API endpoints."""

    @pytest.mark.asyncio
    async def test_create_agent(self, client: AsyncClient, sample_agent_data):
        """Test creating an agent."""
        response = await client.post("/api/v1/agents", json=sample_agent_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_agent_data["name"]
        assert data["external_id"] == sample_agent_data["external_id"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_agents(self, client: AsyncClient, sample_agent_data):
        """Test listing agents."""
        # Create an agent first
        await client.post("/api/v1/agents", json=sample_agent_data)

        response = await client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_agent(self, client: AsyncClient, sample_agent_data):
        """Test getting a single agent."""
        # Create an agent
        create_response = await client.post("/api/v1/agents", json=sample_agent_data)
        agent_id = create_response.json()["id"]

        # Get the agent
        response = await client.get(f"/api/v1/agents/{agent_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == agent_id
        assert data["name"] == sample_agent_data["name"]

    @pytest.mark.asyncio
    async def test_update_agent(self, client: AsyncClient, sample_agent_data):
        """Test updating an agent."""
        # Create an agent
        create_response = await client.post("/api/v1/agents", json=sample_agent_data)
        agent_id = create_response.json()["id"]

        # Update the agent
        update_data = {"name": "Updated Agent Name"}
        response = await client.put(f"/api/v1/agents/{agent_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Agent Name"

    @pytest.mark.asyncio
    async def test_delete_agent(self, client: AsyncClient, sample_agent_data):
        """Test deleting an agent."""
        # Create an agent
        create_response = await client.post("/api/v1/agents", json=sample_agent_data)
        agent_id = create_response.json()["id"]

        # Delete the agent
        response = await client.delete(f"/api/v1/agents/{agent_id}")
        assert response.status_code == 204

        # Verify it's deleted
        get_response = await client.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 404


@pytest.mark.skip(reason="Client CRUD endpoints not yet implemented - documented in CLAUDE.md roadmap")
class TestClientEndpoints:
    """Tests for client API endpoints."""

    @pytest.mark.asyncio
    async def test_create_client(self, client: AsyncClient, sample_client_data):
        """Test creating a client."""
        response = await client.post("/api/v1/clients", json=sample_client_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_client_data["name"]
        assert data["category"] == sample_client_data["category"]

    @pytest.mark.asyncio
    async def test_list_clients(self, client: AsyncClient, sample_client_data):
        """Test listing clients."""
        # Create a client first
        await client.post("/api/v1/clients", json=sample_client_data)

        response = await client.get("/api/v1/clients")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_filter_clients_by_category(
        self, client: AsyncClient, sample_client_data
    ):
        """Test filtering clients by category."""
        # Create a client
        await client.post("/api/v1/clients", json=sample_client_data)

        # Filter by category
        response = await client.get("/api/v1/clients?category=B")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["category"] == "B"


@pytest.mark.skip(reason="Vehicle CRUD endpoints not yet implemented - documented in CLAUDE.md roadmap")
class TestVehicleEndpoints:
    """Tests for vehicle API endpoints."""

    @pytest.mark.asyncio
    async def test_create_vehicle(self, client: AsyncClient, sample_vehicle_data):
        """Test creating a vehicle."""
        response = await client.post("/api/v1/vehicles", json=sample_vehicle_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_vehicle_data["name"]
        assert data["license_plate"] == sample_vehicle_data["license_plate"]

    @pytest.mark.asyncio
    async def test_list_vehicles(self, client: AsyncClient, sample_vehicle_data):
        """Test listing vehicles."""
        # Create a vehicle first
        await client.post("/api/v1/vehicles", json=sample_vehicle_data)

        response = await client.get("/api/v1/vehicles")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_duplicate_license_plate(
        self, client: AsyncClient, sample_vehicle_data
    ):
        """Test that duplicate license plates are rejected."""
        # Create first vehicle
        await client.post("/api/v1/vehicles", json=sample_vehicle_data)

        # Try to create another with same license plate
        response = await client.post("/api/v1/vehicles", json=sample_vehicle_data)
        assert response.status_code == 400
