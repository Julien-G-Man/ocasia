# Flashcards Feature

## Frontend Pages

| File | Route | Sidebar |
|---|---|---|
| `FlashcardDecks.jsx` | `/flashcards` | Yes — shared sidebar (`activeId=""`) |
| `FlashcardCreate.jsx` | `/flashcards/create` | No |
| `FlashcardDeck.jsx` | `/flashcards/deck/:id` | No |
| `FlashcardStudy.jsx` | `/flashcards/study/:id` | No |

Styles live in `src/pages/Flashcards/Flashcards.css`.

### `/flashcards` — Deck List Page

Uses the shared `Sidebar` component with the same user nav items as Dashboard and Profile. Sidebar is always shown (unauthenticated users are redirected to login). No flashcard-specific items are added to the sidebar nav.

Sidebar nav behaviour: clicking "Past Quizzes" → `/quiz`; "Materials" / "Dashboard" → `/dashboard?tab=<id>`; "Profile" → `/profile`.

## Django Endpoints

From `backend/apps/flashcards/urls.py`:

- `POST /api/flashcards/ajax-extract-text/`
- `POST /api/flashcards/generate/`
- `GET /api/flashcards/decks/` (supports pagination: `?page=1&page_size=20`)
- `GET /api/flashcards/decks/:id/`
- `GET /api/flashcards/deck/:id/` (alias)
- `POST /api/flashcards/decks/save/`
- `POST /api/flashcards/save/` (alias)
- `POST /api/flashcards/review/`
- `POST /api/flashcards/explain/` (supports `card_id` for caching or `question`+`answer` for ad-hoc)
- `POST /api/flashcards/cards/update/` (edit card)
- `DELETE /api/flashcards/cards/:id/delete/` (also accepts POST)

## Models

- `Deck` (owner, title, subject, created_at)
- `Flashcard` (question, answer, explanation + SM-2 fields: repetition, interval, ease_factor, next_review)

## Fallback Behavior

If AI providers fail or return invalid shape:

- The Django AI engine returns deterministic fallback cards and `fallback_used: true`.
- Frontend also has client-side fallback card generation on request failure.

This ensures user flow does not hard-fail.

## Review Mapping (Study Mode)

- Again -> quality 0
- Hard -> quality 3
- Good -> quality 4
- Easy -> quality 5

Posted to `/api/flashcards/review/`.

## Security + Validation Hardening (Latest)

The Django flashcards endpoints now enforce stricter request validation and safer failure handling.

### Request Validation

- `POST /api/flashcards/generate/`
	- `subject`: required, non-empty, max 255 chars
	- `text`: required, 30-50,000 chars
	- `prompt`: optional, max 1,500 chars
	- `num_cards`: integer, range 1-25
	- `difficulty`: one of `beginner`, `intermediate`, `exam`

- `POST /api/flashcards/save/` and `POST /api/flashcards/decks/save/`
	- `subject`: required, non-empty, max 255 chars
	- `cards`: required array, 1-100 items
	- card shape:
		- `question`: required, 1-2,000 chars
		- `answer`: required, 1-4,000 chars

- `POST /api/flashcards/review/`
	- `card_id`: integer, >= 1
	- `quality`: integer, 0-5

- `POST /api/flashcards/explain/`
	- `card_id`: optional (for cached explanations)
	- `question`: required if no card_id, 1-2,000 chars
	- `answer`: required if no card_id, 1-4,000 chars

Validation failures now return a consistent `400` payload:

```json
{
	"error": "Invalid request data",
	"details": {"field_name": ["...validation message..."]}
}
```

### Error Handling and Upstream Safety

- Invalid/missing JSON body is handled with `400` (`Invalid JSON body` / `Request body is required`).
- Unexpected internal exceptions are now logged server-side and return generic error messages.
- Raw exception text is no longer exposed to API clients.
- AI provider upstream errors are mapped safely:
	- timeout -> `504`
	- request/upstream failures -> `503`

### Performance & Scalability (5k Concurrent Users)

The flashcards backend is optimized for high-traffic scenarios:

**Database:**
- Connection pooling: `CONN_MAX_AGE=600` (10 minutes)
- Indexed fields: `user_id`, `deck_id`, `created_at`, `next_review`

**AI Request Management:**
- Semaphore: Max 50 concurrent AI requests (prevents AI overload)
- Timeout: 45 seconds per AI request (prevents hanging requests)
- Error recovery: Automatic fallback generation on AI failure

**Caching:**
- Explanation caching: `card_id`-based cache prevents duplicate AI calls for same card
- Response compression: Gzip middleware for payloads > 1 KB

**Frontend Safeguards:**
- Request guards: Max 1 concurrent generation per user
- Debounced actions: 500ms debounce on save/update buttons

**Related Documentation:**
- [Security Reference](../security-reference/SECURITY.md) for input validation patterns
- [Accounts & Authentication](./ACCOUNTS.md) for rate limiting strategy
	- invalid upstream payload shape -> `502`

### Auth/Access Safety

