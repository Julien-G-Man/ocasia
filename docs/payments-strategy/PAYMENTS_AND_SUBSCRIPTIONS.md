# Payments & Subscription Strategy

This document is the single source of truth for how Ocasia handles money —
now and in the future. It covers the voluntary donation phase, the planned
subscription model, Paystack integration specifics, and the business decisions
behind each choice.

Read this before writing a single line of payment code.

---

## Two Phases, One Document

### Phase 1 — Voluntary Donations (Now)
Anyone who wants to support the platform can make a one-time payment of any
amount. No feature gating. No paywall. No subscription logic. The platform
remains completely free. Donors get a badge on their profile.

This phase costs almost nothing to implement and generates goodwill while
the user base grows.

### Phase 2 — Freemium Subscription (After Tier 2 Features Ship)
Once the platform has enough value to justify a paywall — specifically after
Tier 2 intelligent features are live — a Pro subscription is introduced at
10 GHS per month. The free tier remains, but with meaningful limits.

Do not rush Phase 2. A paywall on a platform that isn't yet irreplaceable
drives users away permanently. The platform needs to earn it first.

---

## Payment Provider: Paystack

**Why Paystack:**
- Designed for Ghana and West Africa — GHS is a native currency, not a conversion
- Handles Mobile Money (MTN, Vodafone, AirtelTigo) which is dominant in Ghana
- No monthly fee — pay only per transaction
- Webhook-driven subscription lifecycle (renewals, failures, cancellations)
- Sandbox environment available with no documents required
- Strong developer documentation and active support

**Account Setup (Do This First):**
1. Sign up at paystack.com — immediately in Test Mode, no documents needed
2. Create a monthly Plan in the Paystack dashboard: name "Pro Monthly",
   amount 1000 pesewas (= 10 GHS), interval monthly — note the Plan Code
3. Register your webhook URL pointing to your server
4. Submit verification documents when ready to go live (see Document Requirements below)

**Document Requirements (Ghana):**

Starter Account (personal — simplest path for indie projects):
- Valid Ghana Card or Passport
- GPS / digital address (get from the Ghana Post app)
- Personal mobile money or bank account for payouts

Registered Business Account (if the project is formally registered):
- Business registration certificate from Registrar General's Department
- Tax Identification Number (TIN)
- Corporate bank account (name must exactly match the registration certificate)
- Director details and IDs

You can build and test the entire integration in sandbox before submitting
any documents. Documents are only required to go live with real money.

**Transaction Fees:**
- 1.95% per successful transaction — no flat fee
- On a 10 GHS subscription: Paystack takes ~0.20 GHS, you receive ~9.80 GHS
- No monthly platform fee
- High-volume merchants can negotiate lower rates

**Payout Schedule:**
- Automatic settlement next working day (T+1)
- Mobile Money: no minimum payout threshold
- Bank Account: minimum GHS 50 before payout is released
- Manual payouts (including weekends) available for registered businesses on request

**Important Considerations:**
- E-Levy: Paystack handles this automatically if your TIN is verified with GRA
- Chargebacks: Paystack holds disputed funds during investigation — keep webhook
  handling robust so subscription state stays accurate during disputes
- Failed renewals: Paystack retries automatically; your webhook receives
  invoice.payment_failed — decide on grace period (recommend 3 days) before downgrading
- Refunds: The 1.95% fee is not returned to you on refunded transactions
- International cards: GHS account processes GHS by default; international card
  acceptance requires a separate approval from Paystack

---

## Phase 1: Voluntary Donations

### Status: LIVE (2026-06-22)

Phase 1 is fully live in production with real payments. Paystack account is activated, live keys are on Render, and the end-to-end flow has been tested with a real GHS transaction (authenticated + anonymous, webhook confirmed).

**What was built:**

