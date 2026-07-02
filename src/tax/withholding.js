// Tax & compliance calculations. Wrong numbers here mean legal liability,
// audit failures, and customer penalties.
// v4.0.0 changes both the withholding formula and the interest method.

// v4.0.0: new withholding tax brackets. If these tables are wrong or applied to
// the wrong income base, every affected customer is under- or over-withheld.
const WITHHOLDING_BRACKETS = [
  { upTo: 10000, rate: 0.1 },
  { upTo: 40000, rate: 0.22 },
  { upTo: Infinity, rate: 0.32 },
];

function withholdingTax(income) {
  const bracket = WITHHOLDING_BRACKETS.find((b) => income <= b.upTo);
  return income * bracket.rate;
}

// v4.0.0: interest accrual changed from simple to daily-compounded.
// This changes reported balances and interest statements for every account.
function accruedInterest(principal, annualRate, days) {
  const daily = annualRate / 365;
  return principal * (Math.pow(1 + daily, days) - 1); // was principal * annualRate * days / 365
}

module.exports = { withholdingTax, accruedInterest };
