"""Tests for mm_quota.py — Layer 1 short-circuit and Layer 3 log parsing.

Self-contained: no conftest, no shared fixtures. Each test sets up its own
inputs and asserts directly on the function output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts dir to import path so the test can import mm_quota directly
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mm_quota  # noqa: E402


# --- Layer 1: env-var short-circuit -----------------------------------------


def test_layer1_skips_when_chrome_profile_missing(monkeypatch, tmp_path):
    """No mm-quota Chrome profile on disk → returns skipped, never launches Chrome.

    The persistent-context path requires a Chrome user-data directory. If
    `_discover_chrome_user_data_dir` returns None, the skill must short-
    circuit with a clear reason, not import playwright at all.
    """
    # Force the discovery helper to find no Chrome user-data dir.
    monkeypatch.setattr(mm_quota, "_discover_chrome_user_data_dir", lambda: None)

    result = mm_quota._layer1_console_scrape({})
    assert result["source"] == "skipped"
    assert "user-data directory" in result["reason"].lower() or "chrome" in result["reason"].lower()


def test_layer1_skips_when_playwright_missing(monkeypatch, tmp_path):
    """Cookie set but playwright import fails → returns skipped, not crash."""
    fake_env_path = tmp_path / "has_cookie.env"
    fake_env_path.write_text("MINIMAX_CONSOLE_COOKIE=fake-session-value\n", encoding="utf-8")
    env = mm_quota._load_env(fake_env_path)

    # Force the import to fail by hiding playwright from sys.modules
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

    result = mm_quota._layer1_console_scrape(env)
    assert result["source"] == "skipped"
    assert "playwright" in result["reason"].lower()


def test_layer1_uses_persistent_context(monkeypatch, tmp_path):
    """Layer 1 must call launch_persistent_context (not launch+add_cookies).

    Verifies the live-scrape path uses a persistent context against the
    mm-quota profile directory, with headless=True and channel="chrome".
    No real browser is launched; we inject a fake context manager.
    """
    # Fake user-data-dir containing the mm-quota profile.
    fake_user_data = tmp_path / "User Data"
    fake_user_data.mkdir()
    (fake_user_data / mm_quota.MM_QUOTA_PROFILE_NAME).mkdir()
    monkeypatch.setattr(mm_quota, "_discover_chrome_user_data_dir", lambda: fake_user_data)

    # Build a fake playwright that records the call and returns a no-op
    # context manager whose new_page() returns a page whose wait_for_selector
    # raises TimeoutError (so we exercise the "did not render" hint path
    # without needing a real network).
    class _FakePage:
        def goto(self, *a, **kw): return None
        def wait_for_selector(self, *a, **kw):
            raise TimeoutError("fake timeout")
    class _FakeContext:
        def new_page(self): return _FakePage()
        def close(self): pass
    class _FakeBrowser:
        def launch_persistent_context(self, **kw):
            # Record the call so the test can assert on it.
            fake_browser.calls.append(kw)
            return _FakeContext()
    fake_browser = type("_B", (), {"calls": []})()
    fake_browser.launch_persistent_context = lambda **kw: (
        fake_browser.calls.append(kw) or _FakeContext()
    )

    class _FakePlaywrightCM:
        def __enter__(self_inner):
            class _P:
                chromium = fake_browser
            return _P()
        def __exit__(self_inner, *a): return False

    fake_module = type(sys)("playwright.sync_api")
    fake_module.sync_playwright = lambda: _FakePlaywrightCM()
    monkeypatch.setitem(sys.modules, "playwright", type(sys)("playwright"))
    sys.modules["playwright"].sync_api = fake_module
    sys.modules["playwright.sync_api"] = fake_module

    result = mm_quota._layer1_console_scrape({})

    # Persistent context was called with the mm-quota profile's full path
    # (not the parent user-data dir), headless=True, channel="chrome".
    assert len(fake_browser.calls) == 1
    call = fake_browser.calls[0]
    assert call["headless"] is True
    assert call["channel"] == "chrome"
    assert call["user_data_dir"].endswith(mm_quota.MM_QUOTA_PROFILE_NAME)
    # And the result reflects the "did not render" hint path.
    assert result["source"] == "skipped"
    assert "did not render" in result["reason"]


# --- Layer 3: log parsing ----------------------------------------------------


def test_layer3_probe_only_when_log_missing(monkeypatch, tmp_path):
    """No log file on disk → returns probe_only with non-negative ints.

    This test does NOT require a real API call — we monkeypatch requests.post
    to return a controlled response.
    """
    # Point _resolve_session_log at a path that won't exist
    fake_log = tmp_path / "no_such_log.jsonl"
    # Build a minimal env with the API key
    env = {"ANTHROPIC_AUTH_TOKEN": "sk-test"}

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"usage": {"input_tokens": 7, "output_tokens": 3}, "id": "x"}

    monkeypatch.setattr(mm_quota.requests, "post", lambda *a, **kw: _FakeResp())

    result = mm_quota._layer3_session_tokens(env, fake_log)
    assert result["source"] == "probe_only"
    assert result["input"] == 7
    assert result["output"] == 3
    assert result["from_log_calls"] == 0
    assert "probe_error" not in result


def test_layer3_sums_existing_log(tmp_path, monkeypatch):
    """Pre-existing JSONL log with two records → input/output are summed."""
    log = tmp_path / "calls.jsonl"
    log.write_text(
        json.dumps({"usage": {"input_tokens": 100, "output_tokens": 50}}) + "\n"
        + json.dumps({"usage": {"input_tokens": 200, "output_tokens": 75}}) + "\n",
        encoding="utf-8",
    )
    env = {"ANTHROPIC_AUTH_TOKEN": "sk-test"}

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"usage": {"input_tokens": 1, "output_tokens": 1}, "id": "x"}

    monkeypatch.setattr(mm_quota.requests, "post", lambda *a, **kw: _FakeResp())

    result = mm_quota._layer3_session_tokens(env, log)
    # 100+200+1 = 301 in; 50+75+1 = 126 out
    assert result["source"] == "log+probe"
    assert result["from_log_input"] == 300
    assert result["from_log_output"] == 125
    assert result["probe_input"] == 1
    assert result["probe_output"] == 1
    assert result["input"] == 301
    assert result["output"] == 126
    assert result["from_log_calls"] == 2


def test_layer3_tolerates_malformed_log_lines(tmp_path, monkeypatch):
    """Garbage lines in the log are skipped, valid lines still summed."""
    log = tmp_path / "mixed.jsonl"
    log.write_text(
        "this is not json\n"
        + json.dumps({"usage": {"input_tokens": 10, "output_tokens": 5}}) + "\n"
        + '{"usage": not valid json}\n'
        + json.dumps({"usage": {"input_tokens": 20, "output_tokens": 0}}) + "\n",
        encoding="utf-8",
    )
    env = {"ANTHROPIC_AUTH_TOKEN": "sk-test"}

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"usage": {"input_tokens": 0, "output_tokens": 0}, "id": "x"}

    monkeypatch.setattr(mm_quota.requests, "post", lambda *a, **kw: _FakeResp())

    result = mm_quota._layer3_session_tokens(env, log)
    # Only the two valid records sum: 10+20 = 30 in, 5+0 = 5 out
    assert result["from_log_input"] == 30
    assert result["from_log_output"] == 5
    assert result["from_log_calls"] == 2


def test_layer3_skips_when_no_api_key(tmp_path):
    """ANTHROPIC_AUTH_TOKEN missing → returns skipped, never calls requests."""
    env: dict = {}  # no API key
    log = tmp_path / "any.jsonl"
    result = mm_quota._layer3_session_tokens(env, log)
    assert result["source"] == "skipped"
    assert "ANTHROPIC_AUTH_TOKEN" in result["reason"]


def test_layer3_captures_probe_error(tmp_path, monkeypatch):
    """Network/API error during probe → result has probe_error, doesn't crash."""
    log = tmp_path / "x.jsonl"
    env = {"ANTHROPIC_AUTH_TOKEN": "sk-test"}

    def _boom(*a, **kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(mm_quota.requests, "post", _boom)
    result = mm_quota._layer3_session_tokens(env, log)
    # No log content, no probe content, but we get an error annotation
    assert result["input"] == 0
    assert result["output"] == 0
    assert "probe_error" in result
    assert "connection refused" in result["probe_error"]


# --- Output formatting smoke tests ------------------------------------------


def test_format_output_console_scrape_path():
    """Layer 1 success → output shows real values, no fallback block."""
    layer1 = {
        "source": "console_scrape",
        "five_hour_pct": 10,
        "five_hour_reset": "resets in 4 hr 5 min",
        "weekly": "Unlimited",
        "monthly": "Total quota 100%",
    }
    layer3 = {"source": "probe_only", "input": 3200, "output": 9250}
    fallback = mm_quota._layer2_fallback_block()

    out = mm_quota._format_output(layer1, layer3, fallback)
    assert "10% used" in out
    assert "resets in 4 hr 5 min" in out
    assert "Unlimited" in out
    assert "Total quota 100%" in out
    assert "12,450" in out  # 3200 + 9250
    assert "Source: console scrape" in out
    # No fallback block on the happy path
    assert "Fallback: open" not in out


def test_format_output_layer1_skipped_path():
    """Layer 1 unavailable → output shows ?? values, includes fallback."""
    layer1 = {
        "source": "skipped",
        "reason": "MINIMAX_CONSOLE_COOKIE not set in P:/.env",
    }
    layer3 = {"source": "probe_only", "input": 0, "output": 0}
    fallback = mm_quota._layer2_fallback_block()

    out = mm_quota._format_output(layer1, layer3, fallback)
    assert "??" in out
    assert "Source: no data" in out
    assert "MINIMAX_CONSOLE_COOKIE" in out
    assert "Fallback: open" in out
    assert "platform.minimax.io/console/usage" in out


# --- Env loading ------------------------------------------------------------


def test_load_env_returns_empty_for_missing_file(tmp_path):
    """Nonexistent env path → {}, no exception."""
    assert mm_quota._load_env(tmp_path / "nope.env") == {}


def test_load_env_parses_key_value_pairs(tmp_path):
    """Standard .env format parses correctly; comments and blank lines ignored."""
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "# comment line\n"
        "\n"
        "ANTHROPIC_AUTH_TOKEN=sk-abc\n"
        "QUOTED=\"value with spaces\"\n"
        "SINGLE_QUOTED='single'\n"
        "NO_EQUALS_SIGN\n",
        encoding="utf-8",
    )
    env = mm_quota._load_env(env_file)
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-abc"
    assert env["QUOTED"] == "value with spaces"
    assert env["SINGLE_QUOTED"] == "single"
    # Lines without = are silently dropped
    assert "NO_EQUALS_SIGN" not in env