Backend — `backend/apps/subscriptions/`:
- `models.py` — `Donation` model (user FK nullable, amount, reference, status, email, paid_at, created_at)
- `paystack.py` — thin wrapper for Paystack Initialize + Verify Transaction API calls (timeout: 15s)
- `views.py` — three endpoints: initiate, verify, webhook
- `helpers.py` — `mark_donation_paid` (idempotent, row-locked), `generate_reference`, `WEBHOOK_HANDLERS`
- `urls.py` registers both `/webhook/` and `/webhook` (no trailing slash) — Paystack sends without slash; Django's `APPEND_SLASH` would redirect POST→GET which breaks webhook delivery
- `admin.py`, `apps.py`, `migrations/`
- Registered in `INSTALLED_APPS` and mounted at `/api/subscriptions/`

Security and reliability hardening added post-launch:
- `verify_donation` compares Paystack's confirmed amount against stored amount — mismatch is rejected
- `verify_donation` short-circuits immediately for already-resolved donations (no redundant Paystack call)
- Stale pending donations older than 30 minutes are auto-failed on next verify call
- `charge.abandoned` webhook handler added — Paystack fires this hours after an abandoned session
- `DonateThankyou.jsx` 15-second timeout prevents users being stuck forever if backend is down
- Cancelled payments return `{"status": "abandoned"}` (200, not 402) so frontend shows "Payment cancelled, no charge was made" instead of "Something went wrong"

User model (`backend/apps/accounts/models.py`):
- Added `is_donor = BooleanField(default=False)` — set once on donation confirmation, never unset
- Migration: `accounts/migrations/0002_user_is_donor.py`
- `user_to_dict` updated to include `is_donor` in all user payloads

Frontend:
- `frontend/src/pages/Donate/Donate.jsx` — donation form with suggested amounts, anonymous email field, redirects to Paystack hosted payment page
- `frontend/src/pages/Donate/DonateThankyou.jsx` — verifies payment on load, shows success / cancelled / failed states with appropriate messaging
- Routes: `/donate` and `/donate/thank-you`
- `frontend/src/services/payments.js` — `initiateDonation`, `verifyDonation`

Donate button placements:
- **Navbar** — unauthenticated users only: solid blue "Support Us" button, right of Login. Not shown to logged-in users (they have the sidebar link).
- **AppShell sidebar** — "Support Ocasia" with heart icon, above the user section. Visible to all authenticated users on every page.
- **Quiz Results page** — nudge bar after the rating section: "Enjoying Ocasia? Help keep it free for every student."
- **Footer** — Quick Links column

Settings: `PAYSTACK_PUBLIC_KEY` and `PAYSTACK_SECRET_KEY` in `settings.py` (read from env). Live keys active on Render.

**Critical deployment note:**
The Paystack webhook URL registered in the dashboard must include a trailing slash:
```
https://your-api.onrender.com/api/subscriptions/webhook/
```
Without it, Django's `APPEND_SLASH` redirects POST → GET (301), and the webhook endpoint returns 405. The code now also accepts the URL without a trailing slash as a fallback.

**What was intentionally deferred:**
- Donor badge / "Supporter" visual badge — deferred until social profiles and
  group features (group quizzes, competitions) are built. `is_donor` flag is
  already set and ready; the badge display is the only missing piece.

---

### Original Spec (kept for reference)

A single page on the platform: "Support Our Work"

Content:
- Short explanation of what the platform is and who built it
- Clear statement that the platform is and will remain free
- A "Donate" button that opens a Paystack payment page
- A thank-you message after payment

The implementation is a single Paystack transaction — not a subscription,
not a recurring charge, not a plan. The user enters any amount they choose
(suggest a minimum of 5 GHS), pays once, and that is the end of the flow.

### Backend (Minimal)

One new Django app: `subscriptions` (plant it now, grow it in Phase 2)

For Phase 1, this app needs only:

**Model: Donation**
```
user          ForeignKey → User (nullable — allow anonymous donations)
amount        DecimalField (in GHS)
reference     CharField — Paystack transaction reference (unique)
status        CharField — pending / success / failed
email         EmailField — for anonymous donors
paid_at       DateTimeField (nullable)
created_at    DateTimeField
```

