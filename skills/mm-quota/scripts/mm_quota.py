#!/usr/bin/env python3
"""
mm_quota.py — MiniMax Plus quota check, three-layer implementation.

Layer 1: headless-browse platform.minimax.io/console/usage (env-gated).
Layer 2: always-print manual fallback instructions.
Layer 3: probe the MiniMax API once, report tokens consumed by that probe
         and (when available) tokens accumulated in the local JSONL log.

All three layers are independent. Each returns a result object; the main()
function assembles the chat display block.

Never raises on user-facing paths. Internal errors are captured as
{skipped, reason} dicts and printed as one-line annotations.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import requests

# --- constants ----------------------------------------------------------------

CONSOLE_URL = "https://platform.minimax.io/console/usage"
API_MESSAGES_URL = "https://api.minimax.io/anthropic/v1/messages"
DEFAULT_MODEL = "MiniMax-M3"
PROBE_MAX_TOKENS = 1

ENV_PATH = Path("P:/.env")
ARTIFACT_DIR = Path(".claude/.artifacts")
LOG_FILENAME = "mm_quota_calls.jsonl"

# Dedicated Chrome profile for the platform.minimax.io session. Using a
# separate profile (not the user's `Default`) isolates the platform session
# from their real browsing and prevents unrelated cookies from being sent.
# Playwright's launch_persistent_context auto-creates the profile directory
# on first launch, so no manual setup of the folder is required.
MM_QUOTA_PROFILE_NAME = "mm-quota"

# How stale the HTML snapshot can be before we warn the user. The Usage
# page shows the live 5h-window percent, so even a few minutes of
# staleness can matter. Two minutes is the default "you're not really
# looking at fresh data" threshold.
HTML_STALENESS_MINUTES = 2

# --- cookie lifecycle --------------------------------------------------------
# How long a captured cookie is considered fresh. After this age, the skill
# will trigger a refresh automatically. MiniMax session cookies are short-
# lived (typically 30 days), so 7 days is a safe upper bound.
COOKIE_MAX_AGE_DAYS = 7
COOKIE_TIMESTAMP_KEY = "MINIMAX_CONSOLE_COOKIE_CAPTURED_AT"
COOKIE_KEY = "MINIMAX_CONSOLE_COOKIE"
# Heuristics: the page is "logged in" once the usage article renders.
# We use aria-label on the 5h limit row as the canonical signal.
LOGIN_SUCCESS_SELECTOR = 'article div[aria-label^="5h limit"]'
# Setup uses the user's real Chrome profile so Google recognises the browser
# as already-signed-in and doesn't trigger the anti-automation block.
# Mirrors the yt-selenium Firefox-profile discovery pattern.
CHROME_USER_DATA_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data",
    Path(os.environ.get("APPDATA", "")) / "Google" / "Chrome" / "User Data",
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome",  # macOS
    Path.home() / ".config" / "google-chrome",  # Linux
]
# Chrome profile names, in order of preference. Dedicated download profile
# is preferred (matches yt-selenium's `Profile 1` heuristic), but `Default`
# is the realistic choice for a normal user.
CHROME_PROFILE_PREFERENCE = ["mm-quota", "Default", "Profile 1", "Profile 2"]

# --- env loading --------------------------------------------------------------


def _load_env(path: Path = ENV_PATH) -> dict[str, str]:
    """Read KEY=VALUE lines from a .env file. Returns {} on any error.

    Deliberately does NOT raise — missing or unreadable .env is the common case
    for Layer 1, and the skill must degrade gracefully.
    """
    out: dict[str, str] = {}
    try:
        if not path.exists():
            return out
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as e:  # noqa: BLE001 — env loading must not crash
        print(f"[mm-quota] env load skipped: {e}", file=sys.stderr)
    return out


def _cookie_age_days(env: dict[str, str]) -> float | None:
    """Return the age of the captured cookie in days, or None if unknown."""
    ts = env.get(COOKIE_TIMESTAMP_KEY)
    if not ts:
        return None
    try:
        captured = float(ts)
    except ValueError:
        return None
    return (time.time() - captured) / 86400.0


def _cookie_is_fresh(env: dict[str, str]) -> bool:
    """True if a cookie is present AND within the freshness window."""
    if not env.get(COOKIE_KEY):
        return False
    age = _cookie_age_days(env)
    if age is None:
        # Cookie present but no timestamp — treat as fresh so we don't
        # force a re-login on first run after a manual .env edit.
        return True
    return age <= COOKIE_MAX_AGE_DAYS


def _save_cookie_to_env(cookie_value: str) -> None:
    """Persist the cookie and its capture timestamp to P:/.env.

    Preserves all other keys in the file. Creates the file if missing.
    Failure is non-fatal — the user is told what happened.
    """
    try:
        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing_lines: list[str] = []
        if ENV_PATH.exists():
            existing_lines = ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        new_ts = f"{time.time():.3f}"
        # Drop any prior lines for the keys we manage.
        keep = [ln for ln in existing_lines
                if not ln.lstrip().startswith(COOKIE_KEY + "=")
                and not ln.lstrip().startswith(COOKIE_TIMESTAMP_KEY + "=")]
        keep.append(f'{COOKIE_KEY}="{cookie_value}"')
        keep.append(f"{COOKIE_TIMESTAMP_KEY}={new_ts}")
        # Preserve trailing newline.
        ENV_PATH.write_text("\n".join(keep) + "\n", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"[mm-quota] failed to persist cookie to {ENV_PATH}: {e}", file=sys.stderr)


def _discover_chrome_user_data_dir() -> Path | None:
    """Return the first existing Chrome user-data directory, or None.

    Mirrors the yt-selenium profile-discovery heuristic: check OS-expected
    paths, return the first that exists. We don't enumerate profiles inside
    it yet — `_pick_chrome_profile` does that.
    """
    for candidate in CHROME_USER_DATA_CANDIDATES:
        try:
            if candidate.exists() and candidate.is_dir():
                return candidate
        except Exception:  # noqa: BLE001
            continue
    return None


def _pick_chrome_profile(user_data_dir: Path) -> str | None:
    """Pick the Chrome profile directory name (e.g. 'Default', 'Profile 1').

    Preference order is `CHROME_PROFILE_PREFERENCE`; if none of those exist,
    fall back to the first directory inside user_data_dir.
    """
    if not user_data_dir.exists():
        return None
    available: set[str] = set()
    try:
        for child in user_data_dir.iterdir():
            if child.is_dir():
                available.add(child.name)
    except Exception:  # noqa: BLE001
        return None
    for preferred in CHROME_PROFILE_PREFERENCE:
        if preferred in available:
            return preferred
    if available:
        return sorted(available)[0]
    return None


def _setup_capture_cookie(chrome_profile_override: str | None = None) -> dict[str, Any]:
    """Interactive setup: open a visible persistent-context browser against
    the mm-quota Chrome profile, wait for the user to log in, then capture
    and persist the session cookie (legacy/fallback path).

    The visible browser is needed only on the FIRST run (when the mm-quota
    profile doesn't exist yet). Playwright's launch_persistent_context
    auto-creates the profile directory. Once the user has logged in once
    and the platform session is stored in the profile, subsequent headless
    Layer 1 runs will inherit the session without needing --setup again.

    Returns {"source": "setup_ok", "cookie": "..."} on success,
            {"source": "setup_skipped", "reason": "..."} otherwise.
    Never raises — any failure is captured as a reason string.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:  # noqa: BLE001
        return {"source": "setup_skipped",
                "reason": f"playwright not installed ({e.__class__.__name__}); cannot run setup"}

    user_data_dir = _discover_chrome_user_data_dir()
    if user_data_dir is None:
        return {"source": "setup_skipped",
                "reason": "Chrome user-data directory not found (install Chrome)"}

    # Always target the dedicated mm-quota profile for setup. If the user
    # passes --chrome-profile explicitly, honour it (escape hatch).
    target_profile = chrome_profile_override or MM_QUOTA_PROFILE_NAME
    # Point launch_persistent_context at the profile's full path. Playwright
    # does NOT accept a `profile` kwarg; the profile is selected by the
    # user_data_dir path. Auto-created on first launch.
    target_profile_dir = user_data_dir / target_profile

    print(f"[mm-quota] SETUP: launching visible persistent context against "
          f"profile '{target_profile}' in {user_data_dir}", file=sys.stderr)
    print(f"[mm-quota] SETUP: log in to platform.minimax.io in the opened browser",
          file=sys.stderr)
    print(f"[mm-quota] SETUP: waiting up to 5 minutes for {LOGIN_SUCCESS_SELECTOR!r}",
          file=sys.stderr)
    print("[mm-quota] SETUP: once the usage bars render, the cookie is captured automatically",
          file=sys.stderr)

    try:
        with sync_playwright() as p:
            # headless=False is required for setup so the user can see and
            # interact with the login form. Persistent context means the
            # mm-quota profile's storage (cookies, local storage) is reused
            # across runs, so a single login is enough.
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(target_profile_dir),
                headless=False,
                slow_mo=200,
                channel="chrome",
            )
            try:
                page = context.new_page()
                page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_selector(LOGIN_SUCCESS_SELECTOR, timeout=300_000)
                except Exception as e:  # noqa: BLE001
                    return {"source": "setup_skipped",
                            "reason": f"login timed out ({e.__class__.__name__}); setup aborted"}
                cookies = context.cookies("https://platform.minimax.io")
                return _persist_and_return(cookies)
            finally:
                context.close()
    except Exception as e:  # noqa: BLE001
        return {"source": "setup_skipped",
                "reason": (f"setup crashed: {e.__class__.__name__}: {e}. "
                           f"Try --cookie-paste for a manual cookie entry — "
                           f"the most reliable path when the Google sign-in "
                           f"block fires against headless Playwright.")}


