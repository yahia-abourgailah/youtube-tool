"""initial_schema

Idempotent baseline for databases created before Alembic was wired in.
Existing installations already have these tables, so each create is skipped.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _table_names()

    if "channels" not in tables:
        op.create_table(
            "channels",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("url", sa.String(255), nullable=True),
            sa.Column("name", sa.String(255), nullable=True),
            sa.Column("status", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_channels_id"), "channels", ["id"], unique=False)
        op.create_index(op.f("ix_channels_url"), "channels", ["url"], unique=True)

    if "videos" not in tables:
        op.create_table(
            "videos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("video_id", sa.String(255), nullable=True),
            sa.Column("channel_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("duration", sa.Float(), nullable=True),
            sa.Column("upload_date", sa.String(50), nullable=True),
            sa.Column("status", sa.String(50), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_videos_id"), "videos", ["id"], unique=False)
        op.create_index(op.f("ix_videos_video_id"), "videos", ["video_id"], unique=True)

    if "audio_chunks" not in tables:
        op.create_table(
            "audio_chunks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("chunk_id", sa.String(255), nullable=True),
            sa.Column("video_id", sa.Integer(), nullable=True),
            sa.Column("file_path", sa.String(500), nullable=True),
            sa.Column("duration", sa.Float(), nullable=True),
            sa.Column("start_time", sa.Float(), nullable=True),
            sa.Column("end_time", sa.Float(), nullable=True),
            sa.Column("transcript_text", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_audio_chunks_id"), "audio_chunks", ["id"], unique=False)
        op.create_index(op.f("ix_audio_chunks_chunk_id"), "audio_chunks", ["chunk_id"], unique=True)

    if "jobs" not in tables:
        op.create_table(
            "jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("job_type", sa.String(50), nullable=True),
            sa.Column("entity_id", sa.String(255), nullable=True),
            sa.Column("celery_task_id", sa.String(255), nullable=True),
            sa.Column("status", sa.String(50), nullable=True),
            sa.Column("progress", sa.Float(), nullable=True),
            sa.Column("error_log_path", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_jobs_id"), "jobs", ["id"], unique=False)


def downgrade() -> None:
    tables = _table_names()
    if "jobs" in tables:
        op.drop_table("jobs")
    if "audio_chunks" in tables:
        op.drop_table("audio_chunks")
    if "videos" in tables:
        op.drop_table("videos")
    if "channels" in tables:
        op.drop_table("channels")
