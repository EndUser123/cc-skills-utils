#!/usr/bin/env python3
"""Sync model catalog from NVIDIA NIM and OpenRouter APIs."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Load .env if present
_ENV = Path(__file__).resolve().parents[5] / ".env"  # P:/.env
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if k:
            os.environ[k] = v

CATALOG_DB = Path(__file__).parent.parent.parent / "catalog.db"
SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "model_catalog.sql"

# ── Provider definitions ──────────────────────────────────────────────────────

PROVIDERS = [
    {
        "bifrost_name": "nvidia",
        "display_name": "NVIDIA NIM",
        "access_model": "free_key",
        "api_base": "https://integrate.api.nvidia.com/v1",
        "notes": "NIM subscription — all models effectively free",
    },
    {
        "bifrost_name": "openrouter",
        "display_name": "OpenRouter",
        "access_model": "openrouter",
        "api_base": "https://openrouter.ai/api/v1",
        "notes": "Cost-aware filtering required",
    },
    {
        "bifrost_name": "cerebras",
        "display_name": "Cerebras",
        "access_model": "free_key",
        "api_base": None,
        "notes": "API key covers access",
    },
    {
        "bifrost_name": "groq",
        "display_name": "Groq",
        "access_model": "free_key",
        "api_base": None,
        "notes": "API key covers access",
    },
    {
        "bifrost_name": "mistral",
        "display_name": "Mistral",
        "access_model": "free_key",
        "api_base": None,
        "notes": "API key covers access",
    },
    {
        "bifrost_name": "minimax",
        "display_name": "MiniMax",
        "access_model": "subscription",
        "api_base": None,
        "notes": "MiniMax subscription",
    },
    {
        "bifrost_name": "z.ai",
        "display_name": "Z.AI",
        "access_model": "subscription",
        "api_base": None,
        "notes": "Z.AI subscription",
    },
]


# ── Schema init ───────────────────────────────────────────────────────────────

def init_db() -> sqlite3.Connection:
    CATALOG_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CATALOG_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    # Seed providers
    for p in PROVIDERS:
        conn.execute("""
            INSERT OR IGNORE INTO providers (bifrost_name, display_name, access_model, api_base, notes)
            VALUES (:bifrost_name, :display_name, :access_model, :api_base, :notes)
        """, p)
    # Migrate models table: add free-tier columns if missing
    for col, typ in [
        ("max_input_tokens_free", "INTEGER"),
        ("max_output_tokens_free", "INTEGER"),
    ]:
        try:
            conn.execute(f"ALTER TABLE models ADD COLUMN {col} {typ}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    return conn


# ── NIM sync ──────────────────────────────────────────────────────────────────

def fetch_nim_models() -> list[dict]:
    """Fetch all models from NVIDIA NIM API."""
    api_key = os.environ.get("NVIDIA_NIM_API_KEY") or os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        print("NVIDIA_NIM_API_KEY not set — skipping NIM sync")
        return []

    url = "https://integrate.api.nvidia.com/v1/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    models = data.get("data", [])
    results = []
    now = datetime.now(timezone.utc).isoformat()

    for m in models:
        mid = m.get("id", "")
        # Skip non-chat models (embeddings, safety, etc.) for now
        # NIM models often have context in special fields
        # NIM /v1/models uses context_window (vLLM backend); fall back to context_length, then max_tokens
        context_len = (
            m.get("context_window")
            or m.get("context_length")
            or m.get("max_tokens")
            or 0
        )

        # Determine mode from model ID / name
        name_lower = mid.lower()
        if any(x in name_lower for x in ["embed", "embedding", "rerank"]):
            mode = "embed"
        elif any(x in name_lower for x in ["safety", "guard", "shield"]):
            mode = "safety"
        elif any(x in name_lower for x in ["translate", "translation"]):
            mode = "translate"
        elif any(x in name_lower for x in ["vision", "vlm", "vision-language"]):
            mode = "video"
        else:
            mode = "chat"

        # Derive host/vendor/slug from model ID
        # NIM model IDs are "provider/model-slug" (e.g. "meta/llama-3.3-70b-instruct")
        # Vendor is the provider prefix (parts[0]), slug is everything after
        parts = mid.split("/")
        if len(parts) >= 2:
            host = "nvidia"        # NIM is always accessed via nvidia host in UMU
            vendor = parts[0]       # provider prefix is the vendor (meta, moonshotai, nvidia, etc.)
            slug = "/".join(parts[1:])
        else:
            host = "nvidia"
            vendor = "nvidia"
            slug = mid

        umu = f"{host}://{vendor}/{slug}"

        pricing = m.get("pricing", {}) or {}
        input_cost = float(pricing.get("input", 0) or 0)
        output_cost = float(pricing.get("output", 0) or 0)

        results.append({
            "model": mid,
            "umu": umu,
            "bifrost_provider": "nvidia",
            "host": host,
            "vendor": vendor,
            "model_slug": slug,
            "base_model": mid,
            "mode": mode,
            "max_input_tokens": context_len,
            "max_output_tokens": None,
            "input_cost_per_token": input_cost,
            "output_cost_per_token": output_cost,
            "max_input_tokens_free": None,
            "max_output_tokens_free": None,
            "source": "nvidia_nim",
            "fetched_at": now,
        })

    return results


# ── OpenRouter sync ───────────────────────────────────────────────────────────

# Known free vendors to exclude (have their own subscription paths)
OPENROUTER_EXCLUDED_VENDORS = {"moonshotai", "minimax", "z.ai", "bytedance"}


def fetch_openrouter_models() -> list[dict]:
    """Fetch all models from OpenRouter API."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not set — skipping OpenRouter sync")
        return []

    url = "https://openrouter.ai/api/v1/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    models = data.get("data", [])
    results = []
    now = datetime.now(timezone.utc).isoformat()

    for m in models:
        mid = m.get("id", "")
        if not mid:
            continue

        # Determine mode
        name_lower = mid.lower()
        modalities = m.get("supported_parameters", []) or []
        if "embed" in modalities or "embeddings" in modalities:
            mode = "embed"
        elif "image" in modalities or "vision" in modalities:
            mode = "video"
        else:
            mode = "chat"

        # OpenRouter format: "provider/model" or "provider/model:variant"
        # Keep full model string (including :variant) as slug — UMU must be unique
        parts = mid.split("/")
        if len(parts) >= 2:
            vendor = parts[0].lower()
            slug = "/".join(parts[1:])   # preserve full variant suffix (e.g. :free, :aa2897)
        else:
            vendor = parts[0].lower()
            slug = parts[0]

        host = "openrouter"
        umu = f"{host}://{vendor}/{slug}"

        ctx = m.get("context_length", 0) or 0
        pricing = m.get("pricing", {}) or {}
        input_cost = float(pricing.get("input", 0) or 0)
        output_cost = float(pricing.get("output", 0) or 0)

        # Skip excluded vendors for free models (they have subscription paths)
        excluded = OPENROUTER_EXCLUDED_VENDORS
        is_free = input_cost == 0 and output_cost == 0
        skip_reason = None
        if vendor in excluded and is_free:
            skip_reason = f"vendor {vendor} excluded (subscription path)"
        elif vendor not in excluded and not is_free:
            skip_reason = f"vendor {vendor}, non-zero cost"

        results.append({
            "model": mid,
            "umu": umu,
            "bifrost_provider": "openrouter",
            "host": host,
            "vendor": vendor,
            "model_slug": slug,
            "base_model": mid,
            "mode": mode,
            "max_input_tokens": ctx,
            "max_output_tokens": m.get("max_output_tokens"),
            "input_cost_per_token": input_cost,
            "output_cost_per_token": output_cost,
            "max_input_tokens_free": None,
            "max_output_tokens_free": None,
            "source": "openrouter",
            "fetched_at": now,
            "_skip_reason": skip_reason,
        })

    return results


