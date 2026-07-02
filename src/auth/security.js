// Authentication & session security. SECURITY-SENSITIVE + audit-relevant.
// v4.0.0 changes the hashing algorithm and the session token format at once.

const crypto = require("crypto");

// v4.0.0: switched password hashing SHA-256 -> bcrypt.
// Existing SHA-256 hashes in the DB are NOT compatible with the new verify
// path, so every user must reset or be re-hashed on next login.
async function hashPassword(password) {
  const bcrypt = require("bcrypt");
  return bcrypt.hash(password, 12);
}

async function verifyPassword(password, storedHash) {
  const bcrypt = require("bcrypt");
  return bcrypt.compare(password, storedHash);
}

// v4.0.0: new session token format. Old tokens are invalid, so ALL active
// sessions are dropped on deploy — every user is logged out at once.
function issueSession(userId) {
  const token = crypto.randomBytes(32).toString("hex");
  return { token, userId, version: "v4", issuedAt: Date.now() };
}

// v4.0.0: MFA now mandatory for admins.
function requiresMfa(user) {
  return user.role === "admin";
}

module.exports = { hashPassword, verifyPassword, issueSession, requiresMfa };
