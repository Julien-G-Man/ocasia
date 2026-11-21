# Dashboard Features

## Overview

The Dashboard system provides two separate experience layers:

1. **User Dashboard**: Personal statistics, profile management, and activity overview.
2. **Admin Dashboard**: System-wide statistics, user management, activity auditing, settings, and admin profile pages.

The frontend now uses route-based admin pages under `/admin-dashboard/*` instead of a single tabbed screen. The admin experience is rendered inside a dedicated `AdminAppShell` wrapper that keeps the standard authenticated top navbar while using an admin-styled sidebar.

### Admin frontend routes

- `/admin-dashboard/overview` - Admin summary, usage trends, recent activity, token estimates, and ratings
- `/admin-dashboard/users` - User management table
- `/admin-dashboard/content` - Content totals and anonymous usage review
- `/admin-dashboard/settings` - System settings and feature toggles
- `/admin-dashboard/activity` - Activity feed explorer
- `/admin-dashboard/ratings` - Quiz ratings history
- `/admin-dashboard/clashes` - All Clash sessions table
- `/admin-dashboard/clashes/:code` - Individual Clash detail (leaderboard, player stats)
- `/admin-dashboard/user/:id` - User analytics detail page
- `/admin-dashboard/profile` - Admin profile page (same profile form, admin shell)

`/admin-dashboard` redirects to `/admin-dashboard/overview`.

All admin endpoints require `IsAdminUser` permission (authenticated + `is_admin=true`). User endpoints are accessible to any authenticated user.

---

## User Dashboard

### Recent Activity

The user dashboard merges four activity sources into a single chronological list (newest first, limited to 6 items):

| Source | API called | Display |
|---|---|---|
| Quizzes | `GET /api/quiz/history/` | Subject · `Score: N%` · date; `N%` badge on right |
| Flashcard decks | `GET /api/flashcards/history/` | Title · `N cards` · date |
| Uploaded materials | `GET /api/materials/mine/` | Title · size + downloads · date |
| Clash games | `GET /api/clash/my/` | Subject · `N players · NQ` · date; `#rank of N` / `N pts` on right |

Clash items only appear for **finished** rooms. The `GET /api/clash/my/` endpoint returns:

```json
{
  "clashes": [
    {
      "room_code": "AB12CD",
      "subject": "Cell Biology",
      "difficulty": "medium",
      "num_questions": 10,
      "score": 9500,
      "rank": 2,
      "player_count": 8,
      "is_host": false,
      "finished_at": "2026-05-28T14:30:00Z"
    }
  ]
}
```

---

### `GET /api/dashboard/stats/`

Retrieve the authenticated user's personal statistics.

**Response (200 OK):**
```json
{
  "total_quizzes": 15,
  "average_score": 82.5,
  "total_flashcard_sets": 3,
  "total_chats": 8,
  "study_streak": 5,
  "total_ratings": 2,
  "average_experience_rating": 4.5,
  "weak_areas": [
    { "topic": "Thermodynamics", "accuracy": 38.0, "total_questions": 20 },
    { "topic": "Cell Biology",   "accuracy": 55.0, "total_questions": 12 }
  ]
}
```

`weak_areas` — up to 3 lowest-accuracy topics for the user (min 3 questions attempted). Empty array if the user has no qualifying topic history. Drives the weak areas card on the dashboard overview and the tutor performance injection.

**Security:**
- Requires authentication.
- Returns only the authenticated user's data (no user ID parameter).

---

### `GET /api/dashboard/user/activity/`

Retrieve the authenticated user's recent activity timeline.

**Query Parameters:**
- `period`: `day`, `week`, `month`, `quarter`, `year`, or `all` (default: `day`)
- `limit`: Maximum items to return (default: 50, max: 500)
- `offset`: Pagination offset (default: 0)