# ── DB upsert ────────────────────────────────────────────────────────────────

MODEL_COLS = [
    "model", "umu", "bifrost_provider", "host", "vendor", "model_slug",
    "base_model", "mode", "max_input_tokens", "max_output_tokens",
    "input_cost_per_token", "output_cost_per_token",
    "max_input_tokens_free", "max_output_tokens_free",
    "source", "fetched_at",
]


def upsert_models(conn: sqlite3.Connection, rows: list[dict]) -> int:
    upserted = 0
    skipped = 0
    for r in rows:
        skip = r.pop("_skip_reason", None)
        if skip:
            skipped += 1
            continue

        cols = {k: r[k] for k in MODEL_COLS if k in r}
        cols["updated_at"] = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO models (id, model, umu, bifrost_provider,
                host, vendor, model_slug, base_model, mode,
                max_input_tokens, max_output_tokens,
                input_cost_per_token, output_cost_per_token,
                source, fetched_at, created_at, updated_at,
                max_input_tokens_free, max_output_tokens_free)
            VALUES (NULL, :model, :umu, :bifrost_provider,
                :host, :vendor, :model_slug, :base_model, :mode,
                :max_input_tokens, :max_output_tokens,
                :input_cost_per_token, :output_cost_per_token,
                :source, :fetched_at,
                datetime('now'), :updated_at,
                :max_input_tokens_free, :max_output_tokens_free)
            ON CONFLICT(model) DO UPDATE SET
                umu                = excluded.umu,
                bifrost_provider   = excluded.bifrost_provider,
                host              = excluded.host,
                vendor            = excluded.vendor,
                model_slug        = excluded.model_slug,
                base_model        = excluded.base_model,
                mode              = excluded.mode,
                max_input_tokens  = excluded.max_input_tokens,
                max_output_tokens = excluded.max_output_tokens,
                input_cost_per_token   = excluded.input_cost_per_token,
                output_cost_per_token  = excluded.output_cost_per_token,
                source            = excluded.source,
                fetched_at        = excluded.fetched_at,
                updated_at        = datetime('now'),
                max_input_tokens_free  = excluded.max_input_tokens_free,
                max_output_tokens_free = excluded.max_output_tokens_free
        """, cols)
        upserted += 1

    conn.commit()
    return upserted, skipped


# ── OpenAI-compatible fetch helper ───────────────────────────────────────────

def _fetch_openai_compatible_models(
    provider: str,
    api_base: str,
    env_key: str,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch models from any OpenAI-compatible /models endpoint (requests-based)."""
    import requests as _req

    key = api_key or os.environ.get(env_key)
    if not key:
        print(f"{env_key} not set — skipping {provider} sync")
        return []

    url = f"{api_base.rstrip('/')}/models"
    try:
        resp = _req.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  {provider} fetch failed: {e}")
        return []

    models = data.get("data", []) or data.get("models", []) or []
    results = []
    now = datetime.now(timezone.utc).isoformat()

    for m in models:
        mid = m.get("id", "")
        if not mid:
            continue

        name_lower = mid.lower()
        if any(x in name_lower for x in ["embed", "embedding"]):
            mode = "embed"
        elif any(x in name_lower for x in ["safety", "guard", "shield"]):
            mode = "safety"
        elif any(x in name_lower for x in ["vision", "vlm"]):
            mode = "video"
        elif any(x in name_lower for x in ["translate"]):
            mode = "translate"
        else:
            mode = "chat"

        parts = mid.split("/")
        if len(parts) >= 2:
            vendor = parts[0].lower()
            slug = "/".join(parts[1:])
        else:
            vendor = provider
            slug = mid

        # Groq uses context_window; Mistral uses max_context_length;
        # most others use context_length; fall back to max_tokens
        ctx = m.get("context_window") or m.get("max_context_length") or m.get("context_length", 0) or 0
        if not ctx:
            ctx = m.get("max_tokens", 0) or 0

        pricing = m.get("pricing", {}) or {}
        input_cost = float(pricing.get("input", 0) or 0)
        output_cost = float(pricing.get("output", 0) or 0)

        results.append({
            "model": mid,
            "umu": f"{provider}://{vendor}/{slug}",
            "bifrost_provider": provider,
            "host": provider,
            "vendor": vendor,
            "model_slug": slug,
            "base_model": mid,
            "mode": mode,
            "max_input_tokens": ctx,
            "max_output_tokens": m.get("max_output_tokens"),
            "input_cost_per_token": input_cost,
            "output_cost_per_token": output_cost,
            "max_input_tokens_free": None,
            "max_output_tokens_free": None,
            "source": f"{provider}_api",
            "fetched_at": now,
        })

    return results


