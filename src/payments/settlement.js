// Payment settlement core. BUSINESS-CRITICAL: every transaction settles here.
// v4.0.0 changes money-movement behavior in three ways at once.

// v4.0.0: rounding changed from round-half-up to TRUNCATION.
// This silently drops fractions of a cent on every conversion — across millions
// of transactions the rounding bias compounds in the platform's favor.
function convertCurrency(amount, rate) {
  const raw = amount * rate;
  return Math.trunc(raw * 100) / 100; // was Math.round(raw * 100) / 100
}

// v4.0.0: fees changed from a flat 2% to tiered rates.
function calculateFee(amount) {
  if (amount <= 100) return convertCurrency(amount * 0.03, 1);
  if (amount <= 1000) return convertCurrency(amount * 0.02, 1);
  return convertCurrency(amount * 0.01, 1);
}

// v4.0.0: settlements are now BATCHED instead of settling one-by-one.
// If a batch partially fails, some transactions in it may be double-counted or
// dropped — there is no per-transaction rollback.
function settleBatch(transactions, rate) {
  let total = 0;
  const settled = [];
  for (const tx of transactions) {
    const converted = convertCurrency(tx.amount, rate);
    const fee = calculateFee(converted);
    total += converted - fee;
    settled.push({ id: tx.id, net: converted - fee });
  }
  return { total, settled };
}

module.exports = { convertCurrency, calculateFee, settleBatch };
