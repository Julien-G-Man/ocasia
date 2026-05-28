# Security Reference

## Non-Negotiables

- Never commit secrets (`.env`, API keys, credentials).
- Keep Django and FastAPI `FASTAPI_SECRET` synchronized and private.
- Keep CORS and CSRF allowlists explicit in production.

## Security Review Findings - 2026-05-28

This section records vulnerabilities and security gaps found by static review of the repository. Severity reflects likely production impact if the affected paths are reachable from the public web.

### High: Raw HTML Rendering in Rich Text Output

**Evidence:** `frontend/src/utils/richTextRenderer.jsx` imports `rehype-raw` and passes it to `ReactMarkdown`. That renderer is reused for chatbot responses, flashcards, quiz questions/results, and admin content views.

**Risk:** AI responses, uploaded study material, generated quiz/flashcard content, and stored admin-visible tutor responses can contain raw HTML. Rendering raw HTML creates an HTML injection surface and can become XSS if a dangerous element, attribute, URL transform bypass, or future markdown/plugin change slips through.

**Recommended fix:**
- Remove `rehypeRaw` unless raw HTML is a hard requirement.
- If raw HTML must be supported, add `rehype-sanitize` with a strict allowlist for educational formatting only.
- Keep links restricted to `http:`, `https:`, and `mailto:` and continue using `rel="noopener noreferrer"` for new tabs.
- Treat all AI/model output and extracted file text as untrusted user-controlled input.

### Medium: Google OAuth Endpoint Is Not Throttled

**Evidence:** `backend/apps/accounts/google_auth.py` sets `permission_classes = [AllowAny]`, but unlike signup/login/password-reset views in `backend/apps/accounts/views.py`, it does not set `throttle_classes = [AuthThrottle]`.

**Risk:** Attackers can repeatedly submit arbitrary Google ID tokens, causing repeated calls to Google's token verifier and noisy authentication attempts. This can become an abuse, logging, or availability issue. The existing documentation currently says Google auth shares the auth endpoint rate limit, but the code does not enforce that.

**Recommended fix:**
- Reuse `AuthThrottle` on `GoogleAuthView`.
- Consider separate throttle scopes for expensive third-party verification endpoints.

### Medium: Public Email and Feedback Endpoints Lack Abuse Controls

**Evidence:** `backend/apps/dashboard/views.py` exposes `ContactMessageView`, `NewsletterSubscribeView`, and `QuizFeedbackView` with `AllowAny`. Contact/newsletter views send email, and quiz feedback can create anonymous `QuizExperienceRating` records.

**Risk:** These endpoints can be abused for email spam, inbox flooding, database noise, and reputation damage with no authentication, CAPTCHA, per-IP throttle, or deduplication beyond session-based rating updates.

**Recommended fix:**
- Add DRF throttles for contact, newsletter, and anonymous feedback.
- Add CAPTCHA or a server-side proof/challenge for contact/newsletter forms.
- Deduplicate newsletter submissions by normalized email.
- Consider persisting contact submissions separately and queueing email delivery with spam scoring.

### Medium: Upload Extractors Trust File Extensions

**Evidence:** `backend/apps/quiz/extract_text.py` and `backend/apps/chatbot/file_extractor.py` choose parsers from `file.name` extension. `backend/apps/flashcards/extract_text_helper.py` adds MIME checks, but still relies on client-supplied metadata rather than file signatures.

**Risk:** An attacker can upload malformed or mislabeled files to parser libraries (`PyPDF2`, `python-docx`, `python-pptx`). The 10 MB size limit helps, but extension-only validation still leaves parser abuse and resource exhaustion risk. This is higher risk because these endpoints process untrusted documents synchronously in request flow.

**Recommended fix:**
- Validate file signatures with `python-magic` or equivalent before parsing.
- Keep extension and MIME checks, but treat them as hints only.
- Add parser timeouts or run extraction in an isolated worker.
- Enforce page/slide/paragraph count limits in addition to byte-size limits.
- Align quiz, flashcards, chatbot, profile image, and material upload validation rules.

### Medium: Long-Lived Auth Tokens Are Stored in localStorage

**Evidence:** both frontends read and write `auth_token` in `localStorage` and send it as `Authorization: Token ...`.

