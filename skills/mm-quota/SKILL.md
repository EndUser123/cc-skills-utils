---
name: mm-quota
version: "1.2.0"
status: "stable"
category: infrastructure
enforcement: advisory
allowed_first_tools:
  - Bash
description: Report MiniMax Plus plan quota — 5h rolling window, weekly, monthly — and session token usage, with one-time Chrome profile login and graceful fallback when console credentials are not configured.
triggers:
  - /mm-quota
workflow_steps:
  - load_env: 'Read P:/.env to obtain MINIMAX_CONSOLE_COOKIE (and its capture timestamp), ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL. Never raise; missing vars become None.'
  - auto_setup_check: 'If the live scrape hits a sign-in form (article did not render), automatically invoke the visible-browser setup flow once against the dedicated mm-quota Chrome profile. The user logs in once; the session is persisted to the mm-quota profile directory for all future runs.'
  - layer1_console_scrape: 'Launch a persistent context against the mm-quota Chrome profile (headless, channel=chrome). The profile inherits the platform.minimax.io session across runs, so no cookie injection is needed. On any failure, return {skipped, reason}; never raise to caller.'
  - layer1b_html_opt_in: 'Only when the user passes --html PATH. Parse a saved HTML snapshot of the console page. This is an offline / air-gapped escape hatch, not a default path.'
  - layer2_fallback_block: 'Always print a clearly-labeled block with the console URL and the three values to copy. This block is informational; the user only acts on it if Layer 1 returned no data.'
  - layer3_session_tokens: 'Read the local MiniMax API call JSONL log; sum usage.input_tokens and usage.output_tokens for the current session. If no log exists, make a single max_tokens=1 probe and report the (zero) tokens it consumed.'
  - assemble_output: 'Render the three-layer output as a single chat display block with explicit per-layer Source: lines and a Fallback: section appended when Layer 1 fell through.'
---

# /mm-quota — MiniMax Plus Quota Check

One-command readout of MiniMax Plus plan quota state. Surfaces the 5-hour rolling window, weekly window, monthly allotment, and tokens consumed in the current session. Degrades gracefully — always returns useful data even if the fully-automated console scrape is unavailable.

## ⚡ EXECUTION DIRECTIVE

**When /mm-quota is invoked, execute the quota script:**

```bash
python P://packages/cc-skills-utils/skills/mm-quota/scripts/mm_quota.py
```

**Optional flags:**

```bash
# First run (or when the cookie expires): open a visible browser, log in
# once, capture the session cookie, and persist it to P:/.env.
python .../mm_quota.py --setup

# Probe the API and report token count for the current session only
python .../mm_quota.py --session-only

# Skip the console scrape attempt; run layers 2 and 3 only
python .../mm_quota.py --no-scrape

# Disable automatic setup retry (default: auto-setup is on)
python .../mm_quota.py --no-auto-setup
```

## First Run & Cookie Lifecycle

The skill uses a dedicated Chrome profile (`mm-quota`) to hold the `platform.minimax.io` session. This isolates the platform session from your real browser and lets subsequent headless runs inherit the session without cookie injection.

**First run (one-time, ~30 seconds):**

1. Run `python .../mm_quota.py` (or `/mm-quota`).
2. The skill detects there's no `mm-quota` Chrome profile yet, automatically opens a **visible** Chrome window against the new profile, and prints:
   ```
   [mm-quota] live scrape hit a sign-in form — running automatic setup
   [mm-quota] SETUP: launching visible persistent context against profile 'mm-quota' …
   [mm-quota] SETUP: log in to platform.minimax.io in the opened browser
   ```
3. Log in to `platform.minimax.io` in the opened window. Once the usage bars render, the skill captures the session into the `mm-quota` profile and closes the browser.

**Every subsequent run:**

- The skill launches a **headless** persistent context against the existing `mm-quota` profile, navigates to the console, and scrapes the live numbers. No browser window appears. No cookies are injected from `.env` — the profile's own storage supplies the session.

