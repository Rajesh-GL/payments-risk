// src/services/rebateCalculator.ts
//
// ⚠️ TEST FIXTURE - INTENTIONALLY BROKEN MATH ⚠️
// Used only to exercise the AI risk-analysis pipeline. Issues on purpose:
//   1. Uses JavaScript's native floating-point `number` type to accumulate
//      currency amounts instead of an exact decimal/integer-cents type.
//      Binary floating point cannot represent most decimal fractions
//      exactly (e.g. 0.1 + 0.2 !== 0.3), so summing many rebate line items
//      drifts by fractions of a cent - and at volume, those drift errors
//      compound into real, audit-visible discrepancies.
//   2. Silently switched rounding mode from "round half up" (the historical
//      behavior finance reconciled against) to "round half to even" /
//      banker's rounding, changing payout amounts by up to 1 cent per line
//      with no migration note, changelog, or feature flag - so historical
//      reports will no longer reconcile against newly computed ones.

interface RebateLine {
  orderId: string;
  amount: number; // BUG: should be an integer cents value or a Decimal type
  rebatePercent: number;
}

export function vectorizedSum(lines: RebateLine[]): number {
  // BUG: naive floating-point accumulation - error compounds with volume
  let total = 0;
  for (const line of lines) {
    total += line.amount * (line.rebatePercent / 100);
  }
  return total;
}

export function roundPayout(value: number): number {
  // BUG: silently changed from historical "round half up" to "round half
  // to even" (banker's rounding). Math.round() in JS actually rounds
  // half-away-from-zero for positives, so this reimplementation was
  // introduced specifically to switch behavior - shifting payouts by up
  // to $0.01 per line versus every historical report already reconciled.
  const scaled = value * 100;
  const rounded =
    Math.abs(scaled % 1) === 0.5
      ? 2 * Math.round(scaled / 2) // round half to even
      : Math.round(scaled);
  return rounded / 100;
}

export function calculateRebatePayout(lines: RebateLine[]): number {
  const rawTotal = vectorizedSum(lines);
  return roundPayout(rawTotal);
}