**Response (200 OK):**
```json
{
  "activity": [
    {
      "type": "quiz",
      "text": "completed a Math quiz (85%)",
      "created_at": "2025-01-15T10:30:00Z"
    },
    {
      "type": "flashcards",
      "text": "created flashcard deck 'Biology'",
      "created_at": "2025-01-14T15:45:00Z"
    },
    {
      "type": "chat",
      "text": "chat session (12 messages)",
      "created_at": "2025-01-14T09:20:00Z"
    }
  ],
  "total": 156
}
```

**Security:**
- Requires authentication.
- Returns only the authenticated user's activity.

---

## Admin Dashboard API

### `GET /api/dashboard/admin/stats/`

Retrieve system-wide statistics.

**Response (200 OK):**
```json
{
  "total_users": 1250,
  "verified_users": 1100,
  "total_quizzes": 5420,
  "total_quiz_questions": 43200,
  "average_score": 78.3,
  "total_materials": 340,
  "total_flashcard_decks": 520,
  "total_flashcards": 8900,
  "total_chat_sessions": 2100,
  "total_chat_messages": 42000,
  "total_clashes": 87,
  "avg_quizzes_per_user": 4.34,
  "avg_chats_per_user": 1.68,
  "activity_24h": {
    "new_users": 12,
    "quizzes": 45,
    "decks": 8,
    "flashcards": 120,
    "chat_messages": 350,
    "uploaded_materials": 5,
    "clashes": 3,
    "anonymous_api_hits": 64
  },
  "unauthenticated_usage_24h": {
    "quiz_requests": 18,
    "chat_requests": 31,
    "flashcard_requests": 15,
    "estimated_tokens": 4275,
    "source": "anonymous_api_events",
    "retention_hours": 24
  },
  "recent_activity": [
    {
      "type": "chat",
      "text": "user_123 created chat session (5 messages)",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "estimated_tokens": {
    "chat": 10500000,
    "quiz": 10800000,
    "flashcards": 2225000,
    "clash": 435000,
    "total": 23960000,
    "method": "chars_div_4_estimate",
    "note": "Approximation only. Provider billing tokens may differ."
  }
}
```

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).

---

### `GET /api/dashboard/admin/usage-trends/?days=14`

Retrieve usage trends over a specified period.

**Query Parameters:**
- `days`: Number of days to analyze (default: 14, max: 365)

**Response (200 OK):**
```json
{
  "days": 14,
  "labels": ["2025-01-01", "2025-01-02"],
  "series": {
    "new_users": [5, 8],
    "quizzes": [32, 45],
    "decks": [7, 10],
    "chat_messages": [250, 340],
    "uploaded_materials": [2, 3],
    "clashes": [1, 2]
  }
}
```

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).

---

### `GET /api/dashboard/admin/activity/?period=week&limit=50&offset=0`

Retrieve system-wide activity feed with flexible filtering.

**Query Parameters:**
- `period`: `day`, `week`, `month`, `quarter`, `year`, or `all` (default: `day`)
- `custom_days`: Override `period` with a custom number of days (1–365)
- `limit`: Maximum items to return (default: 50, max: 500)
- `offset`: Pagination offset (default: 0)

**Response (200 OK):**
```json
{
  "activities": [
    {
      "type": "quiz",
      "actor": "user_456",
      "text": "completed a History quiz (92%)",
      "created_at": "2025-01-15T10:30:00Z"
    },
    {
      "type": "flashcards",
      "actor": "user_789",
      "text": "created flashcard deck 'French Vocabulary' (Languages)",
      "created_at": "2025-01-15T09:15:00Z"
    },
    {
      "type": "clash",
      "actor": "user_123",
      "text": "hosted a Clash on 'Cell Biology' (8 players, medium)",
      "created_at": "2025-01-15T08:45:00Z"
    }
  ],
  "total": 1253,
  "counts": {
    "quiz": 540,
    "flashcards": 120,
    "chat": 580,
    "material": 10,
    "clash": 3
  },
  "period": "week"
}
```

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).

---

