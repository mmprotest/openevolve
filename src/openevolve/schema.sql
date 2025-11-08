CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_json TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    cand_id TEXT PRIMARY KEY,
    run_id TEXT,
    parent_ids TEXT,
    meta_prompt_id TEXT,
    filepath TEXT,
    patch TEXT,
    code_snapshot TEXT,
    gen INTEGER,
    novelty REAL DEFAULT 0.0,
    age INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evaluations (
    eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cand_id TEXT,
    metric TEXT,
    value REAL,
    passed INTEGER,
    cost_ms INTEGER,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_prompts (
    meta_prompt_id TEXT PRIMARY KEY,
    template TEXT,
    parent_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    fitness REAL DEFAULT 0.0
);
