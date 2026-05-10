-- Model catalog schema: local shadow DB replacing Bifrost governance DB
-- UMU format: {host}://{vendor}/{model_slug}

CREATE TABLE IF NOT EXISTS providers (
    id              INTEGER PRIMARY KEY,
    bifrost_name    TEXT UNIQUE NOT NULL,  -- "nvidia", "openrouter", "cerebras", etc.
    display_name    TEXT NOT NULL,
    access_model    TEXT NOT NULL,        -- "free_key" | "subscription" | "per_token" | "openrouter"
    api_base       TEXT,                 -- NULL if no direct API
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS models (
    id                  INTEGER PRIMARY KEY,
    model               TEXT UNIQUE NOT NULL,  -- full model string from provider
    umu                 TEXT UNIQUE NOT NULL,  -- {host}://{vendor}/{model_slug}

    -- 5-field UMU
    bifrost_provider    TEXT NOT NULL,        -- maps to providers.bifrost_name
    host                TEXT NOT NULL,        -- API provider/brand
    vendor              TEXT NOT NULL,         -- model creator/owner
    model_slug          TEXT NOT NULL,        -- immutable model identifier
    base_model          TEXT,                 -- original model string

    -- Taxonomy
    mode                TEXT,                 -- chat, embed, safety, video, translate, parse
    max_input_tokens    INTEGER,
    max_output_tokens   INTEGER,

    -- Cost (USD per token, NULL = unknown)
    input_cost_per_token   REAL,
    output_cost_per_token  REAL,

    -- Free-tier context limits (NULL = same as paid columns; used for free-key providers like Cerebras)
    max_input_tokens_free  INTEGER,
    max_output_tokens_free INTEGER,

    -- Source
    source              TEXT,                 -- "nvidia_nim", "openrouter", "manual"

    -- Timestamps
    fetched_at          TEXT,                 -- ISO8601 when last fetched from API
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_models_provider ON models(bifrost_provider);
CREATE INDEX IF NOT EXISTS idx_models_vendor   ON models(vendor);
CREATE INDEX IF NOT EXISTS idx_models_mode     ON models(mode);
CREATE INDEX IF NOT EXISTS idx_models_umu       ON models(umu);
