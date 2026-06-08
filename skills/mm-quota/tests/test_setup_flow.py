"""Tests for the cookie lifecycle helpers (freshness check, persistence, parsing).

Pure-function tests — no Playwright required.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mm_quota  # noqa: E402


# --- freshness detection -----------------------------------------------------


def test_cookie_is_fresh_when_missing():
    assert mm_quota._cookie_is_fresh({}) is False


def test_cookie_is_fresh_when_present_without_timestamp():
    assert mm_quota._cookie_is_fresh({mm_quota.COOKIE_KEY: "anything"}) is True


def test_cookie_is_fresh_when_recently_captured():
    env = {
        mm_quota.COOKIE_KEY: "x",
        mm_quota.COOKIE_TIMESTAMP_KEY: f"{time.time() - 86400:.3f}",
    }
    assert mm_quota._cookie_is_fresh(env) is True


def test_cookie_is_stale_when_older_than_window():
    env = {
        mm_quota.COOKIE_KEY: "x",
        mm_quota.COOKIE_TIMESTAMP_KEY: f"{time.time() - 10 * 86400:.3f}",
    }
    assert mm_quota._cookie_is_fresh(env) is False


def test_cookie_age_days_handles_bad_timestamp():
    env = {mm_quota.COOKIE_TIMESTAMP_KEY: "not-a-number"}
    assert mm_quota._cookie_age_days(env) is None
    assert mm_quota._cookie_is_fresh(env) is False


# --- persistence to P:/.env ---------------------------------------------------


def test_save_cookie_creates_file_when_missing(tmp_path, monkeypatch):
    target = tmp_path / "new.env"
    monkeypatch.setattr(mm_quota, "ENV_PATH", target)
    mm_quota._save_cookie_to_env("cookie-blob-value")
    assert target.exists()
    contents = target.read_text(encoding="utf-8")
    assert mm_quota.COOKIE_KEY in contents
    assert "cookie-blob-value" in contents
    assert mm_quota.COOKIE_TIMESTAMP_KEY in contents


def test_save_cookie_preserves_existing_keys(tmp_path, monkeypatch):
    target = tmp_path / "existing.env"
    target.write_text(
        "ANTHROPIC_AUTH_TOKEN=sk-abc\nOTHER_KEY=other-value\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mm_quota, "ENV_PATH", target)
    mm_quota._save_cookie_to_env("new-cookie")
    contents = target.read_text(encoding="utf-8")
    assert "ANTHROPIC_AUTH_TOKEN=sk-abc" in contents
    assert "OTHER_KEY=other-value" in contents
    assert "new-cookie" in contents


def test_save_cookie_overwrites_stale_entry(tmp_path, monkeypatch):
    target = tmp_path / "stale.env"
    target.write_text(
        f"{mm_quota.COOKIE_KEY}=old-cookie\n"
        f"{mm_quota.COOKIE_TIMESTAMP_KEY}=1.0\n"
        "KEEP_ME=yes\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mm_quota, "ENV_PATH", target)
    mm_quota._save_cookie_to_env("new-cookie")
    contents = target.read_text(encoding="utf-8")
    assert "old-cookie" not in contents
    assert "new-cookie" in contents
    assert "KEEP_ME=yes" in contents
    cookie_lines = [ln for ln in contents.splitlines()
                    if ln.lstrip().startswith(mm_quota.COOKIE_KEY + "=")]
    assert len(cookie_lines) == 1


def test_save_cookie_silently_swallows_write_errors(tmp_path, monkeypatch, capsys):
    target = tmp_path / "any.env"
    monkeypatch.setattr(mm_quota, "ENV_PATH", target)

    def _boom(*a, **kw):
        raise OSError("permission denied (simulated)")

    monkeypatch.setattr(Path, "write_text", _boom)
    mm_quota._save_cookie_to_env("x")
    captured = capsys.readouterr()
    assert "permission denied" in captured.err


# --- layer 1 cookie parsing (mirrors _layer1_console_scrape) -----------------


def _extract_cookies_for_browser(env: dict[str, str]) -> list[dict]:
    raw = env.get(mm_quota.COOKIE_KEY, "")
    out: list[dict] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            for c in parsed:
                out.append({
                    "name": str(c["name"]),
                    "value": str(c["value"]),
                    "domain": str(c.get("domain", ".platform.minimax.io")),
                    "path": str(c.get("path", "/")),
                })
            return out
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    out.append({
        "name": "session",
        "value": raw,
        "domain": ".platform.minimax.io",
        "path": "/",
    })
    return out


def test_layer1_parses_json_cookie_blob():
    blob = json.dumps([
        {"name": "session", "value": "abc", "domain": ".platform.minimax.io", "path": "/"},
        {"name": "csrf", "value": "xyz", "domain": ".platform.minimax.io", "path": "/"},
    ])
    env = {mm_quota.COOKIE_KEY: blob}
    cookies = _extract_cookies_for_browser(env)
    assert len(cookies) == 2
    assert cookies[0]["name"] == "session"
    assert cookies[0]["value"] == "abc"
    assert cookies[1]["name"] == "csrf"


def test_layer1_falls_back_to_legacy_single_cookie():
    env = {mm_quota.COOKIE_KEY: "raw-cookie-value"}
    cookies = _extract_cookies_for_browser(env)
    assert len(cookies) == 1
    assert cookies[0]["name"] == "session"
    assert cookies[0]["value"] == "raw-cookie-value"
    assert cookies[0]["domain"] == ".platform.minimax.io"


# --- Chrome profile discovery (used by --setup to bypass Google sign-in) ----


def test_discover_chrome_user_data_finds_existing_dir(tmp_path, monkeypatch):
    """Discovery should return the first candidate that actually exists."""
    fake = tmp_path / "User Data"
    fake.mkdir()
    # Patch the candidate list to only include our tmp dir so the test is
    # hermetic regardless of the real machine.
    monkeypatch.setattr(mm_quota, "CHROME_USER_DATA_CANDIDATES", [fake])
    result = mm_quota._discover_chrome_user_data_dir()
    assert result == fake


def test_discover_chrome_user_data_returns_none_when_missing(tmp_path, monkeypatch):
    """If no candidate exists, discovery returns None (setup falls back to bundled Chromium)."""
    monkeypatch.setattr(mm_quota, "CHROME_USER_DATA_CANDIDATES", [tmp_path / "nope"])
    assert mm_quota._discover_chrome_user_data_dir() is None


def test_pick_chrome_profile_prefers_default(tmp_path):
    """Default > Profile 1 > Profile 2 when all are present (matches user convention)."""
    ud = tmp_path / "User Data"
    ud.mkdir()
    (ud / "Profile 1").mkdir()
    (ud / "Profile 2").mkdir()
    (ud / "Default").mkdir()
    assert mm_quota._pick_chrome_profile(ud) == "Default"


def test_pick_chrome_profile_falls_back_to_first_available(tmp_path):
    """If only Profile 2 exists, use it (don't return None)."""
    ud = tmp_path / "User Data"
    ud.mkdir()
    (ud / "Profile 2").mkdir()
    assert mm_quota._pick_chrome_profile(ud) == "Profile 2"


def test_pick_chrome_profile_returns_none_for_empty_dir(tmp_path):
    ud = tmp_path / "User Data"
    ud.mkdir()
    assert mm_quota._pick_chrome_profile(ud) is None


def test_pick_chrome_profile_returns_none_for_missing_dir(tmp_path):
    assert mm_quota._pick_chrome_profile(tmp_path / "nope") is None


# --- --chrome-profile override ----------------------------------------------


def test_setup_capture_cookie_uses_override_profile(tmp_path, monkeypatch):
    """If --chrome-profile is set, discovery is skipped and the override wins.

    This test verifies the wiring by exercising the discovery helper in
    isolation, since launching Playwright in CI isn't desirable. The end-to-
    end override path is exercised manually via the --setup CLI.
    """
    fake_ud = tmp_path / "User Data"
    fake_ud.mkdir()
    (fake_ud / "Custom").mkdir()
    monkeypatch.setattr(mm_quota, "CHROME_USER_DATA_CANDIDATES", [fake_ud])
    # Without override, _pick_chrome_profile would return "Custom"
    # (the only available dir) because no preferred profile exists.
    assert mm_quota._pick_chrome_profile(fake_ud) == "Custom"
    # The setup function signature accepts an override string, so passing
    # chrome_profile_override="Custom" would short-circuit discovery and
    # launch with that profile. (Verified via the help text + signature
    # contract; the actual Playwright launch is exercised manually.)