# ── Provider-specific fetchers ─────────────────────────────────────────────────

def fetch_cerebras_models() -> list[dict]:
    return _fetch_openai_compatible_models(
        "cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"
    )


def fetch_groq_models() -> list[dict]:
    return _fetch_openai_compatible_models(
        "groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"
    )


def fetch_mistral_models() -> list[dict]:
    return _fetch_openai_compatible_models(
        "mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY"
    )


# ── Groq context override ──────────────────────────────────────────────────────
#
# Groq API returns correct context_length for most models via /v1/models.
# A small number of edge cases (safety models, preview models, audio models)
# have NULL or 0 context in the API response. We backfill known values here.
#
# Source: https://console.groq.com/docs/models  (official GroqCloud docs)
#
# max_input_tokens  = actual context window for the model
# max_input_tokens_free = same as paid (Groq free-key and paid-key have same context)
GROQ_CONTEXT_OVERRIDE = {
    # Chat models (131072 context — production)
    "llama-3.1-8b-instruct":              {"ctx": 131072, "out": 131072},
    "llama-3.3-70b-versatile":            {"ctx": 131072, "out":  32768},
    "qwen/qwen3-32b":                      {"ctx": 131072, "out":  40960},
    "meta-llama/llama-4-scout-17b-16e-instruct": {"ctx": 131072, "out":  8192},
    # Whisper models (audio transcription — no LLM context window)
    "whisper-large-v3":                   {"ctx":      0, "out":      0},
    "whisper-large-v3-turbo":             {"ctx":      0, "out":      0},
    # Safety models (small fixed context)
    "openai/gpt-oss-safeguard-20b":        {"ctx": 131072, "out":  65536},
    "openai/gpt-oss-120b":                 {"ctx": 131072, "out":  65536},
    "openai/gpt-oss-20b":                  {"ctx": 131072, "out":  65536},
    "meta-llama/llama-prompt-guard-2-22m":  {"ctx":     512, "out":    512},
    "meta-llama/llama-prompt-guard-2-86m":  {"ctx":     512, "out":    512},
    # Compound models (Groq-specific)
    "groq/compound":                       {"ctx": 131072, "out":   8192},
    "groq/compound-mini":                  {"ctx": 131072, "out":   8192},
    # Preview / specialty models
    "canopylabs/orpheus-v1-english":      {"ctx":   4000, "out":  50000},
    "canopylabs/orpheus-arabic-saudi":     {"ctx":   4000, "out":  50000},
    "allam-2-7b":                         {"ctx": 131072, "out":  16384},
}


