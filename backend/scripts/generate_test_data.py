"""
Generate test data for Tashkent.

Creates:
- 10 agents
- 300 clients distributed across Tashkent
- 5 vehicles
- Sample delivery orders

Client distribution:
- Category A: 20% (60 clients)
- Category B: 50% (150 clients)
- Category C: 30% (90 clients)

Coordinates: Tashkent city bounds
- Latitude: 41.20 - 41.40
- Longitude: 69.10 - 69.40
"""
import asyncio
import random
from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Add parent directory to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import Base
from app.models.agent import Agent
from app.models.client import Client, ClientCategory
from app.models.vehicle import Vehicle
from app.models.delivery_order import DeliveryOrder

# Tashkent bounds
TASHKENT_LAT_MIN = 41.20
TASHKENT_LAT_MAX = 41.40
TASHKENT_LON_MIN = 69.10
TASHKENT_LON_MAX = 69.40

# Office location (Tashkent center)
OFFICE_LAT = 41.311081
OFFICE_LON = 69.279737

# Uzbek names for realistic data
FIRST_NAMES = [
    "Aziz", "Bekzod", "Dilshod", "Jasur", "Kamil", "Laziz", "Mirzo", "Nodir",
    "Olim", "Pulat", "Ravshan", "Sardor", "Timur", "Ulugbek", "Zafar",
    "Anvar", "Bobur", "Davron", "Eldor", "Farrukh", "Gulom", "Hamid",
    "Ikrom", "Jahongir", "Karim", "Lochin", "Mansur", "Nigmat", "Odil"
]

LAST_NAMES = [
    "Alimov", "Bahodirov", "Dadajonov", "Ergashev", "Fayzullayev",
    "Gafurov", "Hasanov", "Ibragimov", "Jurayev", "Karimov",
    "Latipov", "Mahmudov", "Nazarov", "Olimov", "Pulatov",
    "Rahimov", "Saidov", "Toshmatov", "Umarov", "Valiyev"
]

COMPANY_TYPES = [
    "Supermarket", "Mini Market", "Grocery", "Shop", "Store",
    "Trading", "Distribution", "Wholesale", "Retail", "Market"
]

COMPANY_NAMES = [
    "Korzinka", "Makro", "Havas", "Artel", "Ideal", "Grand", "Premium",
    "City", "Golden", "Star", "Diamond", "Pearl", "Royal", "Elite"
]

DISTRICTS = [
    "Chilanzar", "Yunusabad", "Mirzo Ulugbek", "Sergeli", "Bektemir",
    "Yakkasaray", "Shayxontohur", "Olmazor", "Mirabad", "Uchtepa"
]

STREETS = [
    "Amir Temur", "Mustaqillik", "Navoiy", "Uzbekistan", "Bunyodkor",
    "Beruniy", "Alisher Navoiy", "Bobur", "Mirzo Ulugbek", "Furqat"
]


def random_coordinates() -> tuple[Decimal, Decimal]:
    """Generate random coordinates within Tashkent."""
    lat = random.uniform(TASHKENT_LAT_MIN, TASHKENT_LAT_MAX)
    lon = random.uniform(TASHKENT_LON_MIN, TASHKENT_LON_MAX)
    return Decimal(str(round(lat, 6))), Decimal(str(round(lon, 6)))


def random_phone() -> str:
    """Generate random Uzbek phone number."""
    prefixes = ["90", "91", "93", "94", "95", "97", "98", "99"]
    return f"+998{random.choice(prefixes)}{random.randint(1000000, 9999999)}"


def random_time_window() -> tuple[time, time]:
    """Generate random business hours."""
    start_hour = random.choice([8, 9, 10])
    end_hour = random.choice([17, 18, 19, 20])
    return time(start_hour, 0), time(end_hour, 0)


def generate_agent_name() -> str:
    """Generate random agent name."""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def generate_company_name() -> str:
    """Generate random company name."""
    style = random.choice([
        lambda: f"{random.choice(COMPANY_NAMES)} {random.choice(COMPANY_TYPES)}",
        lambda: f"{random.choice(LAST_NAMES)} {random.choice(COMPANY_TYPES)}",
        lambda: f"{random.choice(COMPANY_TYPES)} {random.randint(1, 99)}",
    ])
    return style()


def generate_address() -> str:
    """Generate random Tashkent address."""
    district = random.choice(DISTRICTS)
    street = random.choice(STREETS)
    building = random.randint(1, 150)
    return f"{district} district, {street} street, {building}"


async def create_agents(session: AsyncSession, count: int = 10) -> list[Agent]:
    """Create test agents."""
    agents = []

    for i in range(count):
        # Slightly vary agent start locations around office
        lat_offset = random.uniform(-0.02, 0.02)
        lon_offset = random.uniform(-0.02, 0.02)

        agent = Agent(
            external_id=f"AGT-{i+1:04d}",
            name=generate_agent_name(),
            phone=random_phone(),
            email=f"agent{i+1}@company.uz",
            start_latitude=Decimal(str(round(OFFICE_LAT + lat_offset, 6))),
            start_longitude=Decimal(str(round(OFFICE_LON + lon_offset, 6))),
            work_start=time(9, 0),
            work_end=time(18, 0),
            max_visits_per_day=30,
            is_active=True,
        )
        session.add(agent)
        agents.append(agent)

    await session.flush()
    print(f"Created {len(agents)} agents")
    return agents


