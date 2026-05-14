"""
Timeline Seeder — generiert drei parallele Ereignis-Timelines für einen Fall.

investigator / shadow_a / shadow_b decken dieselben Wandzeit-Slots ab
und werden vollständig mit visible_to_player=False persistiert.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.json_utils import parse_llm_json
from backend.core.llm import LLMClient
from backend.db.models import Case, TimelineEvent

log = structlog.get_logger()

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "timeline_seeding.md"
_HAIKU = "claude-haiku-4-5-20251001"
_TIMELINES = ("investigator", "shadow_a", "shadow_b")


class TimelineSeederError(Exception):
    pass


@dataclass
class SeedResult:
    investigator_count: int
    shadow_a_count: int
    shadow_b_count: int


def _parse_json(text: str) -> dict:
    return parse_llm_json(text, TimelineSeederError)


def _validate(timelines: dict[str, list[dict]]) -> None:
    missing = set(_TIMELINES) - set(timelines.keys())
    if missing:
        raise TimelineSeederError(f"Fehlende Timelines: {missing}")

    slot_sets: dict[str, set[str]] = {}
    for name in _TIMELINES:
        events = timelines[name]
        if len(events) < 8:
            raise TimelineSeederError(
                f"Timeline '{name}' hat {len(events)} Events — mindestens 8 erwartet"
            )
        slots = [e.get("wall_clock_slot", "") for e in events]
        if len(slots) != len(set(slots)):
            raise TimelineSeederError(f"Timeline '{name}' enthält doppelte wall_clock_slots")
        for e in events:
            desc = e.get("description", "")
            if len(desc) < 20:
                raise TimelineSeederError(
                    f"Beschreibung zu kurz in '{name}': {desc!r}"
                )
        slot_sets[name] = set(slots)

    ref = slot_sets["investigator"]
    for name, slots in slot_sets.items():
        if slots != ref:
            diff = ref.symmetric_difference(slots)
            raise TimelineSeederError(
                f"Timeline '{name}' hat andere Zeitslots als 'investigator': {diff}"
            )


class TimelineSeeder:
    def __init__(self, db_session: AsyncSession, llm: LLMClient | None = None):
        self.db = db_session
        self.llm = llm or LLMClient(model=_HAIKU)
        self._prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def seed_case(self, case_id: UUID, profile) -> SeedResult:
        """
        Generiert und persistiert drei Timelines für den angegebenen Fall.

        Args:
            case_id: UUID des Falls
            profile:  PlayerProfile-Instanz mit city, routine etc.

        Returns:
            SeedResult mit Event-Counts pro Timeline
        """
        case = await self.db.scalar(select(Case).where(Case.id == case_id))
        if case is None:
            raise TimelineSeederError(f"Fall {case_id} nicht gefunden")

        user_input = json.dumps({
            "case_title": case.title,
            "disappearance_date": case.started_at.strftime("%Y-%m-%d"),
            "city": profile.city or "Unbekannt",
            "missing_person_brief": f"Fall: {case.title}",
            "investigator_profile": f"Stadt: {profile.city}, Routine: {profile.routine or '–'}",
        }, ensure_ascii=False, indent=2)

        log.info("timeline_seeder_start", case_id=str(case_id))

        response = await asyncio.to_thread(
            self.llm.complete,
            system=self._prompt,
            user=user_input,
            max_tokens=8000,
            temperature=0.85,
        )

        log.info(
            "timeline_seeder_llm_done",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        raw = _parse_json(response.text)
        timelines: dict[str, list[dict]] = {k: raw.get(k, []) for k in _TIMELINES}
        _validate(timelines)

        now = datetime.now(timezone.utc)
        counts: dict[str, int] = {}

        for timeline_name in _TIMELINES:
            events = timelines[timeline_name]
            for ev in events:
                occurred_at_raw = ev.get("occurred_at", "")
                try:
                    occurred_at = datetime.fromisoformat(occurred_at_raw)
                    if occurred_at.tzinfo is None:
                        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    occurred_at = now

                self.db.add(TimelineEvent(
                    id=uuid4(),
                    case_id=case_id,
                    timeline=timeline_name,
                    occurred_at=occurred_at,
                    wall_clock_slot=ev["wall_clock_slot"],
                    description=ev["description"],
                    visible_to_player=False,
                    support_score=0.5,
                    evidence_links=[],
                ))
            counts[timeline_name] = len(events)

        await self.db.flush()

        log.info(
            "timeline_seeder_done",
            case_id=str(case_id),
            counts=counts,
        )

        return SeedResult(
            investigator_count=counts["investigator"],
            shadow_a_count=counts["shadow_a"],
            shadow_b_count=counts["shadow_b"],
        )
