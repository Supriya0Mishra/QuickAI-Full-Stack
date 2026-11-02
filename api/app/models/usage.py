from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserUsage(Base):
    """Free-plan usage per user.

    Replaces the counter stored in Clerk metadata. Keeping it in Postgres lets
    the limit be checked and increased in one atomic UPDATE (done in PR 5), which
    fixes the race where two requests at once could both pass the limit.
    """

    __tablename__ = "user_usage"
    __table_args__ = (CheckConstraint("free_usage >= 0", name="free_usage_not_negative"),)

    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    free_usage: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
