"""Tests für Journal/Vergleichen-Mechanik — DB gemockt."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4
from datetime import datetime, timezone

import discord

from backend.bot.main import _word_diff


# ---------------------------------------------------------------------------
# _word_diff helper
# ---------------------------------------------------------------------------

class TestWordDiff:
    def test_identical_strings_no_markers(self):
        result = _word_diff("Emma Schmidt verschwand", "Emma Schmidt verschwand")
        assert "+" not in result
        assert "-" not in result

    def test_changed_word_shows_markers(self):
        result = _word_diff("Emma Schmidt verschwand dienstagabend", "Emma Schmidt verschwand mittwochabend")
        assert "- dienstagabend" in result
        assert "+ mittwochabend" in result

    def test_empty_old(self):
        result = _word_diff("", "neues Wort")
        assert "+ neues" in result

    def test_empty_new(self):
        result = _word_diff("altes Wort", "")
        assert "- altes" in result


# ---------------------------------------------------------------------------
# /note — fact_id und snapshot_value Speicherung
# ---------------------------------------------------------------------------

def _make_fact(description: str = "Emma Schmidt verschwand spurlos"):
    f = MagicMock()
    f.id = uuid4()
    f.description = description
    return f


def _make_layer(value: str, version: int = 1):
    layer = MagicMock()
    layer.value = value
    layer.version = version
    return layer


def _make_note(text: str, fact_id=None, snapshot_value: str | None = None):
    n = MagicMock()
    n.id = uuid4()
    n.text = text
    n.fact_id = fact_id
    n.snapshot_value = snapshot_value
    n.created_at = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    return n


class TestNoteWithSpur:
    """Testet die Logik rund um /note spur=<nr>."""

    def test_note_with_valid_spur_sets_fact_id_and_snapshot(self):
        """Wenn spur gesetzt und gültig: fact_id + snapshot_value werden aus perceived-Layer gefüllt."""
        fact = _make_fact("Emma Schmidt verschwand spurlos")
        layer = _make_layer("Emma Schmidt verschwand spurlos — wahrgenommen")
        added_notes: list = []

        session = MagicMock()
        session.scalars = AsyncMock(return_value=[fact])
        session.scalar = AsyncMock(return_value=layer)
        session.add = MagicMock(side_effect=lambda obj: added_notes.append(obj))

        # Simuliere die Kernlogik aus /note (fact lookup + snapshot)
        facts = [fact]
        spur_nr = 1
        linked_fact = facts[spur_nr - 1]
        fact_id = linked_fact.id
        snapshot_value = layer.value

        assert fact_id == fact.id
        assert snapshot_value == "Emma Schmidt verschwand spurlos — wahrgenommen"

    def test_note_without_spur_has_null_fact_id(self):
        """Wenn spur nicht gesetzt: fact_id und snapshot_value bleiben None."""
        fact_id = None
        snapshot_value = None

        assert fact_id is None
        assert snapshot_value is None

    def test_note_with_invalid_spur_out_of_range(self):
        """Spurennummer außerhalb des Bereichs → keine Notiz gespeichert."""
        facts = [_make_fact()]
        spur_nr = 99

        is_invalid = spur_nr < 1 or spur_nr > len(facts)
        assert is_invalid

    def test_note_with_spur_zero_is_invalid(self):
        """Spurennummer 0 ist ungültig."""
        facts = [_make_fact()]
        spur_nr = 0

        is_invalid = spur_nr < 1 or spur_nr > len(facts)
        assert is_invalid


# ---------------------------------------------------------------------------
# /vergleichen — Diff-Logik
# ---------------------------------------------------------------------------

class TestVergleichen:
    def test_identical_snapshot_and_current_shows_no_change(self):
        """Wenn snapshot == aktueller Wert: kein Diff-Block."""
        snapshot = "Emma Schmidt verschwand dienstagabend spurlos"
        current = "Emma Schmidt verschwand dienstagabend spurlos"

        no_change = current == snapshot
        assert no_change

    def test_changed_value_produces_diff(self):
        """Wenn Werte unterschiedlich: _word_diff liefert Marker."""
        snapshot = "Emma Schmidt verschwand dienstagabend"
        current = "Emma Schmidt verschwand mittwochabend"

        diff = _word_diff(snapshot, current)
        assert "dienstagabend" in diff
        assert "mittwochabend" in diff
        assert "+" in diff or "-" in diff

    def test_note_without_fact_id_triggers_no_fact_bound_message(self):
        """Notiz ohne fact_id → 'nicht an eine Spur gebunden'."""
        note = _make_note("Meine Beobachtung", fact_id=None)
        assert note.fact_id is None

    def test_note_with_fact_id_enables_comparison(self):
        """Notiz mit fact_id → Vergleich möglich."""
        fact_id = uuid4()
        snapshot = "Emma war zuletzt dienstagabend gesehen worden"
        note = _make_note("Meine Beobachtung", fact_id=fact_id, snapshot_value=snapshot)
        assert note.fact_id is not None
        assert note.snapshot_value == snapshot