def _attach_to_cdp_and_capture(port: int) -> dict[str, Any]:
    """Attach Playwright to a running Chrome via CDP and capture cookies.

    Used when Chrome is already running with --remote-debugging-port open,
    which the user may have started manually (this is the most reliable path
    on Windows when Google sign-in blocks the bundled Playwright Chromium).
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:  # noqa: BLE001
        return {"source": "setup_skipped",
                "reason": f"playwright not installed ({e.__class__.__name__})"}
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            try:
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                if context.pages:
                    page = context.pages[0]
                    try:
                        page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        pass
                else:
                    page = context.new_page()
                    page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=30000)
                print(f"[mm-quota] SETUP: waiting up to 5 minutes for {LOGIN_SUCCESS_SELECTOR!r}",
                      file=sys.stderr)
                try:
                    page.wait_for_selector(LOGIN_SUCCESS_SELECTOR, timeout=300_000)
                except Exception as e:  # noqa: BLE001
                    return {"source": "setup_skipped",
                            "reason": f"login timed out ({e.__class__.__name__}); setup aborted"}
                cookies = context.cookies("https://platform.minimax.io")
                return _persist_and_return(cookies)
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:  # noqa: BLE001
        return {"source": "setup_skipped",
                "reason": (f"CDP attach failed: {e.__class__.__name__}: {e}")}


def _persist_and_return(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    """Serialize cookies as JSON, persist to .env, return the result dict.

    Extracted so both the Chrome and Chromium setup paths share the same
    persistence and result-shape logic.
    """
    if not cookies:
        return {"source": "setup_skipped",
                "reason": "no cookies captured for platform.minimax.io after login"}
    cookie_blob = json.dumps([{
        "name": c["name"],
        "value": c["value"],
        "domain": c["domain"],
        "path": c["path"],
        "expires": c.get("expires"),
        "httpOnly": c.get("httpOnly", False),
        "secure": c.get("secure", False),
        "sameSite": c.get("sameSite"),
    } for c in cookies], ensure_ascii=False)
    _save_cookie_to_env(cookie_blob)
    print(f"[mm-quota] SETUP: captured {len(cookies)} cookie(s); saved to {ENV_PATH}",
          file=sys.stderr)
    return {"source": "setup_ok", "cookie": cookie_blob, "count": len(cookies)}


# --- layer 1: console scrape --------------------------------------------------


def _layer1_console_scrape(env: dict[str, str]) -> dict[str, Any]:
    """Best-case path. Returns a result dict.

    Uses a persistent context against the dedicated mm-quota Chrome profile.
    The profile stores the platform.minimax.io session across runs, so we
    inherit the user's login without needing cookie injection.

    Success: {"source": "console_scrape", "five_hour_pct": int|None,
              "five_hour_reset": str|None, "weekly": str|None,
              "monthly": str|None, "yesterday_tokens": str|None,
              "week_tokens": str|None, "month_tokens": str|None,
              "total_tokens": str|None}
    Skipped: {"source": "skipped", "reason": str}
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:  # noqa: BLE001
        return {"source": "skipped", "reason": f"playwright not installed ({e.__class__.__name__})"}

    user_data_dir = _discover_chrome_user_data_dir()
    if user_data_dir is None:
        return {"source": "skipped",
                "reason": "Chrome user-data directory not found (install Chrome or set LOCALAPPDATA)"}

    # Point launch_persistent_context at the mm-quota profile's full path.
    # Playwright's persistent-context API does NOT accept a `profile` kwarg;
    # the profile is selected by passing its directory as `user_data_dir`.
    # The mm-quota profile is auto-created on first launch.
    profile_dir = user_data_dir / MM_QUOTA_PROFILE_NAME

    result: dict[str, Any] = {"source": "skipped", "reason": "scrape failed (see stderr)"}
    try:
        with sync_playwright() as p:
            # Persistent context inherits the platform session from the
            # mm-quota profile's storage. If the profile doesn't exist yet,
            # Playwright creates it on first launch (the user will need to
            # log in once via --setup, then subsequent runs are headless).
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=True,
                channel="chrome",
            )
            try:
                page = context.new_page()
                page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=30000)
                # The "My usage" card is the only <article> in this view.
                # Use a short wait — the persistent context already has the
                # session, so the page should render without a long delay.
                try:
                    page.wait_for_selector("article", timeout=10000)
                except Exception as wait_err:  # noqa: BLE001
                    # If the article doesn't appear, the user may not be
                    # logged in. Surface a clear hint.
                    result = {
                        "source": "skipped",
                        "reason": (f"usage article did not render "
                                   f"({wait_err.__class__.__name__}). "
                                   f"Run with --setup to log in to "
                                   f"platform.minimax.io, then retry."),
                    }
                    return result
                result = _parse_usage_article(page)
            finally:
                context.close()
    except Exception as e:  # noqa: BLE001
        result = {"source": "skipped", "reason": f"scrape error: {e.__class__.__name__}: {e}"}
        print(f"[mm-quota] layer1: {result['reason']}", file=sys.stderr)
    return result