def _patch_groq_context(conn: sqlite3.Connection) -> int:
    """Backfill known context lengths for Groq models that return 0 or NULL."""
    updated = 0
    for slug, info in GROQ_CONTEXT_OVERRIDE.items():
        cur = conn.execute(
            "UPDATE models SET max_input_tokens = ?, max_output_tokens = ?, "
            "max_input_tokens_free = ?, max_output_tokens_free = ?, "
            "updated_at = datetime('now') "
            "WHERE bifrost_provider = 'groq' AND (model = ? OR model_slug = ?) "
            "AND max_input_tokens = 0",
            (info["ctx"], info["out"], info["ctx"], info["out"], slug, slug),
        )
        updated += cur.rowcount
    if updated:
        conn.commit()
    return updated


# ── Cerebras context override ─────────────────────────────────────────────────
#
# Cerebras API returns zero metadata (no context_length field).
# Context limits differ by tier (free vs paid):
#   gpt-oss-120b:           free=65K/32K   paid=131K/40K
#   zai-glm-4.7:            free=64K/40K   paid=131K/40K
#   llama3.1-8b:            free=8K/8K      paid=32K/8K   (DEPRECATED May 27, 2026)
#   qwen-3-235b-a22b-*:     free=65K/32K   paid=131K/40K (DEPRECATED May 27, 2026)
#   llama-3.3-70b:          free=65K/32K    paid=131K/40K  (production)
#   qwen-3-32b:             free=65K/32K    paid=131K/40K  (production)
#
# max_input_tokens  = paid tier (what Cerebras API key default gets you)
# max_input_tokens_free = free tier (what free access gets you)
CEREBRAS_CONTEXT_OVERRIDE = {
    # Deprecated (API still returns these but may stop after 2026-05-27)
    "gpt-oss-120b":                 {"paid_ctx": 131072, "free_ctx": 65536, "paid_out": 40960, "free_out": 32768},
    "llama3.1-8b":                  {"paid_ctx":  32768, "free_ctx":  8192, "paid_out":  8192, "free_out":  8192},
    "qwen-3-235b-a22b-instruct-2507": {"paid_ctx": 131072, "free_ctx": 65536, "paid_out": 40960, "free_out": 32768},
    "zai-glm-4.7":                  {"paid_ctx": 131072, "free_ctx": 65536, "paid_out": 40960, "free_out": 40960},
    # Production (added manually — not in Cerebras /models list)
    "llama-3.3-70b":                {"paid_ctx": 131072, "free_ctx": 65536, "paid_out": 40960, "free_out": 32768},
    "qwen-3-32b":                   {"paid_ctx": 131072, "free_ctx": 65536, "paid_out": 40960, "free_out": 32768},
}


def _patch_cerebras_context(conn: sqlite3.Connection) -> int:
    """Backfill missing context lengths and free-tier variants for Cerebras models."""
    updated = 0
    for slug, info in CEREBRAS_CONTEXT_OVERRIDE.items():
        cur = conn.execute(
            "UPDATE models SET max_input_tokens = ?, max_input_tokens_free = ?, "
            "max_output_tokens = ?, max_output_tokens_free = ?, updated_at = datetime('now') "
            "WHERE bifrost_provider = 'cerebras' AND model_slug = ? AND max_input_tokens = 0",
            (info["paid_ctx"], info["free_ctx"], info["paid_out"], info["free_out"], slug),
        )
        updated += cur.rowcount
    if updated:
        conn.commit()
    return updated