**Risk:** Any XSS or malicious browser extension can steal bearer tokens. DRF tokens are long-lived and only rotate on login/password reset/change/logout, so a stolen token remains useful until invalidated.

**Recommended fix:**
- Prefer secure, HttpOnly, SameSite cookies for browser sessions.
- If bearer tokens remain, add token expiry and refresh/rotation.
- Reduce XSS exposure first, especially the raw HTML rendering path above.

### Low: Material Upload Allows PDF-by-Extension

**Evidence:** `backend/apps/materials/serializers.py` rejects uploads only when both content type is not PDF and the filename does not end in `.pdf`. A non-PDF file named `*.pdf` can pass initial upload validation.

**Risk:** Public material downloads may host mislabeled content, and later extraction/download paths must defend against non-PDF payloads. `MaterialExtractView` checks the `%PDF` magic bytes before extraction, which reduces impact for extraction, but upload acceptance is still too loose.

**Recommended fix:**
- Require both a trusted content check and `.pdf` extension for material uploads.
- Verify first bytes before upload or immediately after upload.
- Store detected content type separately from client-supplied metadata.

### Low: Internal FastAPI Secret Comparison Is Plain String Equality

**Evidence:** `ai_service/core/middleware.py` compares `internal_secret != settings.FASTAPI_SECRET`.

**Risk:** If FastAPI is accidentally exposed publicly, a timing side channel may leak tiny information about the shared internal secret. The bigger control remains network isolation plus a strong secret.

**Recommended fix:**
- Use `hmac.compare_digest()` for `X-Internal-Secret`.
- Keep FastAPI private where possible and verify production ingress rules.

### Documentation Drift — Resolved

All four drift items identified in this review have been corrected:

- **Password complexity:** `validate_password_complexity` shown in this document does not exist in the codebase. `AUTH_PASSWORD_VALIDATORS` uses Django's four default validators only (min length 8, not common, not entirely numeric, not similar to user attributes). There is no uppercase/lowercase/special-character enforcement. The Password Security section below has been updated to reflect reality.
- **Token invalidation:** `ChangePasswordView` **does** delete existing tokens and issue a fresh one. The Token Security section below has been corrected.
- **XSS prevention:** `_no_html()` has been added to `ContactFormSerializer` — `title`, `name`, and `message` now reject inputs containing `<`, `>`, or `script`. The serializer section below is now accurate.
- **Google OAuth throttling:** `AuthThrottle` has been added to `GoogleAuthView`. The Rate Limiting section below is now accurate.

## CORS / CSRF

Django:

- `CORS_ALLOWED_ORIGINS` for frontend origins.
- `CSRF_TRUSTED_ORIGINS` aligned with same trusted origins.

FastAPI:

- `FASTAPI_ALLOWED_ORIGINS` for browser-origin validation.
- `/health` remains public.
- Other endpoints require `X-Internal-Secret`.

## Auth

### Authentication Backend

- **Dual-mode login:** Custom `EmailOrUsernameBackend` accepts either email or username.
- **DRF token auth:** All requests use `Authorization: Token <token>` (not session-based).
- **Token rotation:** Tokens are invalidated and regenerated on **every login**:
  - Old tokens for the user are immediately deleted.
  - New token is issued on successful login (email/username or Google OAuth).
  - This prevents token reuse attacks if credentials are compromised.

### Token Security

- **Stateless tokens:** Tokens don't expire automatically; invalidation is the primary control.
- **Logout:** Explicitly invalidates the user's current token.
- **Password change:** Invalidates all existing tokens and issues a fresh one (`ChangePasswordView` calls `Token.objects.filter(user=user).delete()` then creates a new token).
- **Sensitive operations:** Contact/newsletter endpoints are public; no token required.

### Google OAuth Security

**Custom Implementation (No django-allauth):**
- Backend verifies Google ID tokens using `google.oauth2.id_token.verify_oauth2_token()`
- Token verification happens server-side against Google's public keys
- No redirect-based OAuth flow (uses Google Sign-In SDK token exchange)

