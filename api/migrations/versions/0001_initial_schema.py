"""Initial schema: creations, creation_likes, user_usage, pgvector.

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Needed for embeddings in Phase 1 (RAG). Works on local Postgres and on Neon.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "creations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("publish", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('article', 'blog-title', 'image', 'resume-review')",
            name=op.f("ck_creations_valid_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creations")),
    )
    op.create_index(op.f("ix_creations_user_id"), "creations", ["user_id"])
    op.create_index(
        "ix_creations_published_feed",
        "creations",
        ["created_at"],
        postgresql_where=sa.text("publish"),
    )

    op.create_table(
        "creation_likes",
        sa.Column("creation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["creation_id"],
            ["creations.id"],
            name=op.f("fk_creation_likes_creation_id_creations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("creation_id", "user_id", name=op.f("pk_creation_likes")),
    )

    op.create_table(
        "user_usage",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("free_usage", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("free_usage >= 0", name=op.f("ck_user_usage_free_usage_not_negative")),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_usage")),
    )


def downgrade() -> None:
    op.drop_table("user_usage")
    op.drop_table("creation_likes")
    op.drop_index("ix_creations_published_feed", table_name="creations")
    op.drop_index(op.f("ix_creations_user_id"), table_name="creations")
    op.drop_table("creations")
    # The vector extension is left installed: other database objects may use it.
