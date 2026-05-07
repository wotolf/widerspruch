"""Tests für TruthEngine — alle DB-Calls gemockt."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from backend.core.truth_engine import ChangeRecord, LayerType, TruthEngine
from backend.db.models import Case, Fact, FactLayer, Player


def _make_session(*, scalar=None, scalars=None):
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock(return_value=scalar)
    session.scalars = AsyncMock(return_value=scalars or [])
    return session


def _make_engine(session=None, **kwargs):
    if session is None:
        session = _make_session(**kwargs)
    return TruthEngine(db_session=session, llm=MagicMock())


class TestRecordTruth:
    async def test_adds_fact_and_layer(self):
        session = _make_session(scalar=None)
        engine = _make_engine(session)
        await engine.record_truth(uuid4(), "Beschreibung", "Wert")

        assert session.add.call_count == 2
        session.flush.assert_awaited_once()

    async def test_returns_fact(self):
        session = _make_session(scalar=None)
        engine = _make_engine(session)
        fact = await engine.record_truth(uuid4(), "Beschreibung", "Wert")

        assert isinstance(fact, Fact)
        assert fact.description == "Beschreibung"
        assert fact.id is not None

    async def test_truth_layer_has_correct_type(self):
        session = _make_session(scalar=None)
        engine = _make_engine(session)
        await engine.record_truth(uuid4(), "Beschreibung", "Wert")

        added_objects = [call.args[0] for call in session.add.call_args_list]
        layers = [o for o in added_objects if isinstance(o, FactLayer)]
        assert len(layers) == 1
        assert layers[0].layer_type == "truth"
        assert layers[0].modified_by == "system"
        assert layers[0].version == 1


class TestRecordPerception:
    async def test_adds_perceived_layer(self):
        session = _make_session(scalar=None)
        engine = _make_engine(session)
        layer = await engine.record_perception(uuid4(), "Wahrnehmung", "system")

        session.add.assert_called_once()
        assert isinstance(layer, FactLayer)
        assert layer.layer_type == "perceived"

    async def test_version_increments(self):
        session = _make_session(scalar=3)  # max_v = 3
        engine = _make_engine(session)
        layer = await engine.record_perception(uuid4(), "Neu", "system")
        assert layer.version == 4


class TestGetPlayerVisibleLayers:
    async def test_excludes_truth(self):
        # Die DB-Query filtert truth bereits heraus — Mock gibt nur zurück was die DB liefern würde
        perceived_layer = MagicMock(spec=FactLayer)
        perceived_layer.layer_type = "perceived"
        perceived_layer.value = "sichtbar"

        session = _make_session(scalars=[perceived_layer])
        engine = _make_engine(session)
        result = await engine.get_player_visible_layers(uuid4())

        assert "truth" not in result
        assert result["perceived"] == "sichtbar"

    async def test_latest_version_wins(self):
        old = MagicMock(spec=FactLayer)
        old.layer_type = "perceived"
        old.value = "alt"

        new = MagicMock(spec=FactLayer)
        new.layer_type = "perceived"
        new.value = "neu"

        # Sortierung: neueste zuerst (query ORDER BY version DESC)
        session = _make_session(scalars=[new, old])
        engine = _make_engine(session)
        result = await engine.get_player_visible_layers(uuid4())

        assert result["perceived"] == "neu"

    async def test_empty_fact_returns_empty_dict(self):
        session = _make_session(scalars=[])
        engine = _make_engine(session)
        result = await engine.get_player_visible_layers(uuid4())
        assert result == {}


class TestAdjustRealityScore:
    async def _player_with_score(self, score: float) -> MagicMock:
        player = MagicMock(spec=Player)
        player.reality_score = score
        return player

    async def test_clamps_above_one(self):
        player = await self._player_with_score(1.0)
        session = _make_session(scalar=player)
        engine = _make_engine(session)
        result = await engine.adjust_reality_score(uuid4(), +0.5)
        assert result == 1.0
        assert player.reality_score == 1.0

    async def test_clamps_below_zero(self):
        player = await self._player_with_score(0.0)
        session = _make_session(scalar=player)
        engine = _make_engine(session)
        result = await engine.adjust_reality_score(uuid4(), -0.5)
        assert result == 0.0
        assert player.reality_score == 0.0

    async def test_negative_delta_lowers_score(self):
        player = await self._player_with_score(0.8)
        session = _make_session(scalar=player)
        engine = _make_engine(session)
        result = await engine.adjust_reality_score(uuid4(), -0.02)
        assert abs(result - 0.78) < 1e-9

    async def test_positive_delta_raises_score(self):
        player = await self._player_with_score(0.5)
        session = _make_session(scalar=player)
        engine = _make_engine(session)
        result = await engine.adjust_reality_score(uuid4(), +0.1)
        assert abs(result - 0.6) < 1e-9


class TestApplyCorruption:
    async def test_returns_empty_when_intensity_zero(self):
        session = _make_session()
        engine = _make_engine(session)
        result = await engine.apply_corruption(uuid4(), 0.0)
        assert result == []
        engine.llm.complete.assert_not_called()

    async def test_returns_empty_when_no_active_case(self):
        session = _make_session(scalar=None)
        engine = _make_engine(session)
        result = await engine.apply_corruption(uuid4(), 0.3)
        assert result == []

    async def test_returns_change_record_on_success(self):
        player_id = uuid4()
        case_id = uuid4()
        fact_id = uuid4()

        mock_case = MagicMock(spec=Case)
        mock_case.id = case_id

        mock_fact = MagicMock(spec=Fact)
        mock_fact.id = fact_id

        mock_layer = MagicMock(spec=FactLayer)
        mock_layer.fact_id = fact_id
        mock_layer.layer_type = "perceived"
        mock_layer.value = "Original-Text"
        mock_layer.version = 1

        mock_llm = MagicMock()
        mock_llm.complete.return_value = MagicMock(text="Modifizierter Text")

        # scalar() gibt nacheinander: case, dann layer (pro fact-iteration)
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.scalar = AsyncMock(side_effect=[mock_case, mock_layer])
        session.scalars = AsyncMock(return_value=[mock_fact])

        engine = TruthEngine(db_session=session, llm=mock_llm)
        result = await engine.apply_corruption(player_id, 0.3)

        assert len(result) == 1
        assert isinstance(result[0], ChangeRecord)
        assert result[0].old_value == "Original-Text"
        assert result[0].new_value == "Modifizierter Text"
        assert result[0].layer_type == LayerType.PERCEIVED
        session.add.assert_called_once()
