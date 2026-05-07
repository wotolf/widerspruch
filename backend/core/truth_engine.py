"""
Truth Engine — das Herz von Widerspruch.

Speichert Facts in vier Layer-Versionen (truth, perceived, claimed, evidence)
und erlaubt subtile Drift bei niedrigem Reality-Score.
"""
from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.llm import LLMClient
from backend.core.reality import corruption_intensity
from backend.db.models import Case, Fact, FactLayer, Player

log = structlog.get_logger()

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


class LayerType(str, Enum):
    TRUTH = "truth"
    PERCEIVED = "perceived"
    CLAIMED = "claimed"
    EVIDENCE = "evidence"


@dataclass
class ChangeRecord:
    fact_id: UUID
    layer_type: LayerType
    old_value: str
    new_value: str
    reason: str


class TruthEngine:
    def __init__(self, db_session: AsyncSession, llm: LLMClient | None = None):
        self.db = db_session
        self.llm = llm or LLMClient()
        self._corruption_prompt = (_PROMPT_DIR / "corruption_layer.md").read_text("utf-8")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    async def record_truth(self, case_id: UUID, description: str, value: str) -> Fact:
        """Erzeugt einen neuen Fact mit truth-Layer."""
        now = datetime.now(timezone.utc)
        fact = Fact(id=uuid4(), case_id=case_id, description=description, created_at=now)
        self.db.add(fact)
        await self.db.flush()
        self.db.add(FactLayer(
            id=uuid4(), fact_id=fact.id, layer_type="truth",
            value=value, version=1, modified_by="system", modified_at=now,
        ))
        return fact

    async def record_perception(self, fact_id: UUID, value: str, source: str) -> FactLayer:
        """Speichert was der Spieler wahrnimmt."""
        now = datetime.now(timezone.utc)
        max_v = await self.db.scalar(
            select(func.max(FactLayer.version))
            .where(FactLayer.fact_id == fact_id, FactLayer.layer_type == "perceived")
        )
        layer = FactLayer(
            id=uuid4(), fact_id=fact_id, layer_type="perceived",
            value=value, version=(max_v or 0) + 1, modified_by=source, modified_at=now,
        )
        self.db.add(layer)
        return layer

    async def record_claim(self, fact_id: UUID, value: str, npc_name: str) -> FactLayer:
        """Speichert was ein NPC behauptet."""
        now = datetime.now(timezone.utc)
        max_v = await self.db.scalar(
            select(func.max(FactLayer.version))
            .where(FactLayer.fact_id == fact_id, FactLayer.layer_type == "claimed")
        )
        layer = FactLayer(
            id=uuid4(), fact_id=fact_id, layer_type="claimed",
            value=value, version=(max_v or 0) + 1,
            modified_by=f"npc:{npc_name}", modified_at=now,
        )
        self.db.add(layer)
        return layer

    async def record_evidence(self, fact_id: UUID, value: str, evidence_type: str) -> FactLayer:
        """Speichert was ein Beweis zeigt."""
        now = datetime.now(timezone.utc)
        max_v = await self.db.scalar(
            select(func.max(FactLayer.version))
            .where(FactLayer.fact_id == fact_id, FactLayer.layer_type == "evidence")
        )
        layer = FactLayer(
            id=uuid4(), fact_id=fact_id, layer_type="evidence",
            value=value, version=(max_v or 0) + 1,
            modified_by=f"evidence:{evidence_type}", modified_at=now,
        )
        self.db.add(layer)
        return layer

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    async def get_player_visible_layers(self, fact_id: UUID) -> dict[str, str]:
        """Gibt alle Layer außer truth zurück, neueste Version gewinnt."""
        rows = list(await self.db.scalars(
            select(FactLayer)
            .where(FactLayer.fact_id == fact_id, FactLayer.layer_type != "truth")
            .order_by(FactLayer.layer_type, FactLayer.version.desc())
        ))
        result: dict[str, str] = {}
        for row in rows:
            if row.layer_type not in result:
                result[row.layer_type] = row.value
        return result

    def get_fact(self, fact_id: UUID) -> Any:
        raise NotImplementedError

    def diff_layers(self, fact_id: UUID) -> dict[str, Any]:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Drift
    # ------------------------------------------------------------------

    async def adjust_reality_score(self, player_id: UUID, delta: float) -> float:
        """Passt Reality-Score um delta an (negativ = sinkt). Gibt neuen Wert zurück."""
        player = await self.db.scalar(select(Player).where(Player.id == player_id))
        new_score = max(0.0, min(1.0, player.reality_score + delta))
        player.reality_score = new_score
        return new_score

    async def apply_corruption(self, player_id: UUID, intensity: float) -> list[ChangeRecord]:
        """Korrumpiert subtil einen perceived/claimed Layer. intensity=0 → kein Effekt."""
        if intensity <= 0.0:
            return []

        case = await self.db.scalar(
            select(Case)
            .where(Case.player_id == player_id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if case is None:
            return []

        recent_facts = list(await self.db.scalars(
            select(Fact).where(Fact.case_id == case.id)
            .order_by(Fact.created_at.desc()).limit(5)
        ))
        if not recent_facts:
            return []

        target_layer: FactLayer | None = None
        for fact in random.sample(recent_facts, min(len(recent_facts), 3)):
            layer = await self.db.scalar(
                select(FactLayer)
                .where(
                    FactLayer.fact_id == fact.id,
                    FactLayer.layer_type.in_(["perceived", "claimed"]),
                )
                .order_by(FactLayer.version.desc())
            )
            if layer:
                target_layer = layer
                break

        if target_layer is None:
            return []

        user_input = json.dumps({
            "original": target_layer.value,
            "intensity": intensity,
            "constraint": "verändere nur ein Detail — eine Zeitangabe, ein Adjektiv, oder eine Zahl",
        }, ensure_ascii=False)

        response = await asyncio.to_thread(
            self.llm.complete,
            system=self._corruption_prompt,
            user=user_input,
            max_tokens=512,
            temperature=0.7,
        )
        new_value = response.text.strip()
        now = datetime.now(timezone.utc)

        self.db.add(FactLayer(
            id=uuid4(),
            fact_id=target_layer.fact_id,
            layer_type=target_layer.layer_type,
            value=new_value,
            version=target_layer.version + 1,
            modified_by="llm-corruption",
            modified_at=now,
        ))

        log.info("corruption_applied", fact_id=str(target_layer.fact_id),
                 layer=target_layer.layer_type, intensity=intensity)

        return [ChangeRecord(
            fact_id=target_layer.fact_id,
            layer_type=LayerType(target_layer.layer_type),
            old_value=target_layer.value,
            new_value=new_value,
            reason=f"corruption (intensity={intensity:.2f})",
        )]
