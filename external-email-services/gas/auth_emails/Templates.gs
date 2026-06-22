// ═══════════════════════════════════════════════════════════════════════════════
// Templates.gs — Auth Emails
//
// All email HTML and plain-text fallbacks live here.
// Edit this file to change how emails look.
// Config values (SITE_NAME, LOGO_URL, etc.) are read from Config.gs.
// Logic that calls these functions lives in Code.gs.
// ═══════════════════════════════════════════════════════════════════════════════


// ── Verification email ────────────────────────────────────────────────────────

function buildVerificationHtml(userName, verifyLink, realEmail) {
  return [
    '<!DOCTYPE html>',
    '<html><head><meta charset="UTF-8"><title>Verify Your Email - ' + SITE_NAME + '</title></head>',
    '<body style="margin:0;padding:0;background:#f6f6f6;font-family:Arial,Helvetica,sans-serif;color:#000;">',
    '<div style="max-width:600px;margin:0 auto;background:#ffffff;padding:28px;">',

    _logo(),
    _divider(),

    TEST_MODE ? _testBanner(realEmail) : '',

    '<h1 style="font-size:22px;margin-bottom:14px;">Verify your email</h1>',
    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">Hello ' + esc(userName) + ',</p>',
    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">',
    '  Welcome to <strong>' + SITE_NAME + '</strong>.',
    '  Before you can start using Ocasia, please confirm your email address.',
    '</p>',

    _highlight('Activate your account to begin using Ocasia.'),

    _actionButton('Verify Email', verifyLink),

    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">',
    '  If the button above does not work, copy and paste the link below into your browser:',
    '</p>',
    _linkBox(verifyLink),

    '<p style="font-size:15px;line-height:1.6;margin-top:16px;">',
    '  If you did not create an account on ' + SITE_NAME + ', you can safely ignore this email.',
    '</p>',
    '<p style="font-size:15px;line-height:1.6;">&#8212; The ' + SITE_NAME + ' Team</p>',

    _divider(),
    _ctaButton('Visit Ocasia', SITE_URL),
    _socials(),
    _copyright(),

    '</div>',
    '</body></html>',
  ].join("\n");
}

function buildVerificationText(userName, verifyLink) {
  return [
    "Hello " + userName + ",",
    "",
    "Welcome to " + SITE_NAME + "!",
    "",
    "Please verify your email by visiting the link below:",
    verifyLink,
    "",
    "If you did not create an account, you can safely ignore this email.",
    "",
    "— The " + SITE_NAME + " Team",
  ].join("\n");
}


// ── Password reset email ──────────────────────────────────────────────────────

function buildPasswordResetHtml(userName, resetLink, realEmail) {
  return [
    '<!DOCTYPE html>',
    '<html><head><meta charset="UTF-8"><title>Reset Your Password - ' + SITE_NAME + '</title></head>',
    '<body style="margin:0;padding:0;background:#f6f6f6;font-family:Arial,Helvetica,sans-serif;color:#000;">',
    '<div style="max-width:600px;margin:0 auto;background:#ffffff;padding:28px;">',

    _logo(),
    _divider(),

    TEST_MODE ? _testBanner(realEmail) : '',

    '<h1 style="font-size:22px;margin-bottom:14px;">Reset your password</h1>',
    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">Hello ' + esc(userName) + ',</p>',
    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">',
    '  We received a request to reset the password for your <strong>' + SITE_NAME + '</strong> account.',
    '  Click the button below to set a new password.',
    '</p>',

    _highlight('This link expires in 24 hours. If you did not request a reset, ignore this email.'),

    _actionButton('Reset Password', resetLink),

    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">',
    '  If the button above does not work, copy and paste the link below into your browser:',
    '</p>',
    _linkBox(resetLink),

    '<p style="font-size:15px;line-height:1.6;margin-top:16px;">&#8212; The ' + SITE_NAME + ' Team</p>',

    _divider(),
    _ctaButton('Visit Ocasia', SITE_URL),
    _socials(),
    _copyright(),

    '</div>',
    '</body></html>',
  ].join("\n");
}

function buildPasswordResetText(userName, resetLink) {
  return [
    "Hello " + userName + ",",
    "",
    "We received a request to reset your " + SITE_NAME + " password.",
    "",
    "Reset your password by visiting the link below:",
    resetLink,
    "",
    "This link expires in 24 hours.",
    "If you did not request a reset, you can safely ignore this email.",
    "",
    "— The " + SITE_NAME + " Team",
  ].join("\n");
}


// ── Shared building blocks ────────────────────────────────────────────────────

function _logo() {
  return '<div style="text-align:center;margin-bottom:18px;"><img src="' + LOGO_URL + '" alt="' + SITE_NAME + '" style="max-width:160px;"></div>';
}

function _divider() {
  return '<div style="height:4px;background:#FFD400;margin:24px 0;"></div>';
}

function _highlight(text) {
  return '<div style="background:#FFD400;padding:12px;font-weight:bold;text-align:center;margin:22px 0;">' + text + '</div>';
}

/** Primary black CTA — used for the action button (Verify Email / Reset Password). */
function _actionButton(label, url) {
  return [
    '<div style="text-align:center;margin:30px 0;">',
    '  <a href="' + url + '" style="background:#000;color:#fff;text-decoration:none;padding:14px 24px;font-size:15px;font-weight:bold;border-radius:5px;display:inline-block;">' + label + '</a>',
    '</div>',
  ].join("\n");
}

/** Secondary yellow CTA — used for footer links (Visit Ocasia). */
function _ctaButton(label, url) {
  return [
    '<div style="text-align:center;margin:16px 0;">',
    '  <a href="' + url + '" style="background:#FFD400;color:#000;padding:10px 16px;text-decoration:none;font-size:14px;font-weight:bold;border-radius:4px;">' + label + '</a>',
    '</div>',
  ].join("\n");
}

function _linkBox(url) {
  return '<div style="font-size:13px;background:#f2f2f2;padding:12px;word-break:break-all;">' + url + '</div>';
}

function _socials() {
  var base  = "https://staticassets.netlify.app/public/icons/social/";
  var links = [
    ["https://www.instagram.com/lamla.io",                       base + "instagram.png"],
    ["https://www.linkedin.com/company/lamla-ai",                base + "linkedin.png"],
    ["https://www.facebook.com/people/LamlaAI/61578006032583/",  base + "facebook.png"],
    ["https://x.com/lamla.ai",                                   base + "twitter.png"],
  ];
  var items = links.map(function(l) {
    return '<a href="' + l[0] + '" style="margin:0 6px;display:inline-block;"><img src="' + l[1] + '" width="20" height="20"></a>';
  });
  return '<div style="text-align:center;margin:18px 0;">' + items.join("") + '</div>';
}

function _copyright() {
  return '<p style="font-size:12px;color:#555;text-align:center;margin-top:8px;">© 2026 ' + SITE_NAME + '. All rights reserved.<br>Study Smarter, Perform Better.</p>';
}

function _testBanner(realEmail) {
  return '<p style="background:#fff3cd;border:1px solid #ffc107;padding:8px 12px;font-size:13px;margin-bottom:16px;">&#9888; TEST MODE &#8212; real recipient was: ' + esc(realEmail) + '</p>';
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