async def create_clients(
    session: AsyncSession,
    agents: list[Agent],
    count: int = 300,
) -> list[Client]:
    """
    Create test clients with specified category distribution.

    Distribution:
    - Category A: 20%
    - Category B: 50%
    - Category C: 30%
    """
    clients = []

    # Calculate counts
    count_a = int(count * 0.20)  # 60
    count_b = int(count * 0.50)  # 150
    count_c = count - count_a - count_b  # 90

    categories = (
        [ClientCategory.A] * count_a +
        [ClientCategory.B] * count_b +
        [ClientCategory.C] * count_c
    )
    random.shuffle(categories)

    # Distribute clients among agents (roughly 30 per agent)
    clients_per_agent = count // len(agents)

    for i in range(count):
        lat, lon = random_coordinates()
        start_time, end_time = random_time_window()

        # Assign to agent
        agent_idx = min(i // clients_per_agent, len(agents) - 1)
        agent = agents[agent_idx]

        client = Client(
            external_id=f"CLT-{i+1:05d}",
            name=generate_company_name(),
            address=generate_address(),
            phone=random_phone(),
            contact_person=generate_agent_name(),
            latitude=lat,
            longitude=lon,
            category=categories[i],
            visit_duration_minutes=random.choice([10, 15, 20, 25]),
            time_window_start=start_time,
            time_window_end=end_time,
            agent_id=agent.id,
            priority=random.randint(1, 5),
            is_active=True,
        )
        session.add(client)
        clients.append(client)

    await session.flush()

    # Print distribution
    a_count = len([c for c in clients if c.category == ClientCategory.A])
    b_count = len([c for c in clients if c.category == ClientCategory.B])
    c_count = len([c for c in clients if c.category == ClientCategory.C])
    print(f"Created {len(clients)} clients: A={a_count}, B={b_count}, C={c_count}")

    return clients


async def create_vehicles(session: AsyncSession, count: int = 5) -> list[Vehicle]:
    """Create test vehicles."""
    vehicles = []

    vehicle_types = [
        ("Isuzu NPR", 2000, 15),
        ("Hyundai HD", 3000, 20),
        ("Isuzu NQR", 4000, 25),
        ("Hino 300", 3500, 22),
        ("Fuso Canter", 2500, 18),
    ]

    for i in range(count):
        vtype = vehicle_types[i % len(vehicle_types)]

        vehicle = Vehicle(
            name=f"{vtype[0]} #{i+1}",
            license_plate=f"01{chr(65 + i)}{random.randint(100, 999)}AA",
            capacity_kg=Decimal(str(vtype[1])),
            capacity_volume_m3=Decimal(str(vtype[2])),
            start_latitude=Decimal(str(OFFICE_LAT)),
            start_longitude=Decimal(str(OFFICE_LON)),
            work_start=time(8, 0),
            work_end=time(20, 0),
            cost_per_km=Decimal("1.5"),
            driver_name=generate_agent_name(),
            driver_phone=random_phone(),
            is_active=True,
        )
        session.add(vehicle)
        vehicles.append(vehicle)

    await session.flush()
    print(f"Created {len(vehicles)} vehicles")
    return vehicles


async def create_delivery_orders(
    session: AsyncSession,
    clients: list[Client],
    count: int = 100,
) -> list[DeliveryOrder]:
    """Create sample delivery orders."""
    orders = []

    # Select random clients for delivery
    delivery_clients = random.sample(clients, min(count, len(clients)))

    tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    for i, client in enumerate(delivery_clients):
        # Random time window within client's hours
        start_hour = client.time_window_start.hour
        end_hour = client.time_window_end.hour

        window_start = tomorrow.replace(hour=start_hour)
        window_end = tomorrow.replace(hour=end_hour)

        order = DeliveryOrder(
            external_id=f"ORD-{tomorrow.strftime('%Y%m%d')}-{i+1:04d}",
            client_id=client.id,
            weight_kg=Decimal(str(random.randint(10, 500))),
            volume_m3=Decimal(str(round(random.uniform(0.1, 2.0), 2))),
            items_count=random.randint(1, 50),
            time_window_start=window_start,
            time_window_end=window_end,
            service_time_minutes=random.choice([5, 10, 15]),
            priority=random.randint(1, 5),
        )
        session.add(order)
        orders.append(order)

    await session.flush()
    print(f"Created {len(orders)} delivery orders for {tomorrow.date()}")
    return orders


async def main():
    """Generate all test data."""
    print("=" * 50)
    print("Generating test data for Tashkent")
    print("=" * 50)

    # Create engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    # Create tables if needed
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Generate data
            agents = await create_agents(session, count=10)
            clients = await create_clients(session, agents, count=300)
            vehicles = await create_vehicles(session, count=5)
            orders = await create_delivery_orders(session, clients, count=100)

            await session.commit()

            print("=" * 50)
            print("Test data generation complete!")
            print(f"  - Agents: {len(agents)}")
            print(f"  - Clients: {len(clients)}")
            print(f"  - Vehicles: {len(vehicles)}")
            print(f"  - Orders: {len(orders)}")
            print("=" * 50)

        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")
            raise

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
