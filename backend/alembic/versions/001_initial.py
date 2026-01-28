"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create agents table
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('start_latitude', sa.Numeric(9, 6), nullable=False),
        sa.Column('start_longitude', sa.Numeric(9, 6), nullable=False),
        sa.Column('end_latitude', sa.Numeric(9, 6), nullable=True),
        sa.Column('end_longitude', sa.Numeric(9, 6), nullable=True),
        sa.Column('work_start', sa.Time(), nullable=False, server_default='09:00:00'),
        sa.Column('work_end', sa.Time(), nullable=False, server_default='18:00:00'),
        sa.Column('max_visits_per_day', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
    )
    op.create_index('ix_agents_external_id', 'agents', ['external_id'])

    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.String(500), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('contact_person', sa.String(255), nullable=True),
        sa.Column('latitude', sa.Numeric(9, 6), nullable=False),
        sa.Column('longitude', sa.Numeric(9, 6), nullable=False),
        sa.Column('category', sa.Enum('A', 'B', 'C', name='clientcategory'), nullable=False, server_default='B'),
        sa.Column('visit_duration_minutes', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('time_window_start', sa.Time(), nullable=False, server_default='09:00:00'),
        sa.Column('time_window_end', sa.Time(), nullable=False, server_default='18:00:00'),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_clients_external_id', 'clients', ['external_id'])
    op.create_index('ix_clients_agent_id', 'clients', ['agent_id'])
    op.create_index('ix_clients_latitude', 'clients', ['latitude'])
    op.create_index('ix_clients_longitude', 'clients', ['longitude'])

    # Create vehicles table
    op.create_table(
        'vehicles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('license_plate', sa.String(20), nullable=False),
        sa.Column('capacity_kg', sa.Numeric(10, 2), nullable=False),
        sa.Column('capacity_volume_m3', sa.Numeric(10, 2), nullable=True),
        sa.Column('start_latitude', sa.Numeric(9, 6), nullable=False),
        sa.Column('start_longitude', sa.Numeric(9, 6), nullable=False),
        sa.Column('end_latitude', sa.Numeric(9, 6), nullable=True),
        sa.Column('end_longitude', sa.Numeric(9, 6), nullable=True),
        sa.Column('work_start', sa.Time(), nullable=False, server_default='08:00:00'),
        sa.Column('work_end', sa.Time(), nullable=False, server_default='20:00:00'),
        sa.Column('cost_per_km', sa.Numeric(10, 2), nullable=True, server_default='1.0'),
        sa.Column('fixed_cost', sa.Numeric(10, 2), nullable=True, server_default='0'),
        sa.Column('driver_name', sa.String(255), nullable=True),
        sa.Column('driver_phone', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('license_plate'),
    )

    # Create visit_plans table
    op.create_table(
        'visit_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('planned_date', sa.Date(), nullable=False),
        sa.Column('planned_time', sa.Time(), nullable=False),
        sa.Column('estimated_arrival_time', sa.Time(), nullable=True),
        sa.Column('estimated_departure_time', sa.Time(), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('distance_from_previous_km', sa.Float(), nullable=True),
        sa.Column('duration_from_previous_minutes', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('planned', 'in_progress', 'completed', 'skipped', 'cancelled', name='visitstatus'), nullable=False, server_default='planned'),
        sa.Column('actual_arrival_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_departure_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('skip_reason', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('agent_id', 'client_id', 'planned_date', name='uq_agent_client_date'),
    )
    op.create_index('ix_visit_plans_agent_id', 'visit_plans', ['agent_id'])
    op.create_index('ix_visit_plans_client_id', 'visit_plans', ['client_id'])
    op.create_index('ix_visit_plans_planned_date', 'visit_plans', ['planned_date'])

    # Create delivery_orders table
    op.create_table(
        'delivery_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('weight_kg', sa.Numeric(10, 2), nullable=False),
        sa.Column('volume_m3', sa.Numeric(10, 3), nullable=True),
        sa.Column('items_count', sa.Integer(), nullable=True),
        sa.Column('time_window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('service_time_minutes', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.Enum('pending', 'assigned', 'in_transit', 'delivered', 'failed', 'cancelled', name='orderstatus'), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('delivery_instructions', sa.Text(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_delivery_orders_external_id', 'delivery_orders', ['external_id'])
    op.create_index('ix_delivery_orders_client_id', 'delivery_orders', ['client_id'])
    op.create_index('ix_delivery_orders_status', 'delivery_orders', ['status'])

    # Create delivery_routes table
    op.create_table(
        'delivery_routes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('route_date', sa.Date(), nullable=False),
        sa.Column('total_distance_km', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('total_duration_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_weight_kg', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('total_stops', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('geometry', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'planned', 'in_progress', 'completed', 'cancelled', name='routestatus'), nullable=False, server_default='draft'),
        sa.Column('planned_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('planned_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_delivery_routes_vehicle_id', 'delivery_routes', ['vehicle_id'])
    op.create_index('ix_delivery_routes_route_date', 'delivery_routes', ['route_date'])

    # Create delivery_route_stops table
    op.create_table(
        'delivery_route_stops',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('route_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('distance_from_previous_km', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('duration_from_previous_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('planned_arrival', sa.DateTime(timezone=True), nullable=True),
        sa.Column('planned_departure', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_arrival', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_departure', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['route_id'], ['delivery_routes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['delivery_orders.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_delivery_route_stops_route_id', 'delivery_route_stops', ['route_id'])
    op.create_index('ix_delivery_route_stops_order_id', 'delivery_route_stops', ['order_id'])


def downgrade() -> None:
    op.drop_table('delivery_route_stops')
    op.drop_table('delivery_routes')
    op.drop_table('delivery_orders')
    op.drop_table('visit_plans')
    op.drop_table('vehicles')
    op.drop_table('clients')
    op.drop_table('agents')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS routestatus')
    op.execute('DROP TYPE IF EXISTS orderstatus')
    op.execute('DROP TYPE IF EXISTS visitstatus')
    op.execute('DROP TYPE IF EXISTS clientcategory')
