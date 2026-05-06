"""
Truth Engine — das Herz von Widerspruch.

Speichert Facts in vier Layer-Versionen (truth, perceived, claimed, evidence)
und erlaubt subtile Drift bei niedrigem Reality-Score.

Dieses Modul ist intentional ausführlich kommentiert — die Komplexität liegt
in der konzeptionellen Sauberkeit, nicht in den Zeilen Code.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

import structlog

log = structlog.get_logger()


class LayerType(str, Enum):
    TRUTH = "truth"           # Was wirklich passiert ist (system only)
    PERCEIVED = "perceived"   # Was der Spieler wahrnimmt
    CLAIMED = "claimed"       # Was NPCs aussagen
    EVIDENCE = "evidence"     # Was Beweise zeigen


@dataclass
class Fact:
    id: UUID
    case_id: UUID
    description: str


@dataclass
class FactLayer:
    fact_id: UUID
    layer_type: LayerType
    value: str
    version: int
    modified_by: str


@dataclass
class ChangeRecord:
    fact_id: UUID
    layer_type: LayerType
    old_value: str
    new_value: str
    reason: str


class TruthEngine:
    """
    Zentrale API für alle Wahrheits-Operationen.
    
    Implementation kommt mit Phase 2 — hier nur Skelett.
    """

    def __init__(self, db_session: Any):
        # db_session wird typed sobald wir SQLAlchemy ORM Models haben
        self.db = db_session

    # ------------------------------------------------------------------
    # Recording (Schreiben in Layer)
    # ------------------------------------------------------------------

    def record_truth(self, case_id: UUID, description: str, value: str) -> Fact:
        """Erzeugt einen neuen Fact mit truth-Layer."""
        raise NotImplementedError("Phase 2")

    def record_perception(self, fact_id: UUID, value: str, source: str) -> FactLayer:
        """Speichert was der Spieler wahrnimmt (z.B. nach Akten-Lese-Aktion)."""
        raise NotImplementedError("Phase 2")

    def record_claim(self, fact_id: UUID, value: str, npc_name: str) -> FactLayer:
        """Speichert was ein NPC behauptet."""
        raise NotImplementedError("Phase 2")

    def record_evidence(
        self, fact_id: UUID, value: str, evidence_type: str
    ) -> FactLayer:
        """Speichert was ein Beweis zeigt."""
        raise NotImplementedError("Phase 2")

    # ------------------------------------------------------------------
    # Reading (was sieht der Spieler)
    # ------------------------------------------------------------------

    def get_fact(self, fact_id: UUID) -> Fact:
        raise NotImplementedError("Phase 2")

    def get_player_visible_layers(self, fact_id: UUID) -> dict[LayerType, str]:
        """
        Gibt zurück was der Spieler sehen darf (alles außer truth).
        
        Wenn Reality-Score niedrig: zurückgegebene Werte können bereits
        durch apply_corruption modifiziert sein.
        """
        raise NotImplementedError("Phase 2")

    def diff_layers(self, fact_id: UUID) -> dict[str, Any]:
        """Vergleicht alle Layer-Versionen für Debugging."""
        raise NotImplementedError("Phase 2")

    # ------------------------------------------------------------------
    # Drift (Hidden State Magic)
    # ------------------------------------------------------------------

    def apply_corruption(
        self, player_id: UUID, intensity: float
    ) -> list[ChangeRecord]:
        """
        Modifiziert subtil 1-2 Layer (perceived/claimed) eines kürzlich
        besuchten Facts. Höhere Intensity = mehr/stärkere Änderungen.
        
        Wird periodisch von einem Background-Job aufgerufen wenn Reality
        unter Threshold sinkt.
        """
        raise NotImplementedError("Phase 2")

    def adjust_reality_score(self, player_id: UUID, delta: float) -> float:
        """Passt Reality-Score an. Returnt neuen Wert."""
        raise NotImplementedError("Phase 2")
