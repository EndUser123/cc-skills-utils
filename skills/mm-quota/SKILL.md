---
name: mm-quota
version: "1.1.0"
status: "stable"
category: infrastructure
enforcement: advisory
allowed_first_tools:
  - Bash
description: Report MiniMax Plus plan quota — 5h rolling window, weekly, monthly — and session token usage, with automatic cookie capture/setup and graceful fallback when console credentials are not configured.
triggers:
  - /mm-quota
workflow_steps:
  - load_env: 'Read P:/.env to obtain MINIMAX_CONSOLE_COOKIE (and its capture timestamp), ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL. Never raise; missing vars become None.'
  - auto_setup_check: 'If MINIMAX_CONSOLE_COOKIE is missing OR its capture timestamp is older than 7 days, automatically invoke the visible-browser setup flow once. The user logs in once; the cookie is captured and persisted to P:/.env for all future runs.'
  - layer1_console_scrape: 'If MINIMAX_CONSOLE_COOKIE is set AND playwright is importable, headless-browse platform.minimax.io/console/usage and scrape the 5h/weekly/monthly bars. On any failure, return {skipped, reason}; never raise to caller.'
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

The skill works out of the box when `C:/Users/brsth/Downloads/Usage.html` exists (Layer 1B — offline HTML parse, no cookies needed):

1. **Quickest path** — Open `https://platform.minimax.io/console/usage` in Chrome, press Ctrl+S, save as `Usage.html` to your Downloads folder. The next `/mm-quota` invocation will read that file and return the live numbers.
2. **Staleness hint** — If the HTML file is older than 2 minutes, the skill prints a one-line reminder telling you to refresh in Chrome. No silent stale data.
3. **No auto-setup when HTML path is available** — The Playwright/cookie-capture path is only triggered when no HTML snapshot exists.

If the HTML file is missing and you'd rather not use the browser-saved-page workflow, the skill still supports the auto-setup path:

1. **First run** — `MINIMAX_CONSOLE_COOKIE` is missing from `P:/.env`, so the skill prints `no cookie found — running automatic setup` and opens a visible Chromium to `platform.minimax.io/console/usage`.
2. **You log in** — once the usage bars render, the skill captures every cookie for `platform.minimax.io` and writes them to `P:/.env` along with a `MINIMAX_CONSOLE_COOKIE_CAPTURED_AT` timestamp. The browser closes automatically.
3. **Every subsequent run** — the cookie is loaded from `P:/.env` and the live console is scraped headless. You never see a browser again.
4. **After 7 days** — the cookie is considered stale. The next run auto-triggers setup once more. If a live scrape ever fails with a cookie error (e.g., the server invalidated the session), the skill also auto-retries setup once.

To force a refresh: run with `--setup`. To disable auto-setup entirely: run with `--no-auto-setup`.

## Three Layers, in Order

The skill always runs all three layers. Each layer is independent and degrades independently.

### Layer 1 — Console scrape (best case, env-gated)

If `MINIMAX_CONSOLE_COOKIE` is set in `.env` AND `playwright` is importable, the script launches a headless Chromium, navigates to `https://platform.minimax.io/console/usage`, waits for the usage bars to render, and scrapes:

- 5h window: percent used, time-until-reset
- Weekly: percent used or "Unlimited"
- Monthly total: 100% indicator and any visible consumed number

If either precondition fails, Layer 1 is skipped with a one-line reason and the next layer takes over. No crash, no exception propagation.

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

Optional. The skill works without any of these, but Layer 1 requires both.

| Env var | Effect | Required for |
|---------|--------|--------------|
| `MINIMAX_CONSOLE_COOKIE` | Captured session cookies (JSON blob) for `platform.minimax.io` | Layer 1 (auto-captured on first run) |
| `MINIMAX_CONSOLE_COOKIE_CAPTURED_AT` | Unix timestamp of last successful capture | Auto-managed; 7-day freshness window |
| `ANTHROPIC_AUTH_TOKEN` | API key, used by Layer 3 probe and by `cc-mm` | Layer 3 (probe path) |
| `ANTHROPIC_BASE_URL` | MiniMax Anthropic-compatible endpoint | Layer 3 |

Set these in `P:/.env`, not in process environment. The skill reads `.env` directly to keep credentials out of subprocess environments.

## Failure Modes (all graceful)

| Condition | Behavior |
|-----------|----------|
| `MINIMAX_CONSOLE_COOKIE` unset | Auto-setup opens a visible browser for first-time login |
| Cookie older than 7 days | Auto-setup refreshes the cookie (visible browser, once) |
| Live scrape fails with cookie error | Auto-setup retries once, then falls through to fallback |
| `playwright` not installed | Layer 1 skipped; Layer 1B (HTML snapshot) attempted; Layer 2 + 3 run |
| Console DOM changed (selector miss) | Layer 1 returns null fields; Layer 2 + 3 still print |
| No API call log on disk | Layer 3 makes a single `max_tokens=1` probe |
| Network offline | Layer 1 and 3 fail; Layer 2 still prints fallback instructions |
| User runs `--no-auto-setup` | Setup never triggers automatically; manual `--setup` required |
| Playwright browser binary missing | Layer 1 skipped with install hint; Layer 2 + 3 run |

## Why Three Layers

The user wants the quota check to be "easy and seamless." A single-layer design forces a choice between false automation (skill that claims to work but doesn't) and manual pass-through (skill that adds nothing). Three layers, run in parallel with explicit per-layer success/failure reporting, give the user the best available answer at every invocation while keeping each layer honest about what it actually knows.

## Architecture

```
mm_quota.py
├── _load_env()                 # reads P:/.env, never raises
├── _cookie_is_fresh()          # 7-day window check on MINIMAX_CONSOLE_COOKIE_CAPTURED_AT
├── _save_cookie_to_env()       # writes cookie + timestamp back to P:/.env, preserves other keys
├── _setup_capture_cookie()     # visible-browser login flow; waits for quota DOM, captures all cookies
├── _layer1_console_scrape()    # headless Playwright; uses captured cookies; returns dict or {skipped, reason}
├── _layer1b_parse_html()       # offline HTML snapshot parser (no browser, no creds)
├── _layer2_fallback_block()    # static instructions; always returns string
├── _layer3_session_tokens()    # parses JSONL log or makes probe; returns int tuple
├── _format_output()            # assembles the chat display block
└── main()                      # orchestrates layers + auto-setup + retry-on-cookie-error
```

Dependencies: `playwright` (Layer 1 + setup), `requests` (Layer 3 probe path).

Tests:
- `tests/test_mm_quota.py` — Layer 1 env-var short-circuit, Layer 3 log parsing, env loading.
- `tests/test_html_parser.py` — Layer 1B against the saved `Usage.html` fixture.
- `tests/test_setup_flow.py` — cookie freshness, persistence (no-clobber, overwrite, error-swallow), JSON blob parsing.
