"""Tests für Onboarding-Hilfsfunktionen in backend.bot.main."""
import pytest
from unittest.mock import MagicMock

import discord

from backend.bot.main import _dm_check, _parse_city, _parse_intensity, _parse_list


def _make_message(*, author_id: int, channel_id: int) -> MagicMock:
    msg = MagicMock(spec=discord.Message)
    msg.author.id = author_id
    msg.channel.id = channel_id
    return msg


class TestParseCity:
    def test_comma_separated(self):
        city, hood = _parse_city("Berlin, Mitte")
        assert city == "Berlin"
        assert hood == "Mitte"

    def test_parentheses(self):
        city, hood = _parse_city("Berlin (Prenzlauer Berg)")
        assert city == "Berlin"
        assert hood == "Prenzlauer Berg"

    def test_slash_separated(self):
        city, hood = _parse_city("München/Schwabing")
        assert city == "München"
        assert hood == "Schwabing"

    def test_plain_city_no_neighborhood(self):
        city, hood = _parse_city("Hamburg")
        assert city == "Hamburg"
        assert hood is None

    def test_strips_whitespace(self):
        city, hood = _parse_city("  Köln , Ehrenfeld  ")
        assert city == "Köln"
        assert hood == "Ehrenfeld"

    def test_parentheses_strips_closing(self):
        city, hood = _parse_city("Frankfurt (Sachsenhausen)")
        assert hood == "Sachsenhausen"


class TestParseIntensity:
    @pytest.mark.parametrize("answer", ["wenig", "low", "gering", "kaum", "1"])
    def test_low_keywords(self, answer):
        assert _parse_intensity(answer) == "low"

    @pytest.mark.parametrize("answer", ["stark", "high", "viel", "voll", "sehr", "3"])
    def test_high_keywords(self, answer):
        assert _parse_intensity(answer) == "high"

    @pytest.mark.parametrize("answer", ["mittel", "medium", "normal", "2", "okay", "irgendwie"])
    def test_medium_fallback(self, answer):
        assert _parse_intensity(answer) == "medium"

    def test_case_insensitive_high(self):
        assert _parse_intensity("STARK") == "high"

    def test_case_insensitive_low(self):
        assert _parse_intensity("WENIG") == "low"

    def test_leading_trailing_whitespace(self):
        assert _parse_intensity("  stark  ") == "high"


class TestParseList:
    def test_comma_separated(self):
        assert _parse_list("Anna, Bob, Clara") == ["Anna", "Bob", "Clara"]

    def test_semicolon_separated(self):
        assert _parse_list("Anna; Bob") == ["Anna", "Bob"]

    def test_newline_separated(self):
        assert _parse_list("Anna\nBob") == ["Anna", "Bob"]

    def test_mixed_separators(self):
        assert _parse_list("Anna, Bob; Clara") == ["Anna", "Bob", "Clara"]

    def test_filters_empty_entries(self):
        assert _parse_list("Anna, , Bob") == ["Anna", "Bob"]

    def test_single_entry(self):
        assert _parse_list("Anna") == ["Anna"]

    def test_empty_string(self):
        assert _parse_list("") == []

    def test_strips_whitespace_per_item(self):
        result = _parse_list("  Anna  ,  Bob  ")
        assert result == ["Anna", "Bob"]


class TestDmCheck:
    def test_matches_correct_user_and_channel(self):
        check = _dm_check(user_id=123, channel_id=456)
        msg = _make_message(author_id=123, channel_id=456)
        assert check(msg) is True

    def test_rejects_wrong_user(self):
        check = _dm_check(user_id=123, channel_id=456)
        msg = _make_message(author_id=999, channel_id=456)
        assert check(msg) is False

    def test_rejects_wrong_channel(self):
        check = _dm_check(user_id=123, channel_id=456)
        msg = _make_message(author_id=123, channel_id=999)
        assert check(msg) is False

    def test_rejects_both_wrong(self):
        check = _dm_check(user_id=123, channel_id=456)
        msg = _make_message(author_id=999, channel_id=999)
        assert check(msg) is False

    def test_independent_closures(self):
        check_a = _dm_check(user_id=1, channel_id=10)
        check_b = _dm_check(user_id=2, channel_id=20)
        msg = _make_message(author_id=1, channel_id=10)
        assert check_a(msg) is True
        assert check_b(msg) is False