### `GET /api/dashboard/admin/anonymous-usage/?limit=200`

Retrieve anonymous API activity from the rolling last 24 hours.

**Query Parameters:**
- `limit`: Maximum events to return (default: 200, max: 500)

**Response (200 OK):**
```json
{
  "retention_hours": 24,
  "deleted_expired": 12,
  "total_last_24h": 64,
  "unique_sessions_last_24h": 27,
  "top_paths": [
    { "path": "/api/tutor/chat/", "count": 31 },
    { "path": "/api/quiz/generate/", "count": 18 }
  ],
  "by_status": [
    { "status_code": 200, "count": 59 },
    { "status_code": 429, "count": 5 }
  ],
  "events": [
    {
      "id": 2048,
      "created_at": "2026-04-15T10:18:02.123456+00:00",
      "method": "POST",
      "path": "/api/tutor/chat/",
      "query_string": "",
      "status_code": 200,
      "request_chars": 314,
      "response_chars": 1580,
      "tutor_message": "Explain Newton's second law with an example.",
      "tutor_response": "Newton's second law states that force equals mass times acceleration...",
      "session_key": "abc123...",
      "ip_address": "203.0.113.1",
      "user_agent": "Mozilla/5.0"
    }
  ]
}
```

Notes:
- Events are automatically purged after 24 hours.
- Streaming chat responses are captured from the streamed output and stored in `tutor_response`.

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).

---

### `GET /api/dashboard/admin/users/?page=1&page_size=50`

Retrieve a paginated list of all users with activity summaries.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Users per page (default: 50, max: 200)

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": 1,
      "email": "user@example.com",
      "username": "john_doe",
      "is_email_verified": true,
      "is_admin": false,
      "date_joined": "Dec 15, 2024",
      "total_quizzes": 12,
      "total_flashcard_sets": 3,
      "total_chats": 5
    },
    {
      "id": 2,
      "email": "jane@example.com",
      "username": "jane_smith",
      "is_email_verified": true,
      "is_admin": false,
      "date_joined": "Jan 01, 2025",
      "total_quizzes": 5,
      "total_flashcard_sets": 1,
      "total_chats": 2
    }
  ]
}
```

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).

---

### `GET /api/dashboard/admin/users/<user_id>/`

Retrieve detailed information about a specific user, including activity summary and resource usage.

**Response (200 OK):**
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "john_doe",
    "first_name": "John",
    "last_name": "Doe",
    "is_email_verified": true,
    "is_admin": false,
    "date_joined": "Dec 15, 2024"
  },
  "summary": {
    "total_quizzes": 12,
    "total_quiz_questions": 96,
    "average_score": 85.2,
    "total_flashcard_decks": 3,
    "total_flashcards": 45,
    "total_chat_sessions": 5,
    "total_chat_messages": 120
  },
  "estimated_tokens": {
    "quiz": 24000,
    "flashcards": 11250,
    "chat": 30000,
    "total": 65250,
    "method": "chars_div_4_estimate"
  },
  "recent_activity": [
    {
      "type": "quiz",
      "text": "completed a Math quiz (85%)",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).

---

### `DELETE /api/dashboard/admin/users/<user_id>/`

Permanently delete a user account and all associated data.

**Response (200 OK):**
```json
{
  "detail": "User john_doe removed."
}
```

**Error Cases:**
```json
{
  "detail": "Cannot delete an admin."
}
```

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).
- Admin users cannot be deleted via this endpoint.
- Deletion is audited: logged with admin email, user ID, and timestamp.
- All related data (quizzes, flashcards, chat sessions, etc.) is cascade-deleted.

---

### `GET /api/dashboard/admin/settings/`

Retrieve system-wide settings (e.g., feature flags, maintenance mode).

**Response (200 OK):**
```json
{
  "maintenance_mode": false,
  "max_upload_size_mb": 100,
  "rate_limit_requests_per_hour": 100,
  "email_delivery_provider": "brevo"
}
```

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).

---

### `PUT /api/dashboard/admin/settings/`

Update system-wide settings.

**Request:**
```json
{
  "maintenance_mode": false,
  "max_upload_size_mb": 100,
  "rate_limit_requests_per_hour": 100
}
```

**Response (200 OK):**
```json
{
  "message": "Settings updated successfully.",
  "settings": {
    "maintenance_mode": false,
    "max_upload_size_mb": 100
  }
}
```

**Security:**
- **Admin-only endpoint** (requires `IsAdminUser` permission).

---

## Contact Form & Newsletter

### `POST /api/dashboard/contact/`

Submit a contact form message.

**Request:**
```json
{
  "title": "Feature Request",
  "name": "John Doe",
  "email": "john@example.com",
  "message": "It would be great if the app supported offline mode."
}
```

**Validation Rules:**
- `title`: required, 5–180 characters
- `name`: required, 2–120 characters
- `email`: required, valid email, max 254 characters
- `message`: required, 10–5,000 characters
- XSS prevention: `<`, `>`, and `script` tags are rejected

**Response (201 Created):**
```json
{
  "message": "Thank you for your message. We'll get back to you soon."
}
```

**Security:**
- No authentication required (public endpoint).
- Input validation prevents XSS attacks.
- Messages are sent to support email via multi-provider delivery.

---

### `POST /api/dashboard/newsletter/`

Subscribe to the newsletter.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Validation Rules:**
- `email`: required, valid email format, max 254 characters

**Response (201 Created):**
```json
{
  "message": "Subscription successful! Check your email for confirmation."
}
```

**Error (400):**
```json
{
  "email": ["This email is already subscribed."]
}
```

**Security:**
- No authentication required (public endpoint).
- Email validation is strict.
- Duplicate subscriptions are rejected.

---

## Permission Model

### IsAdminUser

The `IsAdminUser` permission class enforces admin-only access:

```python
class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'is_admin', False)
        )
