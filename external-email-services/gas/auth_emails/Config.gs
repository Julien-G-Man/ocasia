// ═══════════════════════════════════════════════════════════════════════════════
// Config.gs — Auth Emails
//
// All environment-specific values live here.
// The main Code.gs reads from this file; never hard-code values there.
//
// HOW TO USE:
//   1. Set ENV to "development" while testing, "production" before final deploy.
//   2. Flip TEST_MODE to true to send all emails to TEST_EMAIL instead of the
//      real recipient. Flip back before deploying.
//   3. Sensitive values go in Script Properties (NOT here):
//      Extensions → Apps Script → Project Settings → Script Properties
//      Add: GAS_SECRET = <same value as backend env var GAS_AUTH_EMAIL_SECRET>
//
// BACKEND ENV VARS (set on Render):
//   GAS_AUTH_EMAIL_URL    = <your deployed Web App URL>
//   GAS_AUTH_EMAIL_SECRET = <same value as GAS_SECRET in Script Properties>
// ═══════════════════════════════════════════════════════════════════════════════


// ── Environment ───────────────────────────────────────────────────────────────

var ENV       = "production";   // "production" | "development"
var TEST_MODE = false;          // true  → all emails go to TEST_EMAIL
                                // false → normal production behaviour


// ── Test overrides (only active when TEST_MODE = true) ────────────────────────

var TEST_EMAIL = "your-test-email@gmail.com";   // ← replace with your own address


// ── Site ──────────────────────────────────────────────────────────────────────

var SITE_NAME = "Ocasia";
var LOGO_URL  = "https://staticassets.netlify.app/public/logos/lamla_logo.png";

var SITE_URL  = (ENV === "production")
  ? "https://ocasia.live"
  : "http://localhost:3000";


// ── Derived helpers ───────────────────────────────────────────────────────────

/** Returns the actual recipient, honouring TEST_MODE. */
function cfg_recipientEmail(realEmail) {
  return TEST_MODE ? TEST_EMAIL : realEmail;
}

/** Reads the shared secret from Script Properties. Returns null if not set. */
function cfg_secret() {
  return PropertiesService.getScriptProperties().getProperty("GAS_SECRET");
}

/** Logs a prefixed message. */
function cfg_log(msg) {
  Logger.log("[" + ENV.toUpperCase() + (TEST_MODE ? " / TEST" : "") + "] " + msg);
}