def _parse_usage_article(page) -> dict[str, Any]:
    """Extract meter values from the rendered 'My usage' article.

    The article is a <article> with class 'rounded-lg bg-ui-card ...'. It
    contains one or more <div> rows with class 'grid grid-cols-[120px_...]'.
    Each row has an aria-label like "5h limit 89%" or "Weekly limit unlimited".
    The reset-in text is in a sibling <div class="text-[11px] ...">.

    Returns a dict with both per-meter values and the historical token
    stats from the page (Yesterday / 7d / 30d / Total).
    """
    out: dict[str, Any] = {
        "source": "console_scrape",
        "five_hour_pct": None,
        "five_hour_reset": None,
        "weekly": None,
        "monthly": None,
        "yesterday_tokens": None,
        "week_tokens": None,
        "month_tokens": None,
        "total_tokens": None,
    }

    # --- per-meter rows: aria-label is the authoritative value ----------
    meter_rows = page.query_selector_all("article div[aria-label]")
    for row in meter_rows:
        label = (row.get_attribute("aria-label") or "").strip()
        if not label:
            continue
        # 5h limit N%   or   5h limit 89% / 100%
        if label.startswith("5h limit"):
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", label)
            if m:
                out["five_hour_pct"] = int(float(m.group(1)))
            # Reset text lives in a sibling <div class="text-[11px] ...">
            reset_el = row.query_selector("div.text-\\[11px\\]")
            if reset_el:
                txt = (reset_el.inner_text() or "").strip()
                if txt:
                    out["five_hour_reset"] = txt
            # Sanity-check via the bar fill's inline style="width:N%"
            fill = row.query_selector("div[style*='width:']")
            if fill is not None:
                style = fill.get_attribute("style") or ""
                sm = re.search(r"width:\s*(\d+(?:\.\d+)?)\s*%", style)
                if sm and out["five_hour_pct"] is None:
                    out["five_hour_pct"] = int(float(sm.group(1)))
        elif label.startswith("Weekly limit"):
            if "unlimited" in label.lower():
                out["weekly"] = "Unlimited"
            else:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", label)
                if m:
                    out["weekly"] = f"{m.group(1)}%"
        elif label.startswith("Total quota") or "monthly" in label.lower():
            out["monthly"] = label

    # --- historical token stats: label-then-number pattern --------------
    # The page renders each stat as: <p>Label</p><div>114.63M</div>
    # Walk the whole body and find label/value pairs.
    for stat_label, key in [
        ("Yesterday's tokens", "yesterday_tokens"),
        ("Last 7 days", "week_tokens"),
        ("Last 30 days", "month_tokens"),
        ("Total tokens", "total_tokens"),
    ]:
        try:
            el = page.query_selector(f"text={stat_label}")
        except Exception:  # noqa: BLE001
            el = None
        if el is None:
            continue
        # Value is typically the next sibling div.
        try:
            sibling = el.evaluate_handle("e => e.nextElementSibling").as_element()
        except Exception:  # noqa: BLE001
            sibling = None
        if sibling is not None:
            try:
                val = (sibling.inner_text() or "").strip()
                if val:
                    out[key] = val
            except Exception:  # noqa: BLE001
                pass

    return out


