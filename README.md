# fintech-payments

A **maximally high-risk** example release for the Release Risk Scorer — built for
a hackathon demo. In a handful of short files it deliberately touches all four
danger zones of a financial platform at once:

1. **Payment core** ([settlement.js](src/payments/settlement.js)) — batched
   settlement, a rounding change (round-half-up → truncation), and a new fee
   algorithm.
2. **Schema migration** ([001_balances_and_ledger.sql](migrations/001_balances_and_ledger.sql))
   — balances FLOAT → DECIMAL, timestamps → UTC epoch, and a `DROP TABLE` on
   transaction history.
3. **Auth & security** ([security.js](src/auth/security.js)) — hashing SHA-256 →
   bcrypt, a new session format that logs everyone out, mandatory admin MFA.
4. **Tax & compliance** ([withholding.js](src/tax/withholding.js)) — new
   withholding brackets and simple → daily-compounded interest.

Any one of these is risky; shipping all four together should score **Critical**.

## How to use it (demo)

In the Release Risk Scorer UI, type `fintech-payments` into the **"Scan folder"**
box, click **Scan folder**, then **Analyze Release Risk**. Compare the result to
`todo-app` (low risk) to show the scorer telling the two apart.

## Layout

```
src/payments/settlement.js               routing + rounding + fee changes
src/auth/security.js                      hashing swap, session rewrite, MFA
src/tax/withholding.js                    withholding + interest changes
migrations/001_balances_and_ledger.sql    destructive money/history migration
```
