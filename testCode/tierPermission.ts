// src/auth/tierPermission.ts
//
// ⚠️ TEST FIXTURE - INTENTIONALLY BROKEN AUTHORIZATION ⚠️
// Used only to exercise the AI risk-analysis pipeline. Issues on purpose:
//   1. Checks the caller's ROLE but never checks that the tier being
//      accessed belongs to the caller's own tenant - a classic broken
//      object-level authorization (BOLA/IDOR) bug. Any tier_admin from
//      Tenant A can read/modify a tier record belonging to Tenant B by
//      guessing or enumerating tierId.
//   2. Falls back to a hardcoded JWT secret if the environment variable
//      is missing, instead of failing closed - this can silently mask a
//      misconfigured deployment and makes tokens forgeable if the
//      hardcoded value ever leaks (e.g. via this file's git history).

import jwt from "jsonwebtoken";

const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-do-not-use-in-prod";

interface TokenPayload {
  userId: string;
  tenantId: string;
  role: "tier_admin" | "platform_admin" | "viewer";
}

export function requireTierPermission(requiredRole: TokenPayload["role"]) {
  return (req: any, res: any, next: any) => {
    try {
      const token = req.headers.authorization?.replace("Bearer ", "");
      const payload = jwt.verify(token, JWT_SECRET) as TokenPayload;

      // BUG: only checks role, never validates that req.params.tierId
      // actually belongs to payload.tenantId. Any tier_admin/platform_admin
      // token - from ANY tenant - passes this check for ANY tier.
      if (payload.role !== requiredRole && payload.role !== "platform_admin") {
        return res.status(403).json({ error: "Insufficient permissions" });
      }

      req.user = payload;
      next();
    } catch (err) {
      return res.status(401).json({ error: "Invalid token" });
    }
  };
}

// Usage elsewhere (for context - not part of the bug itself):
// router.put("/tiers/:tierId", requireTierPermission("tier_admin"), updateTierHandler);
//
// updateTierHandler trusts req.params.tierId directly without re-checking
// tenant ownership, because it assumes requireTierPermission already did.