def _safe_text(page, selector: str) -> str | None:
    """Read text content of a Playwright selector. Returns None on any error."""
    try:
        el = page.query_selector(selector)
        if el is None:
            return None
        text = el.inner_text(timeout=1000).strip()
        return text or None
    except Exception:  # noqa: BLE001
        return None


# --- layer 1b: html snapshot parser (no browser, no creds) ------------------


def _layer1b_parse_html(path: Path) -> dict[str, Any]:
    """Parse a saved usage-console HTML file. Same shape as Layer 1.

    Success: {"source": "html_snapshot", ...same keys as console_scrape...}
    Skipped: {"source": "skipped", "reason": str}
    """
    out: dict[str, Any] = {
        "source": "skipped",
        "reason": "",
        "five_hour_pct": None,
        "five_hour_reset": None,
        "weekly": None,
        "monthly": None,
        "yesterday_tokens": None,
        "week_tokens": None,
        "month_tokens": None,
        "total_tokens": None,
    }
    try:
        if not path.exists():
            out["reason"] = f"snapshot file not found: {path}"
            return out
        html = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        out["reason"] = f"snapshot read error: {e.__class__.__name__}: {e}"
        return out

    # Per-meter rows: aria-label="5h limit 89%" / "Weekly limit unlimited"
    for m in re.finditer(r'aria-label="(5h limit[^"]+|Weekly limit[^"]+)"', html):
        label = m.group(1)
        if label.startswith("5h limit"):
            pm = re.search(r"(\d+(?:\.\d+)?)\s*%", label)
            if pm:
                out["five_hour_pct"] = int(float(pm.group(1)))
            # Reset text: the next <div class="text-[11px] ..."> after the
            # 5h limit label, regardless of what other elements sit between.
            # The label span may have a tooltip (ⓘ) or other decoration after it.
            reset_m = re.search(
                r'5h limit</span>.*?<div class="text-\[11px\][^"]*">\s*(Resets in[^<]+)\s*</div>',
                html,
                flags=re.DOTALL,
            )
            if reset_m:
                out["five_hour_reset"] = reset_m.group(1).strip()
        elif label.startswith("Weekly limit"):
            if "unlimited" in label.lower():
                out["weekly"] = "Unlimited"
            else:
                pm = re.search(r"(\d+(?:\.\d+)?)\s*%", label)
                if pm:
                    out["weekly"] = f"{pm.group(1)}%"

    # Total quota (multi-line) — appears in the right column of the 5h row.
    tq_m = re.search(r'<div class="text-\[13px\][^"]*">\s*Total quota\s+(\d+(?:\.\d+)?)\s*%\s*</div>', html)
    if tq_m:
        out["monthly"] = f"Total quota {tq_m.group(1)}%"

    # Historical token stats. The page renders VALUE-then-LABEL inside a
    # stat card: <div class="text-xl ...">114.63M</div><div ...>Yesterday's tokens</div>
    # We find the label div and walk backwards to the preceding value div.
    stat_patterns = [
        ("Yesterday's tokens", "yesterday_tokens"),
        ("Last 7 days", "week_tokens"),
        ("Last 30 days", "month_tokens"),
        ("Total tokens", "total_tokens"),
        ("Peak tokens", "peak_tokens"),  # bonus field, may be unused downstream
    ]
    for label_text, key in stat_patterns:
        m = re.search(
            rf'<div class="text-\[12px\][^"]*">\s*{re.escape(label_text)}\s*</div>',
            html,
        )
        if not m:
            continue
        prefix = html[:m.start()]
        vm = re.search(
            r'<div class="text-xl[^"]*">\s*([0-9]+\.?[0-9]*[KMB]?)\s*</div>\s*$',
            prefix,
        )
        if vm:
            out[key] = vm.group(1).strip()

    # If we got at least the 5h pct, declare success.
    if out.get("five_hour_pct") is not None or out.get("weekly") is not None:
        out["source"] = "html_snapshot"
        out["reason"] = ""
    else:
        out["reason"] = "snapshot parsed but no meter values found (DOM may have changed)"
    return out