- Deck deletion now checks ownership/existence before delete to avoid `NoneType` crash paths.
- All deck/card reads and writes continue to require valid token authentication.

### File Upload Security (Text Extraction)

- Accepted extensions are now explicitly allowlisted: `.pdf`, `.docx`, `.pptx`, `.txt`.
- MIME type is validated against extension allowlists (with `application/octet-stream` fallback support).
- Uploaded filename is normalized using `basename` before processing/logging.
- 10 MB max file size remains enforced.

## Scalability Hardening (2026-03-07)

This release adds practical safeguards for high concurrency, especially during AI traffic spikes.

### Django AI Layer

- Flashcard generation and explanation run in-process through `apps.core.ai_engine`
  with the shared provider cascade.
- Generation failures fall back to deterministic cards with `fallback_used: true`.
- Outbound provider HTTP clients use pooled connections and configurable timeouts.
- The legacy FastAPI flashcard service is retired.

### Django/Data Layer

- Added indexes for deck listing and due-card calculations:
	- Deck: `(user, created_at)`
	- Flashcard: `(deck, next_review)`
	- Flashcard: `(next_review)`
- Migration added: `backend/apps/flashcards/migrations/0002_flashcards_indexes.py`

### Frontend Resilience

- Added request timeout defaults in API client.
- Added centralized API error-message extraction for user-facing feedback.
- Flashcards pages now prevent duplicate in-flight actions:
	- duplicate generate
	- duplicate save
	- duplicate explain
	- duplicate review submissions
- Study mode now performs optimistic card advance with rollback on failed review writes.

### Important Capacity Note

For a target like ~5k concurrent users on AI features, these code changes improve graceful degradation and reduce failure cascades, but production capacity still depends on:

- horizontal scaling (multiple Django workers/instances),
- provider-side throughput limits,
- database sizing,
- queueing and observability.

Recommended operational approach is load testing with realistic prompts and setting semaphore/pool limits from observed provider and infra saturation points.

## UX Improvements (2026-03-07)

This release adds essential content management capabilities and optimizations requested by users.

### Card Editing

**Backend:**
- New endpoint: `POST /api/flashcards/cards/update/`
- Request payload:
  ```json
  {
    "card_id": 123,
    "question": "Updated question text",
    "answer": "Updated answer text"
  }
  ```
- Validation: Same bounds as card creation (question: 1-2,000 chars, answer: 1-4,000 chars)
- Ownership is verified via `deck__user` join
- Returns updated card data on success

**Frontend (FlashcardDeck.jsx):**
- Each card now has an "Edit" button
- Inline editing mode with textarea fields for question/answer
- Save/Cancel buttons during edit
- Cached explanations are cleared when a card is edited

### Individual Card Deletion

**Backend:**
- New endpoint: `DELETE /api/flashcards/cards/<card_id>/delete/` (also accepts POST for compatibility)
- Ownership is verified before deletion
- Returns deleted card's deck_id for reference

**Frontend (FlashcardDeck.jsx):**
- Each card now has a "Delete" button
- Confirmation dialog before deletion
- Card is removed from UI immediately on success
- Deletion state prevents duplicate requests

### Deck List Pagination

**Backend:**
- `GET /api/flashcards/decks/` now supports pagination query params:
  - `?page=1` (default: 1)
  - `?page_size=20` (default: 20, max: 100)
- Response includes pagination metadata:
  ```json
  {
    "decks": [...],
    "pagination": {
      "current_page": 1,
      "total_pages": 5,
      "total_count": 87,
      "page_size": 20,
      "has_next": true,
      "has_previous": false
    }
  }
  ```
- Decks are ordered by `created_at` (descending)

**Frontend:**
- Backward compatible: if no pagination params are provided, defaults apply
- Frontend can be updated to add pagination UI controls as needed

### Explanation Caching

**Backend:**
- Added `explanation` field to `Flashcard` model (TextField, blank=True)
- Migration: `backend/apps/flashcards/migrations/0003_add_explanation_cache.py`
- Updated `POST /api/flashcards/explain/` to accept optional `card_id`:
  ```json
  {
    "card_id": 123  // Option 1: Explain and cache for a specific card
  }
  ```
  or
  ```json
  {
    "question": "...",  // Option 2: Ad-hoc explanation (no caching)
    "answer": "..."
  }
  ```
- When `card_id` is provided:
  - Checks if explanation already exists → returns cached value immediately
  - Otherwise fetches from AI and caches in database
- When only question/answer provided: no caching (for flexibility)

**Frontend (FlashcardDeck.jsx):**
- Updated explain call to pass `card_id` for caching
- In-memory cache still prevents duplicate API calls during same session
- Cached explanations persist across page reloads

### Benefits

- **Editing**: Users can fix typos, improve clarity, or update outdated information without recreating decks
- **Deletion**: Remove low-quality or duplicate cards without deleting entire deck
- **Pagination**: Improved performance for users with large deck collections
- **Explanation Caching**: Reduces AI API costs and improves response time for repeated explanations