**Endpoints:**
```
POST /api/subscriptions/donate/initiate/
  → Calls Paystack Initialize Transaction API
  → Returns { authorization_url, reference }

GET  /api/subscriptions/donate/verify/?reference=xxx
  → Calls Paystack Verify Transaction API
  → If success: marks Donation as paid, sets is_donor=True on User
  → Returns { status, amount }

POST /api/subscriptions/webhook/
  → Receives Paystack event notifications
  → For Phase 1: only handles charge.success
  → Always verify webhook signature before processing
```

**Donor badge:**
The `is_donor` boolean is set on the User model on donation confirmation
(used later for LLM budget in Tier 3 and for displaying a badge when social
profiles ship). This flag is set once and never unset — a donor is always a donor.
The visual badge display is deferred to the social features phase.

### Paystack Initialize Transaction Call

```
POST https://api.paystack.co/transaction/initialize
Authorization: Bearer {PAYSTACK_SECRET_KEY}
Content-Type: application/json

{
  "email": user.email,
  "amount": amount_in_pesewas,   // user-specified, minimum 500 (= 5 GHS)
  "currency": "GHS",
  "callback_url": "https://yoursite.com/donate/thank-you",
  "metadata": {
    "user_id": user.id,          // null for anonymous
    "type": "donation"
  }
}
```

Response includes `authorization_url` — redirect the user there.
They pay on Paystack's hosted page. You never handle card data.

### Webhook Signature Verification

Always verify the signature before processing any webhook event.
An unverified webhook is a security hole — anyone can POST fake payment
confirmations to your endpoint.

```python
import hmac
import hashlib

def verify_paystack_signature(request):
    paystack_signature = request.headers.get("x-paystack-signature", "")
    secret = settings.PAYSTACK_SECRET_KEY.encode("utf-8")
    body = request.body
    expected = hmac.new(secret, body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, paystack_signature)
```

Reject any request where this check fails with HTTP 400.
Log rejected requests for audit purposes.

### Environment Variables (Phase 1)

```
PAYSTACK_PUBLIC_KEY=pk_test_...      # used on frontend for Paystack.js
PAYSTACK_SECRET_KEY=sk_test_...      # backend only — never expose in frontend
PAYSTACK_WEBHOOK_SECRET=             # same value as PAYSTACK_SECRET_KEY
```

Switch to `pk_live_` and `sk_live_` when going live.
Never commit secret keys to version control.

---

## Phase 2: Freemium Subscription Model

### When to Activate

Phase 2 launches after all Tier 2 features are live and the platform has
demonstrated clear value. The decision trigger is qualitative, not a user count:

> "Would a student feel meaningfully worse off if they lost access to the
> platform tomorrow?" If yes, a subscription is justified. If no, wait.

Specifically, wait until these are live and working well:
- Weak area detection feeding personalised recommendations
- Post-quiz mistake analysis
- Smart material summariser
- Socratic tutor mode
- Weekly digest emails

A paywall before these features exist is just friction. After them, it is fair.

### Plan

**Free Tier (always available — never removed):**
- Quizzes: 10 per month
- Chat messages: 30 per month
- Flashcard decks: 3 maximum
- Flashcard reviews: unlimited (SM-2 scheduling is too valuable to gate)
- Materials: browse and download unlimited, upload up to 3
- No access to post-quiz mistake analysis
- No access to AI mistake patterns (weekly batch)
- No Socratic tutor mode
- Standard LLM daily budget

**Pro Tier — 10 GHS/month:**
- Everything unlimited
- Post-quiz mistake analysis
- Weekly AI mistake patterns with auto-generated flashcard decks
- Socratic tutor mode
- Higher daily LLM budget
- Donor badge (if they were already a donor, they keep it)
- Priority support

The free tier should feel genuinely useful — enough to build a habit.
The Pro tier should feel like the obvious next step once the habit is formed.

### Subscription Model