# --- layer 2: manual fallback block ------------------------------------------


def _html_staleness_hint(path: Path) -> str | None:
    """Return a one-line hint when the HTML snapshot is older than the
    staleness threshold. None when the file is fresh or unreadable.

    Designed to be informative without being noisy. The user can refresh
    by opening the live console and saving the page (Ctrl+S) — Chrome
    prompts for "Webpage, Complete" by default, which is exactly what
    we need.
    """
    try:
        mtime = path.stat().st_mtime
        age_min = (time.time() - mtime) / 60.0
    except OSError:
        return None
    if age_min <= HTML_STALENESS_MINUTES:
        return None
    if age_min < 60:
        return (f"snapshot is {age_min:.0f} min old "
                f"(>{HTML_STALENESS_MINUTES} min) — refresh in Chrome: "
                f"open {CONSOLE_URL} and Ctrl+S to overwrite "
                f"{path.name}")
    hours = age_min / 60.0
    return (f"snapshot is {hours:.1f} hr old — refresh in Chrome: "
            f"open {CONSOLE_URL} and Ctrl+S to overwrite {path.name}")


def _layer2_fallback_block() -> str:
    """Static instructions. Always returned, always the same."""
    return (
        "Fallback: open the MiniMax usage console to copy the live values.\n"
        f"  URL: {CONSOLE_URL}\n"
        "  Copy back: 5h limit (percent used + resets in), Weekly limit, Total quota."
    )


