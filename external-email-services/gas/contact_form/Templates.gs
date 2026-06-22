// ═══════════════════════════════════════════════════════════════════════════════
// Templates.gs — Contact Form
//
// All email HTML lives here. Edit this file to change how emails look.
// Config values (SITE_NAME, LOGO_URL, etc.) are read from Config.gs.
// Logic that calls these functions lives in Code.gs.
// ═══════════════════════════════════════════════════════════════════════════════


// ── Admin notification ────────────────────────────────────────────────────────

function buildAdminNotificationHtml(name, email, title, message) {
  return [
    '<!DOCTYPE html>',
    '<html><head><meta charset="UTF-8"></head>',
    '<body style="margin:0;padding:0;background:#f6f6f6;font-family:Arial,sans-serif;color:#000;">',
    '<div style="max-width:600px;margin:0 auto;background:#fff;padding:28px;">',

    _logo(),
    _divider(),

    TEST_MODE ? _testBanner(email) : '',

    '<h2 style="font-size:20px;margin-bottom:16px;">New Contact Message</h2>',

    '<table style="width:100%;border-collapse:collapse;font-size:15px;line-height:1.6;">',
    '  <tr>',
    '    <td style="padding:8px 0;font-weight:bold;width:90px;">Subject:</td>',
    '    <td>' + esc(title) + '</td>',
    '  </tr>',
    '  <tr>',
    '    <td style="padding:8px 0;font-weight:bold;">Name:</td>',
    '    <td>' + esc(name) + '</td>',
    '  </tr>',
    '  <tr>',
    '    <td style="padding:8px 0;font-weight:bold;">Email:</td>',
    '    <td>' + esc(email) + '</td>',
    '  </tr>',
    '</table>',

    '<div style="margin-top:16px;">',
    '  <p style="font-weight:bold;margin-bottom:6px;">Message:</p>',
    '  <div style="background:#f2f2f2;padding:12px;font-size:15px;line-height:1.6;white-space:pre-wrap;">' + esc(message) + '</div>',
    '</div>',

    _divider(),
    _copyright(),

    '</div>',
    '</body></html>',
  ].join("\n");
}


// ── User acknowledgment ───────────────────────────────────────────────────────

function buildUserAcknowledgmentHtml(name, email, title) {
  return [
    '<!DOCTYPE html>',
    '<html><head><meta charset="UTF-8"></head>',
    '<body style="margin:0;padding:0;background:#f6f6f6;font-family:Arial,Helvetica,sans-serif;color:#000;">',
    '<div style="max-width:600px;margin:0 auto;background:#ffffff;padding:28px;">',

    _logo(),
    _divider(),

    TEST_MODE ? _testBanner(email) : '',

    '<h1 style="font-size:22px;margin-bottom:14px;">Message Received</h1>',
    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">Hi ' + esc(name) + ',</p>',
    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">',
    '  Thanks for contacting <strong>' + SITE_NAME + '</strong>. We received your message regarding',
    '  &#8220;<strong>' + esc(title) + '</strong>&#8221; and will get back to you as soon as possible.',
    '</p>',

    _highlight('We typically respond within 24&#8211;48 hours.'),

    '<p style="font-size:15px;line-height:1.6;margin-bottom:16px;">',
    '  If you did not send this message, you can safely ignore this email.',
    '</p>',
    '<p style="font-size:15px;line-height:1.6;">&#8212; The ' + SITE_NAME + ' Team</p>',

    _divider(),
    _ctaButton('Visit Ocasia', SITE_URL),
    _socials(),
    _copyright(),
    '<p style="font-size:11px;color:#888;text-align:center;margin-top:4px;">This email was sent to ' + esc(email) + ' for your security.</p>',

    '</div>',
    '</body></html>',
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

function _ctaButton(label, url) {
  return [
    '<div style="text-align:center;margin:16px 0;">',
    '  <a href="' + url + '" style="background:#FFD400;color:#000;padding:10px 16px;text-decoration:none;font-size:14px;font-weight:bold;border-radius:4px;">' + label + '</a>',
    '</div>',
  ].join("\n");
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

function stripTags(html) {
  return html.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}