**Security Controls:**
1. **Client ID validation:** Only tokens signed for configured `GOOGLE_OAUTH_CLIENT_ID` are accepted
2. **Email verification:** Google OAuth users are auto-verified (`is_email_verified=True`) since Google confirms email ownership
3. **Token rotation:** Same token rotation policy as password login (old tokens deleted, new token issued)
4. **Rate limiting:** `AuthThrottle` applied — same 5/hour per IP as traditional login
5. **User matching:** Users matched by email (case-insensitive); duplicate signup prevented
6. **Profile data:** Only email, name, and profile picture extracted from Google token

**Google Cloud Console Configuration Required:**
- Authorized JavaScript origins: `http://localhost:3000`, `https://yourdomain.com`
- Authorized redirect URIs (if using redirect flow in future)
- API & Services → Credentials → OAuth 2.0 Client ID

**Environment Variables:**
```bash
# Backend .env
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret  # Not currently used in token-exchange flow
```

**Security Best Practices:**
- ✅ Never expose `GOOGLE_OAUTH_CLIENT_SECRET` to frontend
- ✅ Use environment variables, not hardcoded values
- ✅ Verify tokens server-side (never trust frontend-provided claims)
- ✅ Keep `google-auth` library updated for security patches
- ⚠️ Monitor failed verification attempts (logged as warnings)

### Rate Limiting (Brute Force Protection)

The following endpoints are rate-limited to **5 requests per hour per IP address** (`AuthThrottle`, scope `"auth"`):

- `POST /api/auth/signup/`
- `POST /api/auth/login/`
- `POST /api/auth/google/`
- `POST /api/auth/verify-email/`
- `POST /api/auth/resend-verification/`

The following public endpoints are rate-limited to **10 requests per hour per IP address** (`ContactThrottle`, scope `"contact"`):

- `POST /api/dashboard/contact/`
- `POST /api/dashboard/newsletter/`

**Configuration:**
```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'auth': '5/hour',
    }
}
```

**Response on limit exceeded:** HTTP 429 Too Many Requests with `Retry-After` header.

### Admin Authorization

The `IsAdminUser` permission class enforces admin-only endpoints:

```python
class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'is_admin', False)
        )
```

**Admin endpoints:**
- Dashboard stats, usage trends, activity feed
- User management (list, detail, delete)
- System settings (get, update)

**Non-admin users:** Receive HTTP 403 Forbidden.

## Input Validation & Sanitization

### Request Validation (DRF Serializers)

All user input is validated via Django REST Framework serializers with strict bounds:

**Accounts:**
- `email`: required, valid format, unique, max 254 characters
- `username`: required, 1–50 characters, alphanumeric with underscores/hyphens, unique
- `password`: required, validated by Django's `AUTH_PASSWORD_VALIDATORS` (min 8 chars, not common, not numeric-only, not similar to user attributes)
- `first_name`, `last_name`: optional, max 100 characters each

**Dashboard:**
- Contact form `title`: 5–180 characters
- Contact form `name`: 2–120 characters
- Contact form `message`: 10–5,000 characters
- Newsletter `email`: valid format, max 254 characters

**Flashcards:**
- `subject`: required, 1–255 characters
- `text`: required, 30–50,000 characters
- `question`: required, 1–2,000 characters
- `answer`: required, 1–4,000 characters
- `num_cards`: integer, 1–25

### XSS Prevention

`ContactFormSerializer` (title, name, message fields) rejects inputs containing:
- `<` or `>` (HTML tags)
- `script` (common XSS vector)

This check is enforced by `_no_html()` in `backend/apps/dashboard/serializers.py`. The newsletter endpoint accepts only a valid email address so no HTML check is needed there.

**Error response (400):**
```json
{
  "message": ["Input contains disallowed HTML content."]
}
```

### File Upload Validation

Profile image uploads are validated for:
- **MIME type:** JPEG, PNG, WebP, GIF only (user-provided content-type checked)
- **File size:** Max 5 MB
- **Planned:** Real content validation via `python-magic` library (checks actual file content, not just headers)

### SQL Injection Protection

- **Django ORM:** All database queries use parameterized ORM methods (no raw SQL with user input).
- **Aggregation queries:** Use Django's `Count`, `Avg`, `Sum`, `Coalesce`, etc. (all parameterized).

---

## Error Handling & Information Disclosure

### Generic Error Messages

API responses avoid verbose error details that could expose:
- Internal paths or file structures
- Stack traces or exception details
- Database schema information
- Valid vs. invalid usernames/emails (helps prevent enumeration)