**Paystack Plan:**
Create a Plan in the Paystack dashboard (do this once manually):
- Name: Pro Monthly
- Amount: 1000 pesewas (10 GHS)
- Interval: monthly
- Note the Plan Code (PLN_xxx) — store it in environment variables

**Recurring billing flow:**
1. User clicks "Upgrade to Pro"
2. Frontend calls `POST /api/subscriptions/initiate/`
3. Backend calls Paystack Initialize Transaction with `plan: PAYSTACK_PLAN_CODE`
4. Returns `authorization_url` — redirect user to Paystack
5. User pays with card or mobile money
6. Paystack redirects to callback URL with `reference` query param
7. Backend calls `GET /api/subscriptions/verify/?reference=xxx`
8. Paystack confirms payment and creates a recurring subscription automatically
9. Backend upgrades user's subscription to Pro
10. Every month: Paystack charges automatically, sends `charge.success` webhook
11. Backend receives webhook, updates `current_period_end`
12. If payment fails: `invoice.payment_failed` webhook → grace period → downgrade if unresolved

### Additional Models (Phase 2)

**Subscription model (extend existing app):**
```
user                    OneToOneField → User
plan                    CharField — free / pro
status                  CharField — active / cancelled / past_due / expired
paystack_customer_code  CharField — CUS_xxx (from Paystack)
paystack_subscription_code  CharField — SUB_xxx (from Paystack, for cancellation)
paystack_email_token    CharField — used for managed subscription links
current_period_start    DateTimeField
current_period_end      DateTimeField
cancelled_at            DateTimeField (nullable)
created_at              DateTimeField
updated_at              DateTimeField
```

Auto-create a Subscription with plan=free via Django signal on User creation.
This means every user always has a Subscription row — no null-checking needed.

**PaymentHistory model:**
```
user        ForeignKey → User
amount      DecimalField (GHS)
currency    CharField (default GHS)
reference   CharField (unique) — Paystack transaction reference
type        CharField — donation / subscription
status      CharField — success / failed / refunded
paid_at     DateTimeField (nullable)
created_at  DateTimeField
```

Every payment event (donation or subscription) creates a PaymentHistory row.
This is your audit trail. Never delete these rows.

### Webhook Events to Handle (Phase 2)

| Event | Action |
|---|---|
| charge.success | Confirm payment, activate/renew Pro, update period_end |
| subscription.create | Save paystack_subscription_code to Subscription model |
| subscription.disable | Downgrade to free at end of current period |
| invoice.payment_failed | Set status=past_due, start grace period, email user |
| invoice.update | Update payment record status |
| customeridentification.success | Optional: log KYC completion for compliance |

All webhook handlers must be idempotent — safe to receive the same event twice.
Paystack may deliver duplicate events. Use the transaction reference as the
deduplication key.

### Plan Enforcement

Enforcement happens at the view layer, not the model layer. Before any
AI-intensive or premium action, check the user's subscription:

```python
def require_pro(view_func):
    """Decorator that checks Pro subscription for gated features."""
    def wrapper(request, *args, **kwargs):
        sub = request.user.subscription
        if sub.plan != "pro" or sub.status != "active":
            return JsonResponse(
                {
                    "error": "pro_required",
                    "message": "This feature is available on the Pro plan.",
                    "upgrade_url": "/api/subscriptions/initiate/"
                },
                status=403
            )
        return view_func(request, *args, **kwargs)
    return wrapper
```

**Monthly usage limits (free tier):**
Track usage in Redis per user per month:

```
Key pattern:  usage:{user_id}:{feature}:{YYYY-MM}
Features:     quizzes, chat_messages, material_uploads
TTL:          set to expire end of month
```

On each action, increment the counter. If it exceeds the free limit, return:
```json
{
  "error": "limit_reached",
  "feature": "quizzes",
  "limit": 10,
  "used": 10,
  "resets": "2025-02-01",
  "upgrade_url": "/api/subscriptions/initiate/"
}
```