**To force a re-login** (e.g., the platform's session expired): run with `--setup`. To disable auto-setup entirely: run with `--no-auto-setup`.

**HTML snapshot escape hatch** (offline / air-gapped runs): pass `--html PATH` to parse a saved HTML file instead of scraping live. This is no longer the default — only opt in explicitly:

```bash
python .../mm_quota.py --html path/to/saved/Usage.html
```

## Three Layers, in Order

The skill always runs all three layers. Each layer is independent and degrades independently.

### Layer 1 — Console scrape (best case, default path)

The script launches a **persistent Chromium context** against the dedicated `mm-quota` Chrome profile (`headless=True`, `channel="chrome"`). The profile's storage (cookies, local storage, IndexedDB) inherits the `platform.minimax.io` session across runs — no cookie injection from `.env` is needed. If the profile doesn't exist yet, Playwright auto-creates it on first launch; the skill detects the sign-in form response and falls back to `--setup` (one-time visible-browser login).

The scrape reads:

- 5h window: percent used, time-until-reset
- Weekly: percent used or "Unlimited"
- Monthly total: 100% indicator and any visible consumed number
- Historical token stats: Yesterday / 7d / 30d / Total

If the persistent context can't be created (e.g., Chrome not installed, no `LOCALAPPDATA`), Layer 1 is skipped with a one-line reason and the next layer takes over. No crash, no exception propagation.

### Layer 2 — Manual fallback (always printed, action optional)

Always emitted as a clearly-labeled block. The user reads it only if Layer 1 returned nothing. The block tells the user which URL to open and which three numbers to copy back. No data is fabricated.

### Layer 3 — Session token usage (always-on, no credentials)

Reads the local MiniMax API call log (JSONL produced by the `cc-mm` provider config) and sums `usage.input_tokens` and `usage.output_tokens` for calls in the current session. If no log exists, makes a single minimal probe call (`max_tokens=1`) and reports the tokens it consumed (always zero or near-zero, but proves the wiring works).

Reports the token sum alongside Layer 1/2 data, formatted as:

```
Tokens used (session): 12,450  (in 3,200 input / 9,250 output)
```

## Output Format

```
MiniMax Plus — Quota Check
─────────────────────────
5h window:    10% used   (resets in 4 hr 5 min)
Weekly:       Unlimited
Monthly:      100% total allotment
Tokens used (session): 12,450  (in 3,200 input / 9,250 output)

Source: console scrape
```

If Layer 1 fell through, the `Source` line changes to `Source: console cookie not set — see fallback` and a `Fallback:` block is appended with the URL and the three values to copy.

## Configuration

The skill works out of the box for Layer 1 once the `mm-quota` Chrome profile has been seeded (one-time login during the first `/mm-quota` run). `.env` values are only needed for the Layer 3 probe and the `--cookie-paste` fallback.

| Env var | Effect | Required for |
|---------|--------|--------------|
| `ANTHROPIC_AUTH_TOKEN` | API key, used by Layer 3 probe and by `cc-mm` | Layer 3 (probe path) |
| `ANTHROPIC_BASE_URL` | MiniMax Anthropic-compatible endpoint | Layer 3 |
| `MINIMAX_CONSOLE_COOKIE` | Captured session cookies (JSON blob) for `platform.minimax.io` | `--cookie-paste` fallback path (not used by the default Layer 1) |
| `MINIMAX_CONSOLE_COOKIE_CAPTURED_AT` | Unix timestamp of last successful capture | Auto-managed; 7-day freshness window |

Set these in `P:/.env`, not in process environment. The skill reads `.env` directly to keep credentials out of subprocess environments.

## Failure Modes (all graceful)

| Condition | Behavior |
|-----------|----------|
| `mm-quota` Chrome profile doesn't exist (first run) | Live scrape hits sign-in form → auto-setup runs once → visible browser → user logs in → profile seeded |
| `playwright` not installed | Layer 1 skipped with install hint; Layer 2 + 3 run |
| Chrome not installed / `LOCALAPPDATA` missing | Layer 1 skipped with reason; Layer 2 + 3 run |
| Persistent context times out on `article` selector | One automatic setup retry, then Layer 1 reports "did not render" and falls through to fallback |
| Console DOM changed (selector miss) | Layer 1 returns null fields; Layer 2 + 3 still print |
| No API call log on disk | Layer 3 makes a single `max_tokens=1` probe |
| Network offline | Layer 1 and 3 fail; Layer 2 still prints fallback instructions |
| User runs `--no-auto-setup` | Setup never triggers automatically; manual `--setup` required |
| Playwright browser binary missing | Layer 1 skipped with install hint; Layer 2 + 3 run |
| User passes `--html PATH` | Layer 1 is skipped; Layer 1B (HTML parser) runs against the given file |

## Why Three Layers

The user wants the quota check to be "easy and seamless." A single-layer design forces a choice between false automation (skill that claims to work but doesn't) and manual pass-through (skill that adds nothing). Three layers, run in parallel with explicit per-layer success/failure reporting, give the user the best available answer at every invocation while keeping each layer honest about what it actually knows.

## Architecture

```
mm_quota.py
├── _load_env()                 # reads P:/.env, never raises
├── _cookie_is_fresh()          # 7-day window check on MINIMAX_CONSOLE_COOKIE_CAPTURED_AT
├── _save_cookie_to_env()       # writes cookie + timestamp back to P:/.env, preserves other keys
├── _discover_chrome_user_data_dir()  # finds Chrome user data directory (LOCALAPPDATA on Windows)
├── _setup_capture_cookie()     # visible-browser login flow; persistent context against mm-quota profile; captures session
├── _layer1_console_scrape()    # headless persistent context against mm-quota profile; inherits session from profile storage
├── _layer1b_parse_html()       # offline HTML snapshot parser (only when --html PATH is passed)
├── _layer2_fallback_block()    # static instructions; always returns string
├── _layer3_session_tokens()    # parses JSONL log or makes probe; returns int tuple
├── _format_output()            # assembles the chat display block
└── main()                      # orchestrates layers + auto-setup + retry-on-sign-in-form
```

Dependencies: `playwright` (Layer 1 + setup), `requests` (Layer 3 probe path).

Tests:
- `tests/test_mm_quota.py` — Layer 1 persistent context behavior, Layer 3 log parsing, env loading.
- `tests/test_html_parser.py` — Layer 1B against the saved `Usage.html` fixture.
- `tests/test_setup_flow.py` — cookie freshness, persistence (no-clobber, overwrite, error-swallow), JSON blob parsing.

## Rollback

If the new live path fails in practice, the user can:

```bash
python .../mm_quota.py --html PATH   # opt back into the offline parser with any saved snapshot
git checkout HEAD -- packages/.claude-marketplace/plugins/cc-skills-utils/skills/mm-quota/   # revert the change set
```

The `--html` path is preserved as a deliberate escape hatch.
