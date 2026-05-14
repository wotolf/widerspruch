"""Tests für case_lifecycle — evaluate_transition und apply_transition."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from backend.core.case_lifecycle import (
    _FIRST_TO_SECOND_ACTIONS,
    _FIRST_TO_SECOND_REALITY,
    _INVEST_TO_FIRST_ACTIONS,
    _INVEST_TO_FIRST_NPCS,
    _OPEN_TO_INVEST_ACTIONS,
    _SECOND_TO_FINALE_ACTIONS,
    _SECOND_TO_FINALE_REALITY,
    apply_transition,
    evaluate_transition,
)


def _case(phase: str) -> MagicMock:
    c = MagicMock()
    c.id = uuid4()
    c.phase = phase
    return c


# ---------------------------------------------------------------------------
# evaluate_transition — happy paths
# ---------------------------------------------------------------------------

class TestEvaluateTransitionHappyPath:
    def test_opening_to_investigation(self):
        case = _case("opening")
        result = evaluate_transition(case, _OPEN_TO_INVEST_ACTIONS, 0, 1.0)
        assert result == "investigation"

    def test_investigation_to_first_reveal(self):
        case = _case("investigation")
        result = evaluate_transition(case, _INVEST_TO_FIRST_ACTIONS, _INVEST_TO_FIRST_NPCS, 1.0)
        assert result == "first_reveal"

    def test_first_reveal_to_second_reveal(self):
        case = _case("first_reveal")
        result = evaluate_transition(
            case, _FIRST_TO_SECOND_ACTIONS, 0, _FIRST_TO_SECOND_REALITY
        )
        assert result == "second_reveal"

    def test_second_reveal_to_finale(self):
        case = _case("second_reveal")
        result = evaluate_transition(
            case, _SECOND_TO_FINALE_ACTIONS, 0, _SECOND_TO_FINALE_REALITY
        )
        assert result == "finale"

    def test_finale_has_no_transition(self):
        case = _case("finale")
        result = evaluate_transition(case, 999, 99, 0.0)
        assert result is None

    def test_closed_has_no_transition(self):
        case = _case("closed")
        result = evaluate_transition(case, 999, 99, 0.0)
        assert result is None


# ---------------------------------------------------------------------------
# evaluate_transition — just below threshold (no transition)
# ---------------------------------------------------------------------------

class TestEvaluateTransitionBelowThreshold:
    def test_opening_one_below_action_threshold(self):
        case = _case("opening")
        result = evaluate_transition(case, _OPEN_TO_INVEST_ACTIONS - 1, 0, 1.0)
        assert result is None

    def test_investigation_actions_met_but_npcs_missing(self):
        case = _case("investigation")
        result = evaluate_transition(
            case, _INVEST_TO_FIRST_ACTIONS, _INVEST_TO_FIRST_NPCS - 1, 1.0
        )
        assert result is None

    def test_investigation_npcs_met_but_actions_missing(self):
        case = _case("investigation")
        result = evaluate_transition(
            case, _INVEST_TO_FIRST_ACTIONS - 1, _INVEST_TO_FIRST_NPCS, 1.0
        )
        assert result is None

    def test_first_reveal_actions_met_but_reality_too_high(self):
        case = _case("first_reveal")
        result = evaluate_transition(
            case, _FIRST_TO_SECOND_ACTIONS, 0, _FIRST_TO_SECOND_REALITY + 0.01
        )
        assert result is None

    def test_first_reveal_reality_met_but_actions_missing(self):
        case = _case("first_reveal")
        result = evaluate_transition(
            case, _FIRST_TO_SECOND_ACTIONS - 1, 0, _FIRST_TO_SECOND_REALITY
        )
        assert result is None

    def test_second_reveal_actions_met_but_reality_too_high(self):
        case = _case("second_reveal")
        result = evaluate_transition(
            case, _SECOND_TO_FINALE_ACTIONS, 0, _SECOND_TO_FINALE_REALITY + 0.01
        )
        assert result is None

    def test_second_reveal_reality_met_but_actions_missing(self):
        case = _case("second_reveal")
        result = evaluate_transition(
            case, _SECOND_TO_FINALE_ACTIONS - 1, 0, _SECOND_TO_FINALE_REALITY
        )
        assert result is None


# ---------------------------------------------------------------------------
# apply_transition
# ---------------------------------------------------------------------------

class TestApplyTransition:
    async def test_writes_phase_history_entry(self):
        case = _case("opening")
        added: list = []
        session = MagicMock()
        session.add = MagicMock(side_effect=added.append)

        await apply_transition(session, case, "investigation", reason="player_action")

        assert len(added) == 1
        entry = added[0]
        assert entry.from_phase == "opening"
        assert entry.to_phase == "investigation"
        assert entry.reason == "player_action"
        assert entry.case_id == case.id

    async def test_updates_case_phase(self):
        case = _case("investigation")
        session = MagicMock()
        session.add = MagicMock()

        await apply_transition(session, case, "first_reveal", reason="test")

        assert case.phase == "first_reveal"

    async def test_admin_override_reason_stored(self):
        case = _case("opening")
        added: list = []
        session = MagicMock()
        session.add = MagicMock(side_effect=added.append)

        await apply_transition(session, case, "finale", reason="admin_override")

        assert added[0].reason == "admin_override"

    async def test_returns_history_entry(self):
        case = _case("opening")
        session = MagicMock()
        session.add = MagicMock()

        from backend.db.models import CasePhaseHistory
        entry = await apply_transition(session, case, "investigation", reason="test")

        assert isinstance(entry, CasePhaseHistory)
        assert entry.to_phase == "investigation"


# ---------------------------------------------------------------------------
# Integration: /note flow triggering a transition
# ---------------------------------------------------------------------------

class TestDoneCriteria:
    """Konkrete Werte aus dem Done-Kriterium — bleiben auch nach Konstanten-Änderungen grün."""

    def test_first_reveal_reality_065_no_transition(self):
        case = _case("first_reveal")
        result = evaluate_transition(case, _FIRST_TO_SECOND_ACTIONS, 0, 0.65)
        assert result is None, "Reality=0.65 liegt über Threshold 0.60 — keine Transition erwartet"

    def test_first_reveal_reality_055_triggers_second_reveal(self):
        case = _case("first_reveal")
        result = evaluate_transition(case, _FIRST_TO_SECOND_ACTIONS, 0, 0.55)
        assert result == "second_reveal", "Reality=0.55 liegt unter Threshold 0.60 — Transition erwartet"


class TestNoteFlowTriggersTransition:
    def test_note_count_at_threshold_triggers_investigation(self):
        """Simuliert: action_count erreicht Schwelle → Transition zu investigation."""
        case = _case("opening")
        action_count = _OPEN_TO_INVEST_ACTIONS
        unique_npcs = 0
        reality_score = 1.0

        result = evaluate_transition(case, action_count, unique_npcs, reality_score)
        assert result == "investigation", (
            f"Erwartete Transition zu 'investigation' bei action_count={action_count}"
        )

    def test_note_count_below_threshold_no_transition(self):
        case = _case("opening")
        result = evaluate_transition(case, _OPEN_TO_INVEST_ACTIONS - 1, 0, 1.0)
        assert result is None
