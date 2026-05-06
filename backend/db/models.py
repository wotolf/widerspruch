"""
SQLAlchemy ORM Models — gespiegelt zum Schema in backend/db/schema.sql.

Phase 1: Player, PlayerProfile, Case
Phase 2: Fact, FactLayer, NPC, NPCMemory
Phase 3: ScheduledThreat
Phase 4: TimelineEvent
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    discord_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    onboarded_at: Mapped[datetime | None]
    reality_score: Mapped[float] = mapped_column(default=1.0)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime]

    profile: Mapped["PlayerProfile"] = relationship(back_populates="player", uselist=False)
    cases: Mapped[list["Case"]] = relationship(back_populates="player")

    __table_args__ = (
        CheckConstraint("reality_score >= 0 AND reality_score <= 1"),
    )


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    player_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    city: Mapped[str | None]
    neighborhood: Mapped[str | None]
    routine: Mapped[str | None]
    close_people: Mapped[list] = mapped_column(JSONB, default=list)
    fears: Mapped[list] = mapped_column(JSONB, default=list)
    locations: Mapped[list] = mapped_column(JSONB, default=list)
    raw_answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    personalization_intensity: Mapped[str] = mapped_column(default="medium")

    player: Mapped[Player] = relationship(back_populates="profile")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    player_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
    )
    title: Mapped[str]
    started_at: Mapped[datetime]
    phase: Mapped[str] = mapped_column(default="opening")

    player: Mapped[Player] = relationship(back_populates="cases")


# TODO Phase 2: Fact, FactLayer, NPC, NPCMemory
# TODO Phase 3: ScheduledThreat
# TODO Phase 4: TimelineEvent
