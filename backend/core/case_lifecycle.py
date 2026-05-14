"""Case Lifecycle — evaluiert und schreibt Phase-Übergänge."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Case, CasePhaseHistory

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Schwellwerte — als Konstanten damit sie leicht anpassbar sind
# ---------------------------------------------------------------------------

# opening → investigation
_OPEN_TO_INVEST_ACTIONS: int = 3

# investigation → first_reveal
_INVEST_TO_FIRST_ACTIONS: int = 10
_INVEST_TO_FIRST_NPCS: int = 2

# first_reveal → second_reveal
_FIRST_TO_SECOND_ACTIONS: int = 20
_FIRST_TO_SECOND_REALITY: float = 0.60

# second_reveal → finale
_SECOND_TO_FINALE_ACTIONS: int = 30
_SECOND_TO_FINALE_REALITY: float = 0.30

VALID_PHASES = ("opening", "investigation", "first_reveal", "second_reveal", "finale", "closed")

_PHASE_MESSAGES: dict[str, str] = {
    "investigation": "Die Ermittlung nimmt Fahrt auf.",
    "first_reveal": "Eine erste Wahrheit taucht auf der Oberfläche auf.",
    "second_reveal": "Die Realität beginnt zu verschwimmen.",
    "finale": "Das Finale naht.",
}


def evaluate_transition(
    case: Case,
    action_count: int,
    unique_npcs_interrogated: int,
    reality_score: float,
) -> str | None:
    """
    Gibt die neue Phase zurück wenn eine Transition fällig ist, sonst None.
    Rein funktional — kein DB-Zugriff.
    """
    phase = case.phase
    if phase == "opening":
        if action_count >= _OPEN_TO_INVEST_ACTIONS:
            return "investigation"
    elif phase == "investigation":
        if action_count >= _INVEST_TO_FIRST_ACTIONS and unique_npcs_interrogated >= _INVEST_TO_FIRST_NPCS:
            return "first_reveal"
    elif phase == "first_reveal":
        if action_count >= _FIRST_TO_SECOND_ACTIONS and reality_score <= _FIRST_TO_SECOND_REALITY:
            return "second_reveal"
    elif phase == "second_reveal":
        if action_count >= _SECOND_TO_FINALE_ACTIONS and reality_score <= _SECOND_TO_FINALE_REALITY:
            return "finale"
    return None


def phase_transition_message(new_phase: str) -> str:
    return _PHASE_MESSAGES.get(new_phase, "Die Ermittlung entwickelt sich.")


async def apply_transition(
    db: AsyncSession,
    case: Case,
    new_phase: str,
    reason: str,
) -> CasePhaseHistory:
    """Schreibt case.phase und legt einen Eintrag in case_phase_history an."""
    from_phase = case.phase
    case.phase = new_phase
    entry = CasePhaseHistory(
        id=uuid4(),
        case_id=case.id,
        from_phase=from_phase,
        to_phase=new_phase,
        reason=reason,
        transitioned_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    log.info(
        "case_phase_transition",
        case_id=str(case.id),
        from_phase=from_phase,
        to_phase=new_phase,
        reason=reason,
    )
    return entry
