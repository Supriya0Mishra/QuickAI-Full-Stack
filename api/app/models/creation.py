from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CreationType(StrEnum):
    ARTICLE = "article"
    BLOG_TITLE = "blog-title"
    IMAGE = "image"
    RESUME_REVIEW = "resume-review"


CREATION_TYPES = tuple(t.value for t in CreationType)


class Creation(Base):
    """Something a user generated: an article, titles, an image or a resume review."""

    __tablename__ = "creations"
    __table_args__ = (
        CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in CREATION_TYPES) + ")",
            name="valid_type",
        ),
        # The community feed only reads published creations, newest first.
        Index(
            "ix_creations_published_feed",
            "created_at",
            postgresql_where=text("publish"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(32))
    publish: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    likes: Mapped[list["CreationLike"]] = relationship(
        back_populates="creation", cascade="all, delete-orphan", passive_deletes=True
    )


class CreationLike(Base):
    """One user liking one creation.

    Replaces the old `likes TEXT[]` column: a user can only like a creation once
    (primary key), and likes are removed with their creation (ON DELETE CASCADE).
    """

    __tablename__ = "creation_likes"

    creation_id: Mapped[int] = mapped_column(
        ForeignKey("creations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creation: Mapped[Creation] = relationship(back_populates="likes")