# --- layer 3: session tokens --------------------------------------------------


def _layer3_session_tokens(
    env: dict[str, str],
    session_log: Path | None,
) -> dict[str, Any]:
    """Sum tokens from the local JSONL log + a fresh probe call.

    Success: {"source": "log+probe", "input": int, "output": int, "from_log": int, "from_probe": int}
    Probe-only: {"source": "probe_only", ...}
    Skipped: {"source": "skipped", "reason": str}
    """
    api_key = env.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        return {"source": "skipped", "reason": "ANTHROPIC_AUTH_TOKEN not set"}

    from_log_in = 0
    from_log_out = 0
    log_count = 0
    if session_log is not None and session_log.exists():
        try:
            with session_log.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        u = rec.get("usage", {}) or {}
                        from_log_in += int(u.get("input_tokens", 0) or 0)
                        from_log_out += int(u.get("output_tokens", 0) or 0)
                        log_count += 1
                    except json.JSONDecodeError:
                        continue
        except Exception as e:  # noqa: BLE001
            print(f"[mm-quota] layer3 log read error: {e}", file=sys.stderr)

    # Always make a minimal probe to prove the API path works.
    probe_in, probe_out = 0, 0
    probe_error: str | None = None
    try:
        resp = requests.post(
            API_MESSAGES_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "quota probe"}],
                "max_tokens": PROBE_MAX_TOKENS,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            u = (data.get("usage") or {})
            probe_in = int(u.get("input_tokens", 0) or 0)
            probe_out = int(u.get("output_tokens", 0) or 0)
            # Best-effort log append. Failure here must not break the report.
            _append_to_log(session_log, data)
        else:
            probe_error = f"HTTP {resp.status_code}"
    except Exception as e:  # noqa: BLE001
        probe_error = f"{e.__class__.__name__}: {e}"

    total_in = from_log_in + probe_in
    total_out = from_log_out + probe_out
    result: dict[str, Any] = {
        "source": "log+probe" if log_count > 0 else "probe_only",
        "input": total_in,
        "output": total_out,
        "from_log_calls": log_count,
        "from_log_input": from_log_in,
        "from_log_output": from_log_out,
        "probe_input": probe_in,
        "probe_output": probe_out,
    }
    if probe_error:
        result["probe_error"] = probe_error
    return result


def _append_to_log(session_log: Path | None, record: dict[str, Any]) -> None:
    """Best-effort append of one API response to the JSONL log.

    Silent on failure — the user-facing report does not depend on persistence.
    """
    if session_log is None:
        return
    try:
        session_log.parent.mkdir(parents=True, exist_ok=True)
        with session_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"[mm-quota] log append error: {e}", file=sys.stderr)


def _resolve_session_log() -> Path | None:
    """Return a per-terminal JSONL log path under .claude/.artifacts, if writable.

    Returns None if the artifacts directory cannot be created — Layer 3 then
    runs probe-only and skips the persistent log.
    """
    try:
        term_id = os.environ.get("CLAUDE_TERMINAL_ID") or os.environ.get("TERMINAL_ID") or "default"
        log_dir = ARTIFACT_DIR / term_id / "mm-quota"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / LOG_FILENAME
    except Exception:  # noqa: BLE001
        return None


