"""Add users table for authentication

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user role enum
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'dispatcher', 'agent', 'driver')")

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('role', postgresql.ENUM('admin', 'dispatcher', 'agent', 'driver', name='userrole', create_type=False), nullable=False, server_default='agent'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Create default admin user (password: admin123)
    # In production, change this password immediately!
    op.execute("""
        INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_superuser)
        VALUES (
            gen_random_uuid(),
            'admin@example.com',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.OPJxRxJB.GCDXK',
            'System Administrator',
            'admin',
            true,
            true
        )
    """)


def downgrade() -> None:
    op.drop_table('users')
    op.execute('DROP TYPE IF EXISTS userrole')
