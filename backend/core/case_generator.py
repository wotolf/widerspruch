"""
Case Generator — erzeugt einen personalisierten Vermissten-Fall.

Nimmt das Player-Profile als Input und gibt eine Akten-Struktur zurück:
- Vermisster (mit Profil, das deckend genug auf den Spieler passt)
- Initial-Spuren (3-5 Leads)
- NPCs (3-7 Personen mit Beziehung zum Vermissten)
- Tatorte (2-3 Locations)
- Zeitlinie

Implementation kommt mit Phase 1 (basisch) und wird in Phase 4 erweitert
um die Shadow-Timeline.
"""
from __future__ import annotations

from dataclasses import dataclass

import structlog

from backend.core.llm import LLMClient

log = structlog.get_logger()


@dataclass
class GeneratedCase:
    title: str
    missing_person: dict
    initial_leads: list[dict]
    npcs: list[dict]
    locations: list[dict]
    timeline: list[dict]


class CaseGenerator:
    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    def generate(self, player_profile: dict) -> GeneratedCase:
        """
        Generiert einen Fall basierend auf dem Spieler-Profil.
        
        Phase 1: Single LLM-Call der ein JSON returnt.
        Phase 4: Multi-Step-Pipeline mit eigenen Calls für Shadow-Timeline.
        """
        raise NotImplementedError("Phase 1")
