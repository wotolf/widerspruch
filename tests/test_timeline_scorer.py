"""Tests für TimelineScorer — DB gemockt."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from backend.core.timeline_scorer import TimelineScorer, _tokenize


def _make_event(description: str, support_score: float = 0.5) -> MagicMock:
    e = MagicMock()
    e.id = uuid4()
    e.description = description
    e.support_score = support_score
    return e


def _make_session(events: list) -> MagicMock:
    session = MagicMock()
    session.scalars = AsyncMock(return_value=events)
    return session


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_lowercases(self):
        assert "emma" in _tokenize("Emma")

    def test_filters_stopwords(self):
        tokens = _tokenize("der die das")
        assert tokens == set()

    def test_filters_short_tokens(self):
        assert "ab" not in _tokenize("ab xy")

    def test_splits_on_punctuation(self):
        tokens = _tokenize("Schmidt, verschwand.")
        assert "schmidt" in tokens
        assert "verschwand" in tokens


# ---------------------------------------------------------------------------
# TimelineScorer.score_action
# ---------------------------------------------------------------------------

class TestTimelineScorer:
    async def test_score_increases_on_match(self):
        events = [
            _make_event("Emma Schmidt verschwand dienstagabend spurlos"),
            _make_event("Das Wetter war regnerisch trocken draußen"),
        ]
        session = _make_session(events)
        await TimelineScorer().score_action(
            uuid4(), "spur", "Emma Schmidt dienstagabend gesehen", session
        )
        assert events[0].support_score > 0.5

    async def test_top_two_updated(self):
        events = [
            _make_event("Emma Schmidt verschwand dienstagabend spurlos"),
            _make_event("Schmidt wurde abends zuletzt gesehen spurlos"),
            _make_event("Das Wetter war regnerisch trocken draußen völlig"),
        ]
        session = _make_session(events)
        await TimelineScorer().score_action(
            uuid4(), "befragen", "Emma Schmidt abends gesehen", session
        )
        assert events[0].support_score > 0.5
        assert events[1].support_score > 0.5
        assert events[2].support_score == pytest.approx(0.5)

    async def test_score_clamped_to_one(self):
        events = [_make_event("Emma Schmidt verschwand spurlos", support_score=0.98)]
        session = _make_session(events)
        await TimelineScorer().score_action(
            uuid4(), "befragen", "Emma Schmidt Aussage spurlos", session
        )
        assert events[0].support_score <= 1.0

    async def test_score_exactly_one_at_cap(self):
        events = [_make_event("Emma Schmidt verschwand spurlos", support_score=1.0)]
        session = _make_session(events)
        await TimelineScorer().score_action(
            uuid4(), "spur", "Emma Schmidt spurlos", session
        )
        assert events[0].support_score == pytest.approx(1.0)

    async def test_unrelated_context_no_change(self):
        events = [
            _make_event("Emma Schmidt verschwand dienstagabend spurlos"),
            _make_event("Zeuge sah das Fahrzeug vorbefahren langsam"),
        ]
        original = [e.support_score for e in events]
        session = _make_session(events)
        await TimelineScorer().score_action(
            uuid4(), "note", "xyzzy foobar quxquux blorblorg", session
        )
        for ev, orig in zip(events, original):
            assert ev.support_score == pytest.approx(orig)

    async def test_empty_context_no_change(self):
        events = [_make_event("Emma Schmidt verschwand spurlos")]
        session = _make_session(events)
        await TimelineScorer().score_action(uuid4(), "spur", "", session)
        assert events[0].support_score == pytest.approx(0.5)
        session.scalars.assert_not_awaited()

    async def test_no_events_is_noop(self):
        session = _make_session([])
        await TimelineScorer().score_action(
            uuid4(), "spur", "Emma Schmidt verschwand", session
        )

    async def test_note_delta_smaller_than_befragen(self):
        case_id = uuid4()
        desc = "Emma Schmidt verschwand dienstagabend spurlos abends"
        ev_spur = _make_event(desc)
        ev_befragen = _make_event(desc)
        ev_note = _make_event(desc)
        context = "Emma Schmidt dienstagabend abends verschwand spurlos"

        await TimelineScorer().score_action(case_id, "note", context, _make_session([ev_note]))
        await TimelineScorer().score_action(case_id, "befragen", context, _make_session([ev_befragen]))
        await TimelineScorer().score_action(case_id, "spur", context, _make_session([ev_spur]))

        assert ev_note.support_score < ev_spur.support_score < ev_befragen.support_score
