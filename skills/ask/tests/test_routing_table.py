"""Tests for ask/lib/routing_table.py."""

import pytest

from ask.lib.routing_table import route


class TestExplicitRouting:
    """Tests for explicit command mentions."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("/design", "/design"),
            ("/rca", "/rca"),
            ("/debug", "/debug"),
            ("/search", "/search"),
            ("/analyze", "/analyze"),
            ("/breakdown", "/breakdown"),
            ("/truth", "/truth"),
            ("/build", "/build"),
            ("/evolve", "/evolve"),
            ("/plan", "/plan"),
            ("/adf", "/adf"),
            ("/tdd", "/tdd"),
            ("/test", "/test"),
            ("/qa", "/qa"),
            ("/discover", "/discover"),
            ("/research", "/research"),
            ("/doc", "/doc"),
            ("/cwo", "/cwo"),
        ],
    )
    def test_explicit_command(self, input_text: str, expected: str) -> None:
        assert route(input_text) == expected

    def test_explicit_command_case_insensitive(self) -> None:
        assert route("/ARCH") == "/design"
        assert route("/RCA") == "/rca"
        assert route("/Debug") == "/debug"


class TestIntentBasedRouting:
    """Tests for implicit intent patterns."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            # Architecture
            ("how should I design this service", "/design"),
            ("what architecture pattern", "/design"),
            ("is creating a new module justified", "/adf"),
            ("should I extract this function", "/adf"),
            # RCA
            ("why is this failing", "/rca"),
            ("why does this keep breaking", "/rca"),
            # Truth
            ("did I actually fix it", "/truth"),
            ("prove it", "/truth"),
            ("verify my claims", "/truth"),
            # Planning
            ("help me plan this project", "/breakdown"),
            ("break down this task", "/breakdown"),
            # Research
            ("research how OAuth works", "/research"),
            ("learn about Python asyncio", "/research"),
            ("how does FastAPI work", "/research"),
            # Analyze
            ("analyze this code quality", "/analyze"),
            ("improve this code", "/analyze"),
            # Discover
            ("discover patterns in this codebase", "/discover"),
            ("what exists in the codebase", "/discover"),
            # Search
            ("what did we discuss about auth", "/search"),
            # Documentation
            ("document this code", "/doc"),
            # Build
            ("build a new feature", "/build"),
            ("implement a login flow", "/build"),
            # Evolve
            ("modernize this codebase", "/evolve"),
            ("refactor the auth module", "/evolve"),
            # QA
            ("run QA on this feature", "/qa"),
            ("end to end test", "/qa"),
        ],
    )
    def test_intent_routing(self, input_text: str, expected: str) -> None:
        assert route(input_text) == expected


class TestAmbiguousAndNoMatch:
    """Tests for ambiguous or non-matching inputs."""

    @pytest.mark.parametrize(
        "input_text",
        [
            "",
            "   ",
            "/ask",
            "/ask help",
            "/ask list",
            "hello world",
            "just testing",
        ],
    )
    def test_no_route(self, input_text: str) -> None:
        assert route(input_text) is None


class TestPriorityExplicitOverImplicit:
    """Explicit command mentions beat implicit intent patterns."""

    def test_explicit_mention_wins(self) -> None:
        # Even though the text contains intent keywords,
        # an explicit command mention should win.
        result = route("/design design a service")
        assert result == "/design"
