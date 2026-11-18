"""add_celery_task_id

Revision ID: 846c3bf42241
Revises: 0001_initial_schema
Create Date: 2025-12-24 22:08:20.525584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '846c3bf42241'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    # Idempotent: existing databases already have these columns.
    if 'celery_task_id' not in _columns('channels'):
        op.add_column('channels', sa.Column('celery_task_id', sa.String(255), nullable=True))
    if 'celery_task_id' not in _columns('videos'):
        op.add_column('videos', sa.Column('celery_task_id', sa.String(255), nullable=True))


def downgrade() -> None:
    if 'celery_task_id' in _columns('videos'):
        op.drop_column('videos', 'celery_task_id')
    if 'celery_task_id' in _columns('channels'):
        op.drop_column('channels', 'celery_task_id')