The frontend handles this response by showing an upgrade prompt, not an error page.
The message should be informative and encouraging, not punitive.

### Additional Endpoints (Phase 2)

```
POST   /api/subscriptions/initiate/          Start Paystack checkout (subscription)
GET    /api/subscriptions/verify/            Verify after redirect
POST   /api/subscriptions/webhook/           Receive all Paystack events
GET    /api/subscriptions/status/            Current plan, usage, period dates
POST   /api/subscriptions/cancel/            Cancel recurring subscription
GET    /api/subscriptions/history/           Payment history for the user
GET    /api/subscriptions/manage-link/       Paystack managed subscription link
```

The manage-link endpoint returns Paystack's hosted subscription management URL
where users can update their card, view billing history, and cancel — without
you building any of that UI yourself.

---

## Environment Variables (Full List)

```
# Phase 1 (needed immediately)
PAYSTACK_PUBLIC_KEY=pk_test_...
PAYSTACK_SECRET_KEY=sk_test_...

# Phase 2 additions
PAYSTACK_PLAN_CODE=PLN_xxx          # monthly plan code from Paystack dashboard
PAYSTACK_CALLBACK_URL=https://yoursite.com/payment/verify

# Switch to live keys when documents approved:
# PAYSTACK_PUBLIC_KEY=pk_live_...
# PAYSTACK_SECRET_KEY=sk_live_...
```

---

## The Django App Structure

Everything lives in one app: `backend/apps/subscriptions/`

```
subscriptions/
  __init__.py
  apps.py
  models.py          # Donation, Subscription, PaymentHistory
  views.py           # Initiate, verify, webhook, status, cancel
  urls.py
  paystack.py        # Paystack API client (thin wrapper around requests)
  enforcement.py     # require_pro decorator, usage limit checks
  signals.py         # auto-create Subscription on User creation
  tasks.py           # grace period expiry, dunning emails
  admin.py
  migrations/
```

Register in `INSTALLED_APPS` and include URLs at `/api/subscriptions/`.

Keep payment logic entirely inside this app. Other apps import only
`from apps.subscriptions.enforcement import require_pro` and the usage
check helpers. No other app should know about Paystack directly.

---

## Go-Live Checklist

Before switching to live Paystack keys:

- [ ] Webhook endpoint verified and signature check passing in production
- [ ] HTTPS enforced on all payment endpoints (already enforced in settings)
- [ ] Test the full donation flow end-to-end in sandbox
- [ ] Test the subscription initiation, renewal webhook, and cancellation in sandbox
- [ ] Test failed payment grace period flow
- [ ] Paystack account documents submitted and approved
- [ ] Live Plan created in Paystack dashboard (separate from test plan)
- [ ] PAYSTACK_PLAN_CODE updated to live plan code
- [ ] All secret keys rotated from test to live in environment variables
- [ ] Admin dashboard shows Donation and PaymentHistory records correctly
- [ ] Donor badge awards correctly on payment confirmation
- [ ] Unsubscribe flow tested (user can cancel without contacting support)

---

## Guiding Principles

**1. Never punish users for being on the free tier.**
The free tier message is always "You've reached your limit for this month."
Never "You need to pay to use this." The framing matters.

**2. Donors are permanent.**
A user who donated 5 GHS once is marked as a donor forever, even if their
Pro subscription lapses. Loyalty deserves recognition.

**3. The webhook is the backbone.**
The Paystack API call at checkout is a fallback confirmation.
The webhook is the authoritative source of truth for subscription state.
Build the webhook handler first and build it to be rock solid.

**4. Graceful degradation over hard blocking.**
When a free user hits a limit, their data is not deleted or hidden.
They can still view their history, their flashcard decks, their quiz results.
Only new AI-intensive actions are limited.

**5. Make cancellation easy.**
A user who cannot cancel easily becomes a public complaint.
The manage-link endpoint gives users a Paystack-hosted page to cancel
without any support interaction. This protects your reputation.
