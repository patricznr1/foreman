# ============================================================
#  FOREMAN — db/base.py
#  Zweck: Gemeinsame DeclarativeBase + Timestamp-Mixin für alle ORM-Modelle.
#  Architektur-Einordnung: Persistenz-Schicht (Schicht 2). Einzige Mapper-Wurzel,
#         auf die Alembic-Autogenerate und der Metadata-Export zugreifen.
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Wurzel-Basisklasse aller FOREMAN-ORM-Modelle."""


class TimestampMixin:
    """Stellt eine einheitliche, server-seitig gesetzte `created_at`-Spalte bereit."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