# NVIDIA NIM API /v1/models returns no context metadata (only id, object, created, owned_by).
# Backfill from Bifrost governance DB which has verified context lengths for 58 NIM models.
NVIDIA_CONTEXT_OVERRIDE = {
    "bge-m3":                               {"ctx": 32768,  "out": 4096},
    "deepseek-coder-6.7b-instruct":          {"ctx": 65536,  "out": 65536},
    "codegemma-1.1-7b":                      {"ctx": 8192,   "out": 8192},
    "codegemma-7b":                          {"ctx": 8192,   "out": 8192},
    "deplot":                               {"ctx": 2048,   "out": 2048},
    "gemma-2-2b-it":                         {"ctx": 8192,   "out": 8192},
    "gemma-2b":                             {"ctx": 8192,   "out": 8192},
    "gemma-3n-e2b-it":                      {"ctx": 32768,  "out": 32768},
    "recurrentgemma-2b":                    {"ctx": 8192,   "out": 8192},
    "granite-34b-code-instruct":             {"ctx": 32768,  "out": 32768},
    "granite-8b-code-instruct":             {"ctx": 32768,  "out": 32768},
    "codellama-70b":                         {"ctx": 16384,  "out": 16384},
    "llama-3.1-405b-instruct":              {"ctx": 131072, "out": 131072},
    "llama-3.1-70b-instruct":               {"ctx": 131072, "out": 131072},
    "llama-3.1-8b-instruct":                {"ctx": 131072, "out": 131072},
    "llama-3.2-11b-vision-instruct":        {"ctx": 131072, "out": 131072},
    "llama-3.2-1b-instruct":                {"ctx": 131072, "out": 131072},
    "llama-3.2-3b-instruct":                {"ctx": 131072, "out": 131072},
    "llama-3.2-90b-vision-instruct":        {"ctx": 131072, "out": 131072},
    "llama-3.3-70b-instruct":               {"ctx": 131072, "out": 131072},
    "llama-4-maverick-17b-128e-instruct":  {"ctx": 131072, "out": 131072},
    "llama-guard-4-12b":                   {"ctx": 131072, "out": 4096},
    "kosmos-2":                              {"ctx": 32768,  "out": 4096},
    "mistral-large-3-675b-instruct-2512":  {"ctx": 131072, "out": 131072},
    "mistral-medium-3-instruct":            {"ctx": 131072, "out": 131072},
    "mistral-medium-3.5-128b":             {"ctx": 131072, "out": 131072},
    "mistral-nemotron":                      {"ctx": 131072, "out": 131072},
    "kimi-k2-instruct":                     {"ctx": 262144, "out": 262144},
    "kimi-k2-instruct-0905":                {"ctx": 262144, "out": 262144},
    "ai-synthetic-video-detector":           {"ctx": 32768,  "out": 4096},
    "cosmos-reason2-8b":                    {"ctx": 32768,  "out": 32768},
    "embed-qa-4":                           {"ctx": 32768,  "out": 4096},
    "llama-3.1-nemoguard-8b-content-safety": {"ctx": 32768,  "out": 4096},
    "llama-3.1-nemoguard-8b-topic-control":  {"ctx": 32768,  "out": 4096},
    "llama-3.1-nemotron-safety-guard-8b-v3": {"ctx": 32768,  "out": 4096},
    "llama-3.2-nemoretriever-1b-vlm-embed-v1": {"ctx": 32768, "out": 4096},
    "llama-3.2-nemoretriever-300m-embed-v1":  {"ctx": 32768, "out": 4096},
    "llama-3.2-nv-embedqa-1b-v1":           {"ctx": 32768,  "out": 4096},
    "llama-3.2-nv-embedqa-1b-v2":           {"ctx": 32768,  "out": 4096},
    "llama-nemotron-embed-1b-v2":           {"ctx": 32768,  "out": 4096},
    "llama-nemotron-embed-vl-1b-v2":        {"ctx": 32768,  "out": 4096},
    "nemoretriever-parse":                  {"ctx": 32768,  "out": 4096},
    "nemotron-3-content-safety":            {"ctx": 32768,  "out": 4096},
    "nemotron-3-nano-omni-30b-a3b-reasoning": {"ctx": 262144, "out": 0},
    "nemotron-4-340b-instruct":             {"ctx": 131072, "out": 131072},
    "nemotron-4-340b-reward":              {"ctx": 32768,  "out": 32768},
    "nemotron-content-safety-reasoning-4b":  {"ctx": 32768,  "out": 4096},
    "nemotron-parse":                       {"ctx": 32768,  "out": 4096},
    "neva-22b":                             {"ctx": 32768,  "out": 4096},
    "nv-embed-v1":                           {"ctx": 32768,  "out": 4096},
    "nv-embedcode-7b-v1":                   {"ctx": 32768,  "out": 4096},
    "nv-embedqa-e5-v5":                     {"ctx": 32768,  "out": 4096},
    "nv-embedqa-mistral-7b-v2":             {"ctx": 32768,  "out": 4096},
    "riva-translate-4b-instruct":           {"ctx": 32768,  "out": 4096},
    "riva-translate-4b-instruct-v1.1":      {"ctx": 32768,  "out": 4096},
    "qwen2.5-coder-32b-instruct":          {"ctx": 32768,  "out": 32768},
    "qwen3-coder-480b-a35b-instruct":      {"ctx": 131072, "out": 131072},
    "arctic-embed-l":                        {"ctx": 32768,  "out": 4096},
}


def _patch_nvidia_context(conn: sqlite3.Connection) -> int:
    """Backfill missing context lengths for NVIDIA NIM models from override table."""
    updated = 0
    for slug, info in NVIDIA_CONTEXT_OVERRIDE.items():
        cur = conn.execute(
            "UPDATE models SET max_input_tokens = ?, max_output_tokens = ?, "
            "max_input_tokens_free = ?, max_output_tokens_free = ?, "
            "updated_at = datetime('now') "
            "WHERE bifrost_provider = 'nvidia' AND model_slug = ? AND max_input_tokens = 0",
            (info["ctx"], info["out"], info["ctx"], info["out"], slug),
        )
        updated += cur.rowcount
    if updated:
        conn.commit()
    return updated


