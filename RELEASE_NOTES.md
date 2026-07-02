# v4.0.0 — Payments Platform Overhaul

A large release touching money movement, the balance ledger, auth, and tax.

## PR #201: Rewrite settlement routing & fee engine
- Replaced the settlement router: transactions now route through a new
  batching path instead of settling individually.
- Changed currency-conversion rounding from round-half-up to truncation.
- New fee calculation algorithm (tiered instead of flat percentage).

## PR #202: Migrate account balances float -> decimal
- Account balances move from FLOAT to DECIMAL(18,2) for exact precision.
- Transaction timestamps switch from local-time strings to UTC epoch millis.
- Old `transaction_history` table is dropped and replaced by `ledger_entries`.

## PR #203: Security overhaul
- Switched password hashing from SHA-256 to bcrypt.
- Rewrote session management (new token format; all users re-authenticate).
- MFA is now mandatory for admin accounts.

## PR #204: Update withholding tax formula
- New withholding tax calculation to match this year's regulatory tables.
- Changed interest accrual from simple to daily-compounded.
