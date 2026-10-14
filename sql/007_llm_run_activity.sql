-- Operational trace for live agent runs shown in the dashboard.
CREATE TABLE IF NOT EXISTS llm_run_activity (
    activity_id UUID PRIMARY KEY,
    run_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    llm_model TEXT NOT NULL,
    task TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'starting',
    status TEXT NOT NULL DEFAULT 'running',
    outcome_success BOOLEAN,
    result_text TEXT,
    memory_id UUID,
    memory_tier TEXT,
    storage_status TEXT NOT NULL DEFAULT 'pending',
    error_text TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_llm_run_activity_updated
    ON llm_run_activity (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_run_activity_status
    ON llm_run_activity (status, updated_at DESC);