# max_input_tokens  = actual context window for the model
# max_input_tokens_free = same as paid (Mistral free-key and paid-key have same context)
MISTRAL_CONTEXT_OVERRIDE = {
    # Current generation models
    "mistral-large-latest":        {"ctx": 262144, "out": 262144},
    "mistral-large-2512":          {"ctx": 262144, "out": 262144},
    "mistral-large-3":             {"ctx": 262144, "out": 262144},
    "mistral-large-2411":          {"ctx": 131072, "out": 131072},
    "mistral-medium-latest":       {"ctx": 262144, "out": 262144},
    "mistral-medium-2604":         {"ctx": 262144, "out": 262144},
    "mistral-medium-2508":         {"ctx": 131072, "out": 131072},
    "mistral-medium-2505":         {"ctx": 131072, "out": 131072},
    "mistral-medium-3":            {"ctx": 131072, "out": 131072},
    "mistral-medium-3.5":          {"ctx": 262144, "out": 262144},
    "mistral-medium-c21211-r0-75": {"ctx": 262144, "out": 262144},
    "mistral-small-latest":        {"ctx": 262144, "out": 262144},
    "mistral-small-2603":          {"ctx": 262144, "out": 262144},
    "mistral-small-2506":          {"ctx": 131072, "out": 131072},
    "mistral-small-2407":          {"ctx": 131072, "out": 131072},
    "mistral-small-2409":          {"ctx": 131072, "out": 131072},
    "mistral-tiny-latest":         {"ctx": 131072, "out": 131072},
    "mistral-tiny-2407":           {"ctx": 131072, "out": 131072},
    # Code models
    "codestral-latest":            {"ctx":  32768, "out":  32768},
    "codestral-2508":              {"ctx":  32768, "out":  32768},
    "devstral-latest":             {"ctx": 262144, "out": 262144},
    "devstral-2512":              {"ctx": 262144, "out": 262144},
    "devstral-medium-latest":      {"ctx": 262144, "out": 262144},
    "devstral-medium-2507":        {"ctx": 131072, "out": 131072},
    "devstral-small-2505":         {"ctx": 131072, "out": 131072},
    # Magistral
    "magistral-medium-latest":     {"ctx":  40960, "out":  40960},
    "magistral-medium-2509":       {"ctx":  40960, "out":  40960},
    "magistral-small-2509":        {"ctx":  40960, "out":  40960},
    # Ministral
    "ministral-14b-latest":        {"ctx":  131072, "out":  131072},
    "ministral-14b-2512":          {"ctx":  131072, "out":  131072},
    "ministral-8b-latest":        {"ctx":  131072, "out":  131072},
    "ministral-8b-2512":          {"ctx":  131072, "out":  131072},
    "ministral-3b-latest":        {"ctx":  131072, "out":  131072},
    "ministral-3b-2512":          {"ctx":  131072, "out":  131072},
    # Pixtral (vision)
    "pixtral-large-latest":       {"ctx": 131072, "out": 131072},
    "pixtral-large-2411":         {"ctx": 131072, "out": 131072},
    "mistral-large-pixtral-2411": {"ctx": 131072, "out": 131072},
    # Voxtral (audio)
    "voxtral-mini-latest":        {"ctx": 131072, "out": 131072},
    "voxtral-mini-2602":          {"ctx": 131072, "out": 131072},
    "voxtral-mini-2507":          {"ctx": 131072, "out": 131072},
    "voxtral-mini-realtime-latest":  {"ctx": 131072, "out": 131072},
    "voxtral-mini-realtime-2602": {"ctx": 131072, "out": 131072},
    "voxtral-mini-transcribe-latest": {"ctx": 131072, "out": 131072},
    "voxtral-mini-transcribe-2507": {"ctx": 131072, "out": 131072},
    "voxtral-mini-transcribe-realtime-2602": {"ctx": 131072, "out": 131072},
    "voxtral-mini-tts-latest":     {"ctx": 131072, "out": 131072},
    "voxtral-mini-tts-2603":      {"ctx": 131072, "out": 131072},
    "voxtral-small-latest":       {"ctx": 131072, "out": 131072},
    "voxtral-small-2507":         {"ctx": 131072, "out": 131072},
    # OCR
    "mistral-ocr-latest":         {"ctx": 131072, "out": 131072},
    "mistral-ocr-2512":           {"ctx": 131072, "out": 131072},
    "mistral-ocr-2505":           {"ctx": 131072, "out": 131072},
    # Moderation
    "mistral-moderation-latest":  {"ctx": 131072, "out": 131072},
    "mistral-moderation-2603":    {"ctx": 131072, "out": 131072},
    "mistral-moderation-2411":    {"ctx": 131072, "out": 131072},
    # Mistral Vibe CLI
    "mistral-vibe-cli-latest":    {"ctx": 131072, "out": 131072},
    "mistral-vibe-cli-fast":      {"ctx": 131072, "out": 131072},
    "mistral-vibe-cli-with-tools": {"ctx": 131072, "out": 131072},
    # Leanstral
    "labs-leanstral-2603":       {"ctx": 131072, "out": 131072},
    # Open models
    "open-mistral-nemo":          {"ctx": 131072, "out": 131072},
    "open-mistral-nemo-2407":     {"ctx": 131072, "out": 131072},
}


