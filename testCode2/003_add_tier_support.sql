-- Migration: 003_add_tier_support.sql
-- Adds multi-tier rebate support and retires the legacy flat-rate column.
--
-- ⚠️ TEST FIXTURE - INTENTIONALLY DESTRUCTIVE MIGRATION ⚠️
-- Used only to exercise the AI risk-analysis pipeline. Issues on purpose:
--   1. ADD COLUMN ... NOT NULL with no DEFAULT - will fail on any existing
--      rows unless a backfill runs first, and no backfill is included here.
--   2. DROP COLUMN legacy_flat_rate - irreversible; no data is preserved
--      and there is no rollback path once this runs.
--   3. No transaction wrapping - a partial failure leaves the schema in an
--      inconsistent, hard-to-diagnose state.

ALTER TABLE rebate_calculations
    ADD COLUMN tier_id UUID NOT NULL;

ALTER TABLE rebate_calculations
    DROP COLUMN legacy_flat_rate;

-- No backfill step, no rollback script, no transaction block.
