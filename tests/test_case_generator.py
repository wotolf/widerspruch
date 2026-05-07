"""Tests für CaseGenerator-Hilfsfunktionen (ohne LLM/DB) und generate() mit Mock-LLM."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from backend.core.case_generator import (
    CaseGenerationError,
    CaseGenerator,
    GeneratedCase,
    _build_fact_descriptions,
    _parse_json_response,
    _validate,
)
from backend.core.llm import LLMResponse

SAMPLE: dict = {
    "title": "Akte 2026-001: Unbekannte Person, Mitte",
    "missing_person": {
        "alter": "34",
        "beruf": "Softwareentwickler",
        "routine": "Morgens Café, abends Park",
    },
    "disappearance_circumstances": "Zuletzt gesehen am 3. Mai gegen 22:30 Uhr.",
    "initial_leads": [
        {"id": "L1", "headline": "Zeuge im Café Schiller", "details": "Barista erinnert sich an auffälliges Gespräch"},
        {"id": "L2", "headline": "Handy-Signal", "details": "Letztes Signal aus Mitte, 22:47 Uhr"},
    ],
    "npcs": [
        {"name": "Anna K.", "relationship": "Bekannte", "personality_brief": "Nervös, ausweichend"},
        {"name": "Tom R.", "relationship": "Arbeitskollege", "personality_brief": "Kooperativ, detailreich"},
    ],
    "locations": [{"name": "Café Schiller"}, {"name": "Tempelhofer Feld"}],
    "timeline": [{"date": "2026-05-03", "event": "Letzte bekannte Aktivität"}],
}


class TestParseJsonResponse:
    def test_direct_json(self):
        result = _parse_json_response(json.dumps(SAMPLE))
        assert result["title"] == SAMPLE["title"]

    def test_strips_markdown_fences(self):
        # Exaktes LLM-Format: ```json\n{\n  "key": "val"\n}\n```
        fenced = "```json\n" + json.dumps(SAMPLE, indent=2, ensure_ascii=False) + "\n```"
        result = _parse_json_response(fenced)
        assert result["title"] == SAMPLE["title"]

    def test_strips_markdown_fences_uppercase(self):
        fenced = "```JSON\n" + json.dumps(SAMPLE, indent=2, ensure_ascii=False) + "\n```"
        result = _parse_json_response(fenced)
        assert result["title"] == SAMPLE["title"]

    def test_strips_plain_fences(self):
        fenced = "```\n" + json.dumps(SAMPLE, indent=2, ensure_ascii=False) + "\n```"
        result = _parse_json_response(fenced)
        assert result["title"] == SAMPLE["title"]

    def test_extracts_json_from_prose(self):
        prose = "Hier ist die Akte:\n\n" + json.dumps(SAMPLE) + "\n\nEnde der Übermittlung."
        result = _parse_json_response(prose)
        assert result["title"] == SAMPLE["title"]

    def test_raises_on_invalid(self):
        with pytest.raises(CaseGenerationError, match="Kein valides JSON"):
            _parse_json_response("Das ist kein JSON.")

    def test_raises_on_empty(self):
        with pytest.raises(CaseGenerationError):
            _parse_json_response("")


class TestValidate:
    def test_valid_sample_passes(self):
        _validate(SAMPLE)  # kein Exception

    def test_missing_title_raises(self):
        data = {**SAMPLE}
        del data["title"]
        with pytest.raises(CaseGenerationError, match="Pflichtfelder"):
            _validate(data)

    def test_empty_leads_raises(self):
        data = {**SAMPLE, "initial_leads": []}
        with pytest.raises(CaseGenerationError, match="initial_leads"):
            _validate(data)

    def test_empty_npcs_raises(self):
        data = {**SAMPLE, "npcs": []}
        with pytest.raises(CaseGenerationError, match="npcs"):
            _validate(data)


class TestBuildFactDescriptions:
    def test_contains_missing_person(self):
        descs = _build_fact_descriptions(SAMPLE)
        assert any("Vermissteninfo" in d for d in descs)

    def test_contains_disappearance(self):
        descs = _build_fact_descriptions(SAMPLE)
        assert any("Verschwinden" in d for d in descs)

    def test_contains_all_leads(self):
        descs = _build_fact_descriptions(SAMPLE)
        assert any("Café Schiller" in d for d in descs)
        assert any("Handy-Signal" in d for d in descs)

    def test_contains_locations(self):
        descs = _build_fact_descriptions(SAMPLE)
        assert any("Tempelhofer Feld" in d for d in descs)

    def test_count(self):
        descs = _build_fact_descriptions(SAMPLE)
        # 1 missing_person + 1 disappearance + 2 leads + 2 locations = 6
        assert len(descs) == 6

    def test_empty_data_returns_empty(self):
        descs = _build_fact_descriptions({})
        assert descs == []


# ---------------------------------------------------------------------------
# CaseGenerator.generate() — LLM und Session gemockt
# ---------------------------------------------------------------------------

def _make_llm(response_text: str) -> MagicMock:
    llm = MagicMock()
    llm.complete.return_value = LLMResponse(
        text=response_text,
        input_tokens=100,
        output_tokens=200,
        model="claude-test",
    )
    return llm


def _make_session() -> MagicMock:
    session = MagicMock()
    session.flush = AsyncMock()
    return session


class TestCaseGeneratorGenerate:
    async def test_returns_generated_case(self):
        gen = CaseGenerator(llm=_make_llm(json.dumps(SAMPLE)))
        result = await gen.generate(uuid4(), {"city": "Berlin"}, _make_session())
        assert isinstance(result, GeneratedCase)
        assert result.title == SAMPLE["title"]

    async def test_result_fields_match_sample(self):
        gen = CaseGenerator(llm=_make_llm(json.dumps(SAMPLE)))
        result = await gen.generate(uuid4(), {}, _make_session())
        assert result.npcs == SAMPLE["npcs"]
        assert result.initial_leads == SAMPLE["initial_leads"]
        assert result.locations == SAMPLE["locations"]
        assert result.timeline == SAMPLE["timeline"]
        assert result.disappearance_circumstances == SAMPLE["disappearance_circumstances"]

    async def test_persists_case_npcs_and_facts(self):
        session = _make_session()
        gen = CaseGenerator(llm=_make_llm(json.dumps(SAMPLE)))
        await gen.generate(uuid4(), {}, session)

        session.flush.assert_awaited_once()
        # 1 Case + 2 NPCs + 6 Facts (verified by TestBuildFactDescriptions.test_count)
        assert session.add.call_count == 9

    async def test_invalid_json_raises(self):
        gen = CaseGenerator(llm=_make_llm("Das ist kein JSON."))
        with pytest.raises(CaseGenerationError, match="Kein valides JSON"):
            await gen.generate(uuid4(), {}, _make_session())

    async def test_missing_required_field_raises(self):
        data = {**SAMPLE}
        del data["title"]
        gen = CaseGenerator(llm=_make_llm(json.dumps(data)))
        with pytest.raises(CaseGenerationError, match="Pflichtfelder"):
            await gen.generate(uuid4(), {}, _make_session())

    async def test_empty_leads_raises(self):
        data = {**SAMPLE, "initial_leads": []}
        gen = CaseGenerator(llm=_make_llm(json.dumps(data)))
        with pytest.raises(CaseGenerationError, match="initial_leads"):
            await gen.generate(uuid4(), {}, _make_session())

    async def test_markdown_fenced_json_is_parsed(self):
        fenced = "```json\n" + json.dumps(SAMPLE) + "\n```"
        gen = CaseGenerator(llm=_make_llm(fenced))
        result = await gen.generate(uuid4(), {}, _make_session())
        assert result.title == SAMPLE["title"]