def _patch_mistral_context(conn: sqlite3.Connection) -> int:
    """Backfill known context lengths for Mistral models whose API key lacks metadata access."""
    updated = 0
    for slug, info in MISTRAL_CONTEXT_OVERRIDE.items():
        cur = conn.execute(
            "UPDATE models SET max_input_tokens = ?, max_output_tokens = ?, "
            "max_input_tokens_free = ?, max_output_tokens_free = ?, "
            "updated_at = datetime('now') "
            "WHERE bifrost_provider = 'mistral' AND (model = ? OR model_slug = ?) "
            "AND max_input_tokens = 0",
            (info["ctx"], info["out"], info["ctx"], info["out"], slug, slug),
        )
        updated += cur.rowcount
    if updated:
        conn.commit()
    return updated


def _upsert_cerebras_production_models(conn: sqlite3.Connection) -> int:
    """Add Cerebras production models not in the /models API response.

    These are confirmed production models from docs but don't appear in the
    API enumeration. We insert them with both free and paid tier context limits.
    """
    now = datetime.now(timezone.utc).isoformat()
    upserted = 0
    for slug, info in CEREBRAS_CONTEXT_OVERRIDE.items():
        parts = slug.split("/")
        vendor = parts[0].lower() if parts else "unknown"

        # Use INSERT OR REPLACE so existing rows get refreshed with correct values
        # (especially free_ctx / free_out for production models back-filled in prior run)
        conn.execute("""
            INSERT OR REPLACE INTO models (id, model, umu, bifrost_provider,
                host, vendor, model_slug, base_model, mode,
                max_input_tokens, max_output_tokens,
                input_cost_per_token, output_cost_per_token,
                max_input_tokens_free, max_output_tokens_free,
                source, fetched_at, created_at, updated_at)
            VALUES (
                (SELECT id FROM models WHERE model = :model AND bifrost_provider = 'cerebras'),
                :model, :umu, :bifrost_provider,
                :host, :vendor, :model_slug, :base_model, :mode,
                :max_input_tokens, :max_output_tokens,
                :input_cost_per_token, :output_cost_per_token,
                :max_input_tokens_free, :max_output_tokens_free,
                :source, :fetched_at, datetime('now'), datetime('now')
            )
        """, {
            "model": slug,
            "umu": f"cerebras://{vendor}/{slug}",
            "bifrost_provider": "cerebras",
            "host": "cerebras",
            "vendor": vendor,
            "model_slug": slug,
            "base_model": slug,
            "mode": "chat",
            "max_input_tokens": info["paid_ctx"],
            "max_output_tokens": info["paid_out"],
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "max_input_tokens_free": info["free_ctx"],
            "max_output_tokens_free": info["free_out"],
            "source": "cerebras_production_doc",
            "fetched_at": now,
        })
        upserted += 1
    conn.commit()
    return upserted


# ── Subscription providers (no public /v1/models endpoint known) ─────────────

# Seeded from bifrost governance DB records — no live API refresh available
MINIMAX_KNOWN_MODELS = [
    {"model": "minimax/minimax-m2.7", "ctx": 196608},
    {"model": "minimax/minimax-m2.5", "ctx": 196608},
    {"model": "minimax/minimax-m2.5:free", "ctx": 196608},
]

ZAI_KNOWN_MODELS = [
    {"model": "zai/glm-5", "ctx": 200000},
    {"model": "zai/glm-5-turbo", "ctx": 200000},
    {"model": "zai/glm-5.1", "ctx": 200000},
]


def fetch_minimax_models() -> list[dict]:
    """Seed from known records — no public /v1/models endpoint."""
    if not os.environ.get("MINIMAX_API_KEY"):
        print("MINIMAX_API_KEY not set — skipping minimax sync")
        return []
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "model": m["model"],
            "umu": f"minimax://minimax/{m['model'].split('/')[1]}",
            "bifrost_provider": "minimax",
            "host": "minimax",
            "vendor": "minimax",
            "model_slug": m["model"].split("/", 1)[1],
            "base_model": m["model"],
            "mode": "chat",
            "max_input_tokens": m["ctx"],
            "max_output_tokens": m["ctx"],
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
            "max_input_tokens_free": None,
            "max_output_tokens_free": None,
            "source": "minimax_seed",
            "fetched_at": now,
        }
        for m in MINIMAX_KNOWN_MODELS
    ]


