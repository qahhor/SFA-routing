"""Add performance indexes

Revision ID: 004
Revises: 003_add_api_clients
Create Date: 2024-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = '004'
down_revision: Union[str, None] = '003_add_api_clients'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # CLIENTS INDEXES
    # ============================================================

    # Compound index for common query pattern: active clients by agent
    op.create_index(
        'ix_clients_agent_active',
        'clients',
        ['agent_id', 'is_active'],
        postgresql_where='is_active = true'
    )

    # Index for category filtering (frequently used in planning)
    op.create_index(
        'ix_clients_category',
        'clients',
        ['category']
    )

    # Compound index for geographic queries
    op.create_index(
        'ix_clients_geo',
        'clients',
        ['latitude', 'longitude']
    )

    # Index for priority-based queries
    op.create_index(
        'ix_clients_priority',
        'clients',
        ['priority'],
        postgresql_where='is_active = true'
    )

    # ============================================================
    # VISIT_PLANS INDEXES
    # ============================================================

    # Compound index for common query: agent's visits on a date
    op.create_index(
        'ix_visit_plans_agent_date_status',
        'visit_plans',
        ['agent_id', 'planned_date', 'status']
    )

    # Index for sequence ordering
    op.create_index(
        'ix_visit_plans_sequence',
        'visit_plans',
        ['agent_id', 'planned_date', 'sequence_number']
    )

    # ============================================================
    # DELIVERY_ORDERS INDEXES
    # ============================================================

    # Compound index for pending orders by client
    op.create_index(
        'ix_delivery_orders_client_status',
        'delivery_orders',
        ['client_id', 'status']
    )

    # Index for time window queries
    op.create_index(
        'ix_delivery_orders_time_window',
        'delivery_orders',
        ['time_window_start', 'time_window_end']
    )

    # Index for priority filtering
    op.create_index(
        'ix_delivery_orders_priority',
        'delivery_orders',
        ['priority'],
        postgresql_where="status = 'pending'"
    )

    # ============================================================
    # DELIVERY_ROUTES INDEXES
    # ============================================================

    # Compound index for vehicle routes on a date
    op.create_index(
        'ix_delivery_routes_vehicle_date_status',
        'delivery_routes',
        ['vehicle_id', 'route_date', 'status']
    )

    # ============================================================
    # DELIVERY_ROUTE_STOPS INDEXES
    # ============================================================

    # Compound index for route stops ordering
    op.create_index(
        'ix_delivery_route_stops_route_sequence',
        'delivery_route_stops',
        ['route_id', 'sequence_number']
    )

    # ============================================================
    # AGENTS INDEXES
    # ============================================================

    # Index for active agents
    op.create_index(
        'ix_agents_is_active',
        'agents',
        ['is_active'],
        postgresql_where='is_active = true'
    )

    # ============================================================
    # VEHICLES INDEXES
    # ============================================================

    # Index for active vehicles
    op.create_index(
        'ix_vehicles_is_active',
        'vehicles',
        ['is_active'],
        postgresql_where='is_active = true'
    )

    # ============================================================
    # USERS INDEXES
    # ============================================================

    # Index for active users by role
    op.create_index(
        'ix_users_role_active',
        'users',
        ['role', 'is_active'],
        postgresql_where='is_active = true'
    )


def downgrade() -> None:
    # Users indexes
    op.drop_index('ix_users_role_active', table_name='users')

    # Vehicles indexes
    op.drop_index('ix_vehicles_is_active', table_name='vehicles')

    # Agents indexes
    op.drop_index('ix_agents_is_active', table_name='agents')

    # Delivery route stops indexes
    op.drop_index('ix_delivery_route_stops_route_sequence', table_name='delivery_route_stops')

    # Delivery routes indexes
    op.drop_index('ix_delivery_routes_vehicle_date_status', table_name='delivery_routes')

    # Delivery orders indexes
    op.drop_index('ix_delivery_orders_priority', table_name='delivery_orders')
    op.drop_index('ix_delivery_orders_time_window', table_name='delivery_orders')
    op.drop_index('ix_delivery_orders_client_status', table_name='delivery_orders')

    # Visit plans indexes
    op.drop_index('ix_visit_plans_sequence', table_name='visit_plans')
    op.drop_index('ix_visit_plans_agent_date_status', table_name='visit_plans')

    # Clients indexes
    op.drop_index('ix_clients_priority', table_name='clients')
    op.drop_index('ix_clients_geo', table_name='clients')
    op.drop_index('ix_clients_category', table_name='clients')
    op.drop_index('ix_clients_agent_active', table_name='clients')