**Example error responses:**
```json
{"detail": "Invalid credentials."}
{"detail": "User not found."}
{"error": "Invalid request data"}
```

### Logging

- Errors are logged server-side with full context (exception traces, user IDs, timestamps).
- Logs are **never** exposed to API clients.
- Sensitive data (passwords, tokens) is **never** logged (print statements removed).

**Audit logging:**
- Admin delete operations are logged: `logger.warning("Admin %s deleted user %s", admin_email, user_email)`

---

## Password Security

### Complexity Requirements

Passwords are validated via `password_validation.validate_password()` which enforces `AUTH_PASSWORD_VALIDATORS` (Django defaults):

- Minimum 8 characters (`MinimumLengthValidator`)
- Not a commonly used password (`CommonPasswordValidator`)
- Not entirely numeric (`NumericPasswordValidator`)
- Not too similar to username/email (`UserAttributeSimilarityValidator`)

There is **no** uppercase, lowercase, or special-character requirement enforced in code. The input validation section of this document previously listed a `validate_password_complexity` function — that function does not exist in the codebase.

### Password Storage

- Passwords are hashed using Django's default hasher (PBKDF2 with SHA256).
- Passwords are **never** stored in plaintext.
- Old passwords are not stored after password change.

---

## Payments Security

### Webhook Verification

Every incoming Paystack webhook is verified before any processing:

```python
expected = hmac.new(secret, request.body, hashlib.sha512).hexdigest()
if not hmac.compare_digest(expected, paystack_sig):
    return 400
```

- Uses `hmac.compare_digest` (constant-time) to prevent timing attacks.
- Rejects requests immediately if `PAYSTACK_SECRET_KEY` is not configured — an empty key would trivially pass its own HMAC, which would allow anyone to forge events.
- `@csrf_exempt` is applied only to the webhook endpoint; all other payment endpoints use standard DRF CSRF handling.

### Reference Sanitisation

Before a reference is interpolated into a Paystack API URL it is validated against `^[a-zA-Z0-9_-]+$`. Any reference that fails this check raises a `ValueError` and is rejected before the HTTP call is made, preventing path traversal.

### Input Validation

- **Amount:** Minimum GHS 5, maximum GHS 10,000. Enforced in the view before any Paystack call.
- **Email (anonymous donors):** Validated with `django.core.validators.validate_email` before being sent to Paystack.

### Idempotency & Race Safety

`mark_donation_paid` uses `select_for_update()` inside `transaction.atomic()`. This acquires a DB-level row lock so that duplicate webhook deliveries or a simultaneous verify + webhook cannot both confirm the same donation.

`PaymentHistory.get_or_create` on the unique `reference` field provides a second deduplication layer at the audit trail level.

### Audit Trail

Every confirmed payment (donation or subscription) creates an immutable `PaymentHistory` row. The Django admin disables deletion of these rows (`has_delete_permission` returns `False`).

### Secret Key Hygiene

- `PAYSTACK_SECRET_KEY` is backend-only — never sent to the frontend, never returned in API responses.
- `PAYSTACK_PUBLIC_KEY` is frontend-safe (used by Paystack.js to open the hosted payment page).
- Switch from `pk_test_` / `sk_test_` to `pk_live_` / `sk_live_` only after Paystack account documents are approved.

---

## Audit Trail & Monitoring

### Admin Actions

Admin delete operations are audited in server logs:
```python
logger.warning("AUDIT: Admin %s deleted user %s (%s) at %s", 
               request.user.email, target.id, target.email, timezone.now())
```

These logs can be monitored for:
- Unusual bulk deletions
- Off-hours admin activity
- Admin account misuse

### Planned Enhancements

- Persistent `AuditLog` model for admin actions (create, update, delete)
- Dashboard view for audit log inspection
- Automated alerts for unusual patterns

---

## Production Baselines

- HTTPS only.
- `SECURE_SSL_REDIRECT=True`
- secure cookies enabled (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)
- HSTS enabled.

## Incident Handling

If a secret leaks:

1. Rotate it immediately.
2. Redeploy all affected services.
3. Audit recent logs and access patterns.
4. Remove leaked value from history where possible.