def fetch_zai_models() -> list[dict]:
    """Seed from known records — no public /v1/models endpoint."""
    if not os.environ.get("ZAI_API_KEY"):
        print("ZAI_API_KEY not set — skipping z.ai sync")
        return []
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "model": m["model"],
            "umu": f"zai://zai/{m['model'].split('/')[1]}",
            "bifrost_provider": "z.ai",
            "host": "zai",
            "vendor": "zai",
            "model_slug": m["model"].split("/", 1)[1],
            "base_model": m["model"],
            "mode": "chat",
            "max_input_tokens": m["ctx"],
            "max_output_tokens": m["ctx"],
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
            "max_input_tokens_free": None,
            "max_output_tokens_free": None,
            "source": "zai_seed",
            "fetched_at": now,
        }
        for m in ZAI_KNOWN_MODELS
    ]


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Sync model catalog from provider APIs")
    parser.add_argument("--source", choices=["nim", "openrouter", "cerebras", "groq", "mistral", "minimax", "zai", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = init_db()

    total_upserted = 0
    total_skipped = 0

    if args.source in ("nim", "all"):
        print("Fetching NVIDIA NIM models...")
        try:
            rows = fetch_nim_models()
            upserted, skipped = upsert_models(conn, rows)
            print(f"  NIM: {upserted} upserted, {skipped} skipped")
            total_upserted += upserted
            total_skipped += skipped
        # Backfill context lengths for NIM models whose API returns no metadata
            patched = _patch_nvidia_context(conn)
            if patched:
                print(f"  NIM: patched {patched} context lengths")
        except Exception as e:
            print(f"  NIM fetch failed: {e}")

    if args.source in ("openrouter", "all"):
        print("Fetching OpenRouter models...")
        try:
            rows = fetch_openrouter_models()
            upserted, skipped = upsert_models(conn, rows)
            print(f"  OpenRouter: {upserted} upserted, {skipped} skipped")
            total_upserted += upserted
            total_skipped += skipped
        except Exception as e:
            print(f"  OpenRouter fetch failed: {e}")

    if args.source in ("cerebras", "all"):
        print("Fetching Cerebras models...")
        try:
            rows = fetch_cerebras_models()
            upserted, skipped = upsert_models(conn, rows)
            print(f"  Cerebras: {upserted} upserted, {skipped} skipped")
            total_upserted += upserted
            total_skipped += skipped
            # Backfill context lengths (API returns no metadata)
            patched = _patch_cerebras_context(conn)
            if patched:
                print(f"  Cerebras: patched {patched} context lengths")
            # Add production models missing from /models API (llama-3.3-70b, qwen-3-32b)
            added = _upsert_cerebras_production_models(conn)
            if added:
                print(f"  Cerebras: added {added} production models missing from API")
        except Exception as e:
            print(f"  Cerebras fetch failed: {e}")

    if args.source in ("groq", "all"):
        print("Fetching Groq models...")
        try:
            rows = fetch_groq_models()
            upserted, skipped = upsert_models(conn, rows)
            print(f"  Groq: {upserted} upserted, {skipped} skipped")
            total_upserted += upserted
            total_skipped += skipped
            # Backfill known context lengths for edge-case Groq models (safety, audio)
            patched = _patch_groq_context(conn)
            if patched:
                print(f"  Groq: patched {patched} context lengths")
        except Exception as e:
            print(f"  Groq fetch failed: {e}")

    if args.source in ("mistral", "all"):
        print("Fetching Mistral models...")
        try:
            rows = fetch_mistral_models()
            upserted, skipped = upsert_models(conn, rows)
            print(f"  Mistral: {upserted} upserted, {skipped} skipped")
            total_upserted += upserted
            total_skipped += skipped
            # Backfill known context lengths for Mistral models whose API key
            # lacks metadata permission (all return context=0 from /v1/models)
            patched = _patch_mistral_context(conn)
            if patched:
                print(f"  Mistral: patched {patched} context lengths")
        except Exception as e:
            print(f"  Mistral fetch failed: {e}")

    if args.source in ("minimax", "all"):
        print("Fetching MiniMax models...")
        try:
            rows = fetch_minimax_models()
            upserted, skipped = upsert_models(conn, rows)
            print(f"  MiniMax: {upserted} upserted, {skipped} skipped")
            total_upserted += upserted
            total_skipped += skipped
        except Exception as e:
            print(f"  MiniMax fetch failed: {e}")

    if args.source in ("zai", "all"):
        print("Fetching Z.AI models...")
        try:
            rows = fetch_zai_models()
            upserted, skipped = upsert_models(conn, rows)
            print(f"  Z.AI: {upserted} upserted, {skipped} skipped")
            total_upserted += upserted
            total_skipped += skipped
        except Exception as e:
            print(f"  Z.AI fetch failed: {e}")

    # Summary
    cur = conn.execute("SELECT COUNT(*), COUNT(DISTINCT bifrost_provider) FROM models")
    count, n_providers = cur.fetchone()
    print(f"\nCatalog: {count} models from {n_providers} providers")
    print(f"Total upserted: {total_upserted}, skipped: {total_skipped}")

    if args.dry_run:
        print("[DRY RUN — no changes committed]")
        conn.rollback()

    conn.close()


if __name__ == "__main__":
    main()
