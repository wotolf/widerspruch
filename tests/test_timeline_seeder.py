"""Tests für TimelineSeeder — LLM und DB gemockt."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from backend.core.timeline_seeder import (
    TimelineSeeder,
    TimelineSeederError,
    SeedResult,
    _parse_json,
    _validate,
)
from backend.core.llm import LLMResponse
from backend.db.models import Case, PlayerProfile, TimelineEvent


def _make_events(n: int = 9) -> list[dict]:
    return [
        {
            "wall_clock_slot": f"Day1-{20 + i:02d}:00",
            "occurred_at": f"2024-11-15T{20 + i:02d}:00:00+00:00",
            "description": f"Ereignis {i + 1} mit ausreichend langem Beschreibungstext hier",
        }
        for i in range(n)
    ]


def _make_timeline_json(n: int = 9) -> str:
    slots = _make_events(n)
    return json.dumps({
        "investigator": slots,
        "shadow_a":     slots,
        "shadow_b":     slots,
    })


def _make_llm(text: str) -> MagicMock:
    llm = MagicMock()
    llm.complete.return_value = LLMResponse(
        text=text, input_tokens=100, output_tokens=300, model="claude-haiku-test"
    )
    return llm


def _make_session(*, case: MagicMock | None = None) -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock(return_value=case)
    return session


def _make_case() -> MagicMock:
    c = MagicMock(spec=Case)
    c.id = uuid4()
    c.title = "Akte 2024-001: Testfall"
    c.started_at = datetime(2024, 11, 15, 0, 0, tzinfo=timezone.utc)
    return c


def _make_profile() -> MagicMock:
    p = MagicMock(spec=PlayerProfile)
    p.city = "Berlin"
    p.routine = "Morgens Café, abends Park"
    return p


# ---------------------------------------------------------------------------
# _parse_json
# ---------------------------------------------------------------------------

class TestParseJson:
    def test_direct_json(self):
        data = _parse_json('{"a": 1}')
        assert data["a"] == 1

    def test_strips_fences(self):
        data = _parse_json('```json\n{"a": 1}\n```')
        assert data["a"] == 1

    def test_raises_on_garbage(self):
        with pytest.raises(TimelineSeederError):
            _parse_json("kein json hier")


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_passes(self):
        events = _make_events(9)
        _validate({"investigator": events, "shadow_a": events, "shadow_b": events})

    def test_too_few_events_raises(self):
        events = _make_events(5)
        with pytest.raises(TimelineSeederError, match="mindestens 8"):
            _validate({"investigator": events, "shadow_a": events, "shadow_b": events})

    def test_missing_timeline_raises(self):
        events = _make_events(9)
        with pytest.raises(TimelineSeederError, match="Fehlende Timelines"):
            _validate({"investigator": events, "shadow_a": events})

    def test_duplicate_slots_raises(self):
        events = _make_events(9)
        dup = events + [events[0]]  # doppelter Slot
        with pytest.raises(TimelineSeederError, match="doppelte"):
            _validate({"investigator": dup, "shadow_a": _make_events(9), "shadow_b": _make_events(9)})

    def test_short_description_raises(self):
        events = _make_events(9)
        events[0]["description"] = "zu kurz"
        with pytest.raises(TimelineSeederError, match="kurz"):
            _validate({"investigator": events, "shadow_a": _make_events(9), "shadow_b": _make_events(9)})

    def test_mismatched_slots_raises(self):
        base = _make_events(9)
        other = _make_events(8)  # anderes Slot-Set
        with pytest.raises(TimelineSeederError, match="andere Zeitslots"):
            _validate({"investigator": base, "shadow_a": other, "shadow_b": base})


# ---------------------------------------------------------------------------
# TimelineSeeder.seed_case
# ---------------------------------------------------------------------------

class TestTimelineSeeder:
    async def test_returns_seed_result(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(9)))
        result = await seeder.seed_case(uuid4(), _make_profile())
        assert isinstance(result, SeedResult)

    async def test_counts_correct(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(10)))
        result = await seeder.seed_case(uuid4(), _make_profile())
        assert result.investigator_count == 10
        assert result.shadow_a_count == 10
        assert result.shadow_b_count == 10

    async def test_all_events_added_to_session(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(9)))
        await seeder.seed_case(uuid4(), _make_profile())
        # 3 Timelines × 9 Events = 27 adds
        assert session.add.call_count == 27

    async def test_all_visible_to_player_false(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(9)))
        await seeder.seed_case(uuid4(), _make_profile())
        added = [call.args[0] for call in session.add.call_args_list]
        assert all(isinstance(e, TimelineEvent) for e in added)
        assert all(e.visible_to_player is False for e in added)

    async def test_three_timelines_in_added_events(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(9)))
        await seeder.seed_case(uuid4(), _make_profile())
        added = [call.args[0] for call in session.add.call_args_list]
        found = {e.timeline for e in added}
        assert found == {"investigator", "shadow_a", "shadow_b"}

    async def test_same_wall_clock_slots_across_timelines(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(9)))
        await seeder.seed_case(uuid4(), _make_profile())
        added = [call.args[0] for call in session.add.call_args_list]
        by_timeline: dict[str, set[str]] = {}
        for e in added:
            by_timeline.setdefault(e.timeline, set()).add(e.wall_clock_slot)
        assert by_timeline["investigator"] == by_timeline["shadow_a"] == by_timeline["shadow_b"]

    async def test_flush_called(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(9)))
        await seeder.seed_case(uuid4(), _make_profile())
        session.flush.assert_awaited_once()

    async def test_raises_when_case_not_found(self):
        session = _make_session(case=None)
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(9)))
        with pytest.raises(TimelineSeederError, match="nicht gefunden"):
            await seeder.seed_case(uuid4(), _make_profile())

    async def test_raises_on_invalid_llm_json(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm("kein json"))
        with pytest.raises(TimelineSeederError):
            await seeder.seed_case(uuid4(), _make_profile())

    async def test_raises_on_too_few_events(self):
        session = _make_session(case=_make_case())
        seeder = TimelineSeeder(db_session=session, llm=_make_llm(_make_timeline_json(5)))
        with pytest.raises(TimelineSeederError, match="mindestens 8"):
            await seeder.seed_case(uuid4(), _make_profile())