# --- output assembly ----------------------------------------------------------


def _format_output(layer1: dict[str, Any], layer3: dict[str, Any], fallback: str) -> str:
    lines: list[str] = []
    lines.append("MiniMax Plus — Quota Check")
    lines.append("─" * 25)

    layer1_source = layer1.get("source")
    if layer1_source in ("console_scrape", "html_snapshot"):
        pct = layer1.get("five_hour_pct")
        pct_str = f"{pct}%" if isinstance(pct, int) else "?"
        reset = layer1.get("five_hour_reset") or "?"
        lines.append(f"5h window:    {pct_str} used   ({reset})")
        lines.append(f"Weekly:       {layer1.get('weekly') or '?'}")
        lines.append(f"Monthly:      {layer1.get('monthly') or '?'}")
        if layer1_source == "console_scrape":
            source_line = "Source: console scrape"
        else:
            source_line = "Source: local HTML snapshot"
    else:
        # Layer 1 unavailable — show "??" for the three values, with the reason.
        reason = layer1.get("reason", "unknown")
        lines.append("5h window:    ??  (no data source available)")
        lines.append("Weekly:       ??  (no data source available)")
        lines.append("Monthly:      ??  (no data source available)")
        source_line = f"Source: no data — see fallback ({reason})"

    # Historical token stats — present only when Layer 1 actually got data.
    if layer1_source in ("console_scrape", "html_snapshot"):
        yest = layer1.get("yesterday_tokens") or "—"
        week = layer1.get("week_tokens") or "—"
        month = layer1.get("month_tokens") or "—"
        total = layer1.get("total_tokens") or "—"
        lines.append("")
        lines.append("Tokens used (historical):")
        lines.append(f"  Yesterday:    {yest}")
        lines.append(f"  Last 7 days:  {week}")
        lines.append(f"  Last 30 days: {month}")
        lines.append(f"  Total:        {total}")

    # Layer 3 — always present (session-local API probe + log)
    in_tok = layer3.get("input", 0)
    out_tok = layer3.get("output", 0)
    lines.append("")
    lines.append(
        f"Tokens used (session): {in_tok + out_tok:,}  "
        f"(in {in_tok:,} input / {out_tok:,} output)"
    )

    lines.append("")
    lines.append(source_line)

    if layer1_source not in ("console_scrape", "html_snapshot"):
        lines.append("")
        lines.append(fallback)

    return "\n".join(lines)


