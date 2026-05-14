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

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    discord_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    onboarded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    reality_score: Mapped[float] = mapped_column(default=1.0)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

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
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    phase: Mapped[str] = mapped_column(default="opening")

    player: Mapped[Player] = relationship(back_populates="cases")
    phase_history: Mapped[list["CasePhaseHistory"]] = relationship(
        back_populates="case", order_by="CasePhaseHistory.transitioned_at"
    )


class CasePhaseHistory(Base):
    __tablename__ = "case_phase_history"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
    )
    from_phase: Mapped[str]
    to_phase: Mapped[str]
    reason: Mapped[str]
    transitioned_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    case: Mapped[Case] = relationship(back_populates="phase_history")


class PlayerNote(Base):
    __tablename__ = "player_notes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
    )
    text: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    fact_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    snapshot_value: Mapped[str | None] = mapped_column(Text, nullable=True)


class NPC(Base):
    __tablename__ = "npcs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
    )
    name: Mapped[str]
    description: Mapped[str | None]
    personality: Mapped[dict] = mapped_column(JSONB, default=dict)
    knowledge: Mapped[dict] = mapped_column(JSONB, default=dict)
    relationship_to_missing: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
    )
    description: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class FactLayer(Base):
    __tablename__ = "fact_layers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    fact_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facts.id", ondelete="CASCADE"),
    )
    layer_type: Mapped[str]  # 'truth' | 'perceived' | 'claimed' | 'evidence'
    value: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    modified_by: Mapped[str] = mapped_column(default="system")
    modified_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
    )
    timeline: Mapped[str]        # 'investigator' | 'shadow_a' | 'shadow_b'
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    wall_clock_slot: Mapped[str]  # shared key across timelines, e.g. "Day1-22:00"
    description: Mapped[str]
    visible_to_player: Mapped[bool] = mapped_column(default=False)
    revealed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    support_score: Mapped[float] = mapped_column(default=0.5)
    evidence_links: Mapped[list] = mapped_column(JSONB, default=list)
