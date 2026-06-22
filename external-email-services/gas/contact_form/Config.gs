// ═══════════════════════════════════════════════════════════════════════════════
// Config.gs — Contact Form
//
// All environment-specific values live here.
// The main Code.gs reads from this file; never hard-code values there.
//
// HOW TO USE:
//   1. Set ENV to "development" while testing, "production" before final deploy.
//   2. Flip TEST_MODE to true to send all emails to TEST_EMAIL instead of real
//      recipients and skip writing to the sheet. Flip back before deploying.
//   3. Sensitive values (none needed here) should go in Script Properties:
//      Extensions → Apps Script → Project Settings → Script Properties
// ═══════════════════════════════════════════════════════════════════════════════


// ── Environment ───────────────────────────────────────────────────────────────

var ENV       = "production";   // "production" | "development"
var TEST_MODE = false;          // true  → all emails go to TEST_EMAIL, sheet skipped
                                // false → normal production behaviour


// ── Test overrides (only active when TEST_MODE = true) ────────────────────────

var TEST_EMAIL = "your-test-email@gmail.com";   // ← replace with your own address


// ── Site ──────────────────────────────────────────────────────────────────────

var SITE_NAME = "Lamla AI";
var LOGO_URL  = "https://staticassets.netlify.app/public/logos/lamla_logo.png";

var SITE_URL  = (ENV === "production")
  ? "https://ocasia.live"
  : "http://localhost:3000";


// ── Admin ─────────────────────────────────────────────────────────────────────

var ADMIN_EMAIL = "contact.lamla1@gmail.com";   // ← admin notification recipient


// ── Sheet ─────────────────────────────────────────────────────────────────────

var SHEET_NAME = "Contact Form";                // name of the tab in the spreadsheet


// ── Derived helpers ───────────────────────────────────────────────────────────
// Use these in Code.gs instead of reading the vars directly.

/** Returns the admin notification address, honouring TEST_MODE. */
function cfg_adminEmail() {
  return TEST_MODE ? TEST_EMAIL : ADMIN_EMAIL;
}

/** Returns the user-facing recipient, honouring TEST_MODE. */
function cfg_userEmail(realEmail) {
  return TEST_MODE ? TEST_EMAIL : realEmail;
}

/** Returns true when the sheet write should be skipped (TEST_MODE). */
function cfg_skipSheet() {
  return TEST_MODE;
}

/** Logs a prefixed message — useful when TEST_MODE is on. */
function cfg_log(msg) {
  Logger.log("[" + ENV.toUpperCase() + (TEST_MODE ? " / TEST" : "") + "] " + msg);
}