```

**Applied to:**
- `AdminDashboardStatsView` (GET)
- `AdminUsageTrendsView` (GET)
- `AdminActivityFeedView` (GET)
- `AdminAnonymousUsageView` (GET)
- `AdminUsersListView` (GET)
- `AdminUserDetailView` (GET)
- `AdminUserDeleteView` (GET, DELETE)
- `AdminSystemSettingsView` (GET, PUT)

---

## Database Optimization

### Aggregation Queries

The admin dashboard uses efficient aggregation queries to compute statistics:

- `Count('id')` for total counts
- `Avg('score_percentage')` for average quiz scores
- `Sum('total_questions')` for total questions answered
- Subqueries to avoid N+1 problems on related counts

**Example:** User dashboard stats query:
```python
QuizSession.objects.filter(user=user).aggregate(
    total=Count('id'),
    avg=Avg('score_percentage'),
    total_questions=Coalesce(Sum('total_questions'), Value(0))
)
```

### Token Estimation

System estimates AI token usage based on character count:

```python
estimated_tokens = character_count / 4
```

This is an **approximation only**. Actual provider billing may differ based on:
- Tokenization algorithm
- Special character handling
- Language-specific encoding

---

## Pagination

Admin list endpoints support pagination:

```
GET /api/dashboard/admin/users/?page=1&page_size=50
```

- **Maximum page size:** 200 (`page_size` is clamped to 200)
- **Default page size:** 50
- **Out-of-range pages:** Redirect to last page

---

## Email Delivery (Contact & Newsletter)

Contact form and newsletter subscriptions use the **multi-provider email system** (see [ACCOUNTS.md](./ACCOUNTS.md#email-delivery) for details).

Providers are attempted in order:
1. Brevo
2. Resend
3. Django SMTP
4. Console (development)

---

## Related Documentation

- [Accounts & Authentication](./ACCOUNTS.md)
- [Security Reference](../security-reference/SECURITY.md)
- [Flashcards Feature](./FLASHCARDS.md)
