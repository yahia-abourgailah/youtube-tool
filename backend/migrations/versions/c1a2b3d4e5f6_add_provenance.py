"""add provenance metadata and channel speaker

Revision ID: c1a2b3d4e5f6
Revises: a35c4537468e
Create Date: 2026-11-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "a35c4537468e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    channel_columns = _columns("channels")
    if "speaker" not in channel_columns:
        op.add_column("channels", sa.Column("speaker", sa.String(255), nullable=True))

    chunk_columns = _columns("audio_chunks")
    additions = [
        ("asr_model", sa.String(100)),
        ("asr_version", sa.String(100)),
        ("confidence", sa.Float()),
        ("language", sa.String(20)),
    ]
    for name, column_type in additions:
        if name not in chunk_columns:
            op.add_column("audio_chunks", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    chunk_columns = _columns("audio_chunks")
    for name in ("language", "confidence", "asr_version", "asr_model"):
        if name in chunk_columns:
            op.drop_column("audio_chunks", name)

    if "speaker" in _columns("channels"):
        op.drop_column("channels", "speaker")
