-- Migration for v4.0.0. HIGHLY DESTRUCTIVE — touches money and history.
-- Requires a verified backup and a tested rollback before running.

-- 1. Change account balances FLOAT -> DECIMAL for exact money math.
--    The FLOAT -> DECIMAL cast can round existing balances; every account
--    balance must be reconciled after this runs.
ALTER TABLE accounts
  ALTER COLUMN balance TYPE DECIMAL(18, 2);

-- 2. Change how transaction timestamps are stored: local-time string -> UTC
--    epoch millis. DESTRUCTIVE and lossy — original timezone info is discarded.
ALTER TABLE transactions
  ALTER COLUMN occurred_at TYPE BIGINT
  USING (EXTRACT(EPOCH FROM occurred_at::timestamp) * 1000)::bigint;

-- 3. DROP the legacy history table and replace it with a new ledger.
--    Data in transaction_history is NOT migrated here — it is lost on deploy.
DROP TABLE transaction_history;

CREATE TABLE ledger_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id UUID NOT NULL,
  amount DECIMAL(18, 2) NOT NULL,
  occurred_at BIGINT NOT NULL,
  entry_type VARCHAR(20) NOT NULL
);
