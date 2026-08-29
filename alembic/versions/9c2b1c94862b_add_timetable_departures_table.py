"""Add timetable_departures table

Revision ID: 9c2b1c94862b
Revises: 2cf9ab210dbd
Create Date: 2026-08-29 23:59:23.983420

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c2b1c94862b'
down_revision: Union[str, Sequence[str], None] = '2cf9ab210dbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('timetable_departures',
    sa.Column('departure_id', sa.String(), nullable=False),
    sa.Column('origin', sa.String(), nullable=False),
    sa.Column('destination', sa.String(), nullable=False),
    sa.Column('departure_time', sa.String(), nullable=False),
    sa.Column('data_source', sa.Enum('OFFICIAL', 'OPERATOR', 'VERIFIED_LOCAL', 'SIMULATION', 'DEMO', 'EXTERNAL_PROVIDER', 'MANUAL', name='datasource'), nullable=False),
    sa.Column('source_doc', sa.String(), nullable=True),
    sa.Column('source_name', sa.String(), nullable=True),
    sa.Column('valid_from', sa.DateTime(), nullable=True),
    sa.Column('valid_until', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('departure_id')
    )
    op.create_index(op.f('ix_timetable_departures_destination'), 'timetable_departures', ['destination'], unique=False)
    op.create_index(op.f('ix_timetable_departures_origin'), 'timetable_departures', ['origin'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_timetable_departures_destination'), table_name='timetable_departures')
    op.drop_index(op.f('ix_timetable_departures_origin'), table_name='timetable_departures')
    op.drop_table('timetable_departures')