# --- main ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MiniMax Plus quota check")
    parser.add_argument("--session-only", action="store_true",
                        help="(reserved) only run layer 3")
    parser.add_argument("--no-scrape", action="store_true",
                        help="skip layer 1 (live console scrape) even if creds are configured")
    parser.add_argument("--html", type=Path, default=None,
                        help="parse a saved HTML snapshot of the console page instead of (or before) "
                             "running a live scrape. Defaults to MM_QUOTA_HTML env var, then to "
                             "C:/Users/brsth/Downloads/Usage.html if it exists.")
    parser.add_argument("--setup", action="store_true",
                        help="open a visible browser, capture the session cookie after you log in, "
                             "and persist it to P:/.env. Use this on first run or when the cookie "
                             "expires. If the Google sign-in block fires, fall back to "
                             "--cookie-paste.")
    parser.add_argument("--chrome-profile", type=str, default=None,
                        help="explicit Chrome profile name to use for --setup (e.g. 'Default', "
                             "'mm-quota'). Overrides auto-detection. The 'mm-quota' profile "
                             "is dedicated (won't conflict with your live browser).")
    parser.add_argument("--cookie-paste", action="store_true",
                        help="manually paste a cookie value (use when --setup can't bypass the "
                             "Google sign-in block). Reads from stdin until EOF. The most "
                             "reliable path on Windows + headless-Playwright + Google SSO.")
    parser.add_argument("--auto-setup", action="store_true",
                        help="(default behavior in normal runs) if the cookie is missing or stale, "
                             "automatically invoke --setup before scraping.")
    parser.add_argument("--no-auto-setup", action="store_true",
                        help="never trigger --setup automatically, even if the cookie is missing.")
    args = parser.parse_args(argv)

    # --setup: capture cookie and exit.
    if args.setup:
        result = _setup_capture_cookie(chrome_profile_override=args.chrome_profile)
        if result.get("source") == "setup_ok":
            print(f"[mm-quota] setup complete: {result.get('count', 0)} cookie(s) saved")
            return 0
        print(f"[mm-quota] setup FAILED: {result.get('reason', 'unknown')}",
              file=sys.stderr)
        return 1

    # --cookie-paste: manual cookie entry. Reads stdin until EOF.
    if args.cookie_paste:
        print("[mm-quota] PASTE: enter the cookie JSON blob (one line, then EOF / Ctrl-Z / Ctrl-D):",
              file=sys.stderr)
        try:
            raw = sys.stdin.read().strip()
        except Exception as e:  # noqa: BLE001
            print(f"[mm-quota] PASTE FAILED: {e}", file=sys.stderr)
            return 1
        if not raw:
            print("[mm-quota] PASTE FAILED: no input received", file=sys.stderr)
            return 1
        # Try to parse; if not JSON, accept as plain string (legacy single-cookie).
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("not a JSON list")
        except (json.JSONDecodeError, ValueError):
            # Plain string — wrap as legacy single-cookie.
            raw = json.dumps([{
                "name": "session", "value": raw,
                "domain": ".platform.minimax.io", "path": "/",
            }])
        _save_cookie_to_env(raw)
        print(f"[mm-quota] PASTE: cookie saved to {ENV_PATH}", file=sys.stderr)
        return 0

    env = _load_env()

    # Live Layer 1 is the always-fresh primary path. It uses a persistent
    # context against the mm-quota Chrome profile, which inherits the
    # platform.minimax.io session across runs. No cookie injection needed.
    #
    # HTML snapshot is demoted to explicit --html PATH opt-in only. The
    # --html path is preserved as a deliberate escape hatch for offline /
    # air-gapped runs; the skill no longer auto-resolves a default file
    # (that was the root cause of "89% reported as live" when an old
    # Usage.html was lying around in Downloads).

    auto_setup_enabled = not args.no_auto_setup
    layer1: dict[str, Any]
    if args.html is not None:
        html_path = args.html
        if not html_path.exists():
            print(f"[mm-quota] --html path does not exist: {html_path}",
                  file=sys.stderr)
            layer1 = {"source": "skipped",
                      "reason": f"--html file not found: {html_path}"}
        else:
            layer1 = _layer1b_parse_html(html_path)
    elif args.no_scrape or args.session_only:
        layer1 = {"source": "skipped", "reason": "--no-scrape/--session-only"}
    else:
        # Auto-setup decision: only relevant on the live Layer 1 path.
        # The cookie is no longer required (persistent context reads it
        # from the mm-quota profile), but we still keep this block for
        # the --cookie-paste fallback path. If the persistent context
        # fails (e.g., profile missing on first run), the layer1 returned
        # below will surface a clear hint to run --setup.
        if auto_setup_enabled and not _cookie_is_fresh(env):
            if not env.get(COOKIE_KEY):
                # No cookie in .env. The persistent context will work
                # against an existing mm-quota profile (created by a prior
                # --setup run). If the profile doesn't exist, the scrape
                # will return a clear "article did not render" hint.
                pass
        layer1 = _layer1_console_scrape(env)

    # If the live scrape failed because the persistent context hit a
    # sign-in form (article didn't render), and auto-setup is enabled,
    # trigger one setup retry. The user logs in once; subsequent runs
    # inherit the session from the mm-quota profile.
    if (
        layer1.get("source") == "skipped"
        and "did not render" in (layer1.get("reason") or "")
        and auto_setup_enabled
        and not args.no_scrape
        and args.html is None
    ):
        print("[mm-quota] live scrape hit a sign-in form — running automatic setup",
              file=sys.stderr)
        setup_result = _setup_capture_cookie()
        if setup_result.get("source") == "setup_ok":
            layer1 = _layer1_console_scrape(_load_env())

    layer3 = _layer3_session_tokens(env, _resolve_session_log())
    fallback = _layer2_fallback_block()

    print(_format_output(layer1, layer3, fallback))

    # If the user explicitly opted into --html, surface a staleness hint
    # so they know to refresh the snapshot. (Not used in the default path
    # anymore — live Layer 1 is always fresh.)
    if args.html is not None and args.html.exists():
        hint = _html_staleness_hint(args.html)
        if hint:
            print(f"\n[mm-quota] {hint}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
