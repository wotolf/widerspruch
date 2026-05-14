"""
Case Generator — erzeugt einen personalisierten Vermissten-Fall.

Nimmt das Player-Profile als Input, ruft das LLM auf und persistiert:
- cases: Akten-Titel und Phase
- npcs: Zeugen und Beteiligte
- facts: Spuren, Vermissteninfo und Umstände als abstrakte Fakten

Die Truth Engine (Phase 2) fügt später die Schicht-Versionen (truth /
perceived / claimed / evidence) zu diesen Facts hinzu.
"""
from __future__ import annotations

import ast
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.json_utils import parse_llm_json
from backend.core.llm import LLMClient
from backend.core.truth_engine import TruthEngine
from backend.db.models import Case, NPC

log = structlog.get_logger()

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "case_generation.md"

_REQUIRED_KEYS = {"title", "missing_person", "initial_leads", "npcs"}


class CaseGenerationError(Exception):
    """LLM-Response war kein valides JSON oder fehlte Pflichtfelder."""


@dataclass
class GeneratedCase:
    title: str
    missing_person: dict
    disappearance_circumstances: str
    initial_leads: list[dict]
    npcs: list[dict]
    locations: list[dict]
    timeline: list[dict]


def _parse_json_response(text: str) -> dict:
    return parse_llm_json(text, CaseGenerationError)


def _validate(data: dict) -> None:
    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise CaseGenerationError(f"LLM-Response fehlt Pflichtfelder: {missing}")
    if not data["initial_leads"]:
        raise CaseGenerationError("initial_leads ist leer")
    if not data["npcs"]:
        raise CaseGenerationError("npcs ist leer")


def _build_fact_descriptions(data: dict) -> list[str]:
    """Wandelt generierten Case-JSON in lesbare Fact-Beschreibungen um."""
    descs: list[str] = []

    mp = data.get("missing_person", {})
    if mp:
        # Kompakte Darstellung statt rohem JSON-Dump
        parts = [f"{k}: {v}" for k, v in mp.items() if v]
        descs.append("Vermissteninfo — " + " | ".join(parts))

    dc = data.get("disappearance_circumstances", "")
    if dc:
        if isinstance(dc, dict):
            dc_str = "\n".join(f"{k}: {v}" for k, v in dc.items() if v)
            descs.append(f"Verschwinden:\n{dc_str}")
        elif isinstance(dc, str) and dc.startswith("{"):
            try:
                parsed = ast.literal_eval(dc)
                if isinstance(parsed, dict):
                    dc_str = "\n".join(f"{k}: {v}" for k, v in parsed.items() if v)
                    descs.append(f"Verschwinden:\n{dc_str}")
                else:
                    descs.append(f"Verschwinden: {dc}")
            except (ValueError, SyntaxError):
                descs.append(f"Verschwinden: {dc}")
        else:
            descs.append(f"Verschwinden: {dc}")

    for lead in data.get("initial_leads", []):
        headline = lead.get("headline", "Unbekannte Spur")
        details = lead.get("details", "")
        descs.append(f"{headline}: {details}" if details else headline)

    for loc in data.get("locations", []):
        if isinstance(loc, dict):
            name = loc.get("name") or loc.get("location") or str(loc)
            descs.append(f"Tatort: {name}")
        else:
            descs.append(f"Tatort: {loc}")

    return descs


class CaseGenerator:
    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()
        self._prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def generate(
        self,
        player_id: UUID,
        player_profile: dict,
        session: AsyncSession,
    ) -> GeneratedCase:
        """
        Generiert einen personalisierten Fall und persistiert ihn in der DB.

        Args:
            player_id:      UUID des Spielers (für cases.player_id FK)
            player_profile: Onboarding-Daten (city, routine, fears, ...)
            session:        Aktive AsyncSession — Commit übernimmt der Aufrufer

        Returns:
            GeneratedCase mit allen generierten Feldern

        Raises:
            CaseGenerationError: LLM-Response ungültig oder fehlende Pflichtfelder
        """
        log.info("case_generation_start", player_id=str(player_id))

        # LLM-Call in Thread — Anthropic SDK ist synchron, würde sonst blockieren
        response = await asyncio.to_thread(
            self.llm.complete,
            system=self._prompt,
            user=json.dumps(player_profile, ensure_ascii=False, indent=2),
            max_tokens=4096,   # <-- war 2048, zu wenig für vollständiges Case-JSON
            temperature=0.9,
        )

        log.info(
            "case_generation_llm_done",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        data = _parse_json_response(response.text)
        _validate(data)

        now = datetime.now(timezone.utc)

        # --- Case ---
        case = Case(
            id=uuid4(),
            player_id=player_id,
            title=data["title"],
            started_at=now,
            phase="opening",
        )
        session.add(case)
        await session.flush()  # case.id für FK-Referenzen verfügbar machen

        # --- NPCs ---
        for npc_data in data["npcs"]:
            session.add(NPC(
                id=uuid4(),
                case_id=case.id,
                name=npc_data.get("name", "Unbekannt"),
                description=npc_data.get("personality_brief"),
                personality={"brief": npc_data.get("personality_brief", "")},
                knowledge={},
                relationship_to_missing=npc_data.get("relationship"),
                created_at=now,
            ))

        # --- Facts + Layer (truth + perceived) ---
        truth_engine = TruthEngine(db_session=session, llm=self.llm)
        descs = _build_fact_descriptions(data)
        for desc in descs:
            fact = await truth_engine.record_truth(case_id=case.id, description=desc, value=desc)
            await truth_engine.record_perception(fact_id=fact.id, value=desc, source="system")

        log.info(
            "case_generation_persisted",
            case_id=str(case.id),
            title=data["title"],
            npc_count=len(data["npcs"]),
            fact_count=len(descs),
        )

        return GeneratedCase(
            title=data["title"],
            missing_person=data.get("missing_person", {}),
            disappearance_circumstances=data.get("disappearance_circumstances", ""),
            initial_leads=data.get("initial_leads", []),
            npcs=data.get("npcs", []),
            locations=data.get("locations", []),
            timeline=data.get("timeline", []),
        )
