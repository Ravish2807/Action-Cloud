-- Session memory, expiry, and opt-in federated tenant visibility.
ALTER TABLE experiences ADD COLUMN IF NOT EXISTS session_id TEXT;
ALTER TABLE experiences ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE experiences ADD COLUMN IF NOT EXISTS tenant_id TEXT;
ALTER TABLE experiences ADD COLUMN IF NOT EXISTS federated BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_exp_session ON experiences (session_id, created_at DESC)
    WHERE session_id IS NOT NULL;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE INDEX IF NOT EXISTS idx_exp_tenant ON experiences USING GIN (tenant_id);
