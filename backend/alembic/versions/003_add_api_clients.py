"""Add API clients table for multi-tenant authentication.

Revision ID: 003_add_api_clients
Revises: 002_add_users
Create Date: 2026-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_api_clients'
down_revision: Union[str, None] = '002_add_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create api_clients table."""
    op.create_table(
        'api_clients',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('api_key_hash', sa.String(length=64), nullable=False),
        sa.Column('api_key_prefix', sa.String(length=8), nullable=False),
        sa.Column('tier', sa.String(length=20), server_default='free', nullable=False),
        sa.Column('rate_limit_per_minute', sa.Integer(), server_default='10', nullable=False),
        sa.Column('max_points_per_request', sa.Integer(), server_default='50', nullable=False),
        sa.Column('monthly_quota', sa.Integer(), server_default='1000', nullable=False),
        sa.Column('requests_this_month', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_request_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('quota_reset_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('allowed_regions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('allowed_endpoints', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_whitelist', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('webhook_url', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create index on api_key_hash for fast lookup
    op.create_index(
        'ix_api_clients_api_key_hash',
        'api_clients',
        ['api_key_hash'],
        unique=True,
    )
    
    # Create index on is_active for filtering
    op.create_index(
        'ix_api_clients_is_active',
        'api_clients',
        ['is_active'],
    )
    
    # Create index on tier for filtering
    op.create_index(
        'ix_api_clients_tier',
        'api_clients',
        ['tier'],
    )


def downgrade() -> None:
    """Drop api_clients table."""
    op.drop_index('ix_api_clients_tier', table_name='api_clients')
    op.drop_index('ix_api_clients_is_active', table_name='api_clients')
    op.drop_index('ix_api_clients_api_key_hash', table_name='api_clients')
    op.drop_table('api_clients')
