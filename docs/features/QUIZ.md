# Quiz Feature

## Frontend Pages

| File | Route | Access |
|---|---|---|
| `src/pages/Quiz/QuizHistory.jsx` | `/quiz` | Authenticated only |
| `src/pages/Quiz/CreateQuiz.jsx` | `/quiz/create` | Authenticated only |
| `src/pages/Quiz/Quiz.jsx` | `/quiz/play` | Authenticated only |
| `src/pages/Quiz/QuizResults.jsx` | `/quiz/results` | Authenticated only |

All quiz routes are wrapped in `ProtectedRoute` and every quiz endpoint requires `IsAuthenticated`. The former guest one-quiz flow is no longer active: `lamla_guest_quiz_used` is only cleared on successful auth, and nothing sets it any more.

### `/quiz` — Quiz History Page

The dedicated quiz history page. Replaces the former inline "Past Quizzes" tab that lived inside `/dashboard`.

- Requires authentication — unauthenticated visitors are redirected to `/auth/login`.
- Uses the shared `Sidebar` component (`activeId="history"`) with the same navigation items as Dashboard and Profile.
- Header row: "Past Quizzes" heading left-aligned, "Take a New Quiz" button right-aligned at the same level.
- Sidebar nav behaviour: clicking "Past Quizzes" stays on page; other items navigate to `/dashboard?tab=<id>` or `/profile`.

## Django Endpoints

From `backend/apps/quiz/urls.py`:

- `POST /api/quiz/ajax-extract-text/` — extract text from uploaded file
- `POST /api/quiz/extract-youtube/` — extract transcript from YouTube URL
- `POST /api/quiz/generate/` — generate quiz (Django-native; no upstream service)
- `POST /api/quiz/submit/` — evaluate and store quiz results
- `POST /api/quiz/download/` — download quiz as PDF/DOCX
- `GET /api/quiz/history/` — authenticated user's past sessions
- `GET /api/quiz/sessions/<id>/` — fetch stored questions for a past session (used by Try Again)
- `GET /api/quiz/weak-areas/` — bottom 5 topics by accuracy (min 3 questions attempted)
- `GET /api/quiz/due-topics/` — topics where `next_review <= now`, ordered most overdue first

From `backend/apps/tutor/urls.py`:

- `POST /api/tutor/quiz/from-agent/` — tutor-triggered quiz generation (see [AI Tutor feature](TUTOR.md))

## Module Layout

| Path | Responsibility |
|---|---|
| `apps/quiz/views.py` | DRF `APIView`s — authentication, request parsing, HTTP status codes only |
| `apps/quiz/serializers.py` | Request payload validation |
| `apps/quiz/services.py` | Async business logic: generation, scoring, persistence, history |
| `apps/quiz/prompts.py` | Quiz generation and repair prompts |
| `apps/quiz/utils/` | Pure helpers: text extraction, scoring, SM-2 scheduling, latency, downloads, YouTube |

Quiz AI calls go through `apps.core.ai_engine.ai_client` (Django in-process), not HTTP.

## Data Model

### `QuizSession`
Primary session record. Fields: subject, scores, duration, question payload, user answers, `exam_mode` (bool), `time_limit_minutes` (nullable int).

### `TopicPerformance`
Per-user accuracy map built automatically after every quiz submission. Fields: `user`, `topic`, `subject`, `total_questions`, `correct_answers`, `accuracy` (recomputed on update), `last_attempted`. Unique on `(user, topic)`. Indexed on `(user, accuracy)` for fast weak-area queries.

### `QuizTopicSchedule`
SM-2 spaced-repetition schedule per user per topic — mirrors the flashcard `Flashcard` model. Fields: `user`, `topic`, `subject`, `repetition`, `interval`, `ease_factor`, `next_review`, `last_review`. Unique on `(user, topic)`. Uses the same `update_sm2()` function from `apps.flashcards.scheduling`.

Score → SM-2 quality mapping applied at submission:
| Score | Quality |
|---|---|
| ≥ 90% | 5 |
| ≥ 75% | 4 |
| ≥ 60% | 3 |
| ≥ 40% | 2 |
| ≥ 20% | 1 |
| < 20%  | 0 |

## Input Sources

The quiz creator (`/quiz/create`) supports three input tabs:

| Tab | How it works |
|---|---|
| **File** | Upload PDF, DOCX, PPTX, or TXT. Django extracts text via `ajax-extract-text`, populates the text field. |
| **YouTube** | Paste any YouTube URL. Django calls `extract-youtube/`, which fetches the video transcript via `youtube-transcript-api` and the title via YouTube oEmbed. Requires captions to be enabled on the video. |
| **Text** | Paste or type study material directly. |

All three paths converge at the same `generate/` endpoint once `extractedText` is populated.

## Generation Flow

1. User picks an input tab and loads content (file, YouTube URL, or direct text).
2. `POST /api/quiz/generate/` validates the request with `QuizGenerateRequestSerializer`.
3. `services.generate_quiz()` normalizes the study text (Unicode cleanup, truncation to 16,000 chars), resolves `difficulty="random"` to a concrete level, and builds the prompt.
4. The prompt tells the LLM the source type so it can adjust tone (e.g., spoken-language transcript vs. academic document).
5. `ai_client.generate_text()` calls the configured provider with a token budget scaled to the question count (4,096–8,192).
6. The response is parsed and validated; malformed JSON triggers one repair attempt.
7. `QuizGenerateView` adds metadata (`id`, `time_limit`, `created_at`, `source_filename`) and returns to the frontend.
8. Frontend navigates to `/quiz/play`.

## Submission Flow

1. Frontend submits `quiz_data` + `user_answers` to `/api/quiz/submit/`.
2. `services.submit_quiz()` evaluates MCQ by letter comparison.
3. Short answers are LLM-evaluated by `services.evaluate_short_answer()` with exact-match fallback.
4. The session is persisted as `QuizSession`, caches are busted, and `TopicPerformance`/`QuizTopicSchedule` are updated.
5. Result payload is returned to the frontend.

## Quiz Settings

| Setting | Range | Default |
|---|---|---|
| MCQ questions | 0–30 | 7 |
| Short answer questions | 0–10 | 3 |
| Quiz time | 1–120 min | 10 |
| Difficulty | easy / medium / hard / random | random |

## Agentic Quiz Creation (via AI Tutor)

Quizzes can also be generated directly from the AI Tutor chat without navigating to `/quiz/create`.

1. User expresses quiz intent in chat → agent calls `request_quiz_form(topic)`.
2. An inline quiz-param card appears in the chat (topic, num_questions, time_limit).
3. User submits → `POST /api/tutor/quiz/from-agent/` → difficulty is auto-determined from user stats → questions generated.
4. A **Start Quiz** card replaces the form; clicking it navigates to `/quiz/play`.

The generated quiz card is persisted as a `__QUIZ__:` tutor message so it reappears when the user returns to that conversation. Difficulty is picked automatically:
- Topic accuracy < 60% → hard; 60–79% → medium; ≥ 80% → hard (challenge mode)
- No topic history: overall avg ≥ 80% → hard; ≥ 60% → medium; else → easy

See [AGENT_IMPLEMENTATION.md § 17](../architecture-design/AGENT_IMPLEMENTATION.md) for the full two-phase flow.

## Weak Area Detection

After every quiz submission, `services.submit_quiz()` updates `TopicPerformance` for the quiz subject using atomic `F()` expressions (race-condition safe). Accuracy is recomputed after each update.

`GET /api/quiz/weak-areas/` returns the 5 lowest-accuracy topics for the user, filtered to topics with at least 3 questions attempted (noise filter). Used by the dashboard weak areas card.

The tutor receives **all** `TopicPerformance` rows (no minimum threshold) plus the last 5 `QuizSession` records so the AI can discuss results the user just took.

### Historical Backfill

Migration `0003_backfill_topic_performance` automatically populates `TopicPerformance` and `QuizTopicSchedule` from all existing `QuizSession` rows on first deploy. Safe to re-run — `TopicPerformance` rows are replaced with the full aggregate and `QuizTopicSchedule` rows are only initialised if they don't exist yet.

A management command is also available for manual re-sync after a DB restore:
```
python manage.py backfill_topic_performance
python manage.py backfill_topic_performance --dry-run
```

## Exam Simulation Mode

`QuizSession` now carries `exam_mode` (bool, default `False`) and `time_limit_minutes`. Pass `exam_mode: true` in the submit payload to flag a session as an exam simulation. The quiz generation endpoint is unchanged — exam mode is a frontend UX constraint recorded at submission time.

`GET /api/quiz/history/` response includes `exam_mode` per session so the frontend can filter exam-only history.

## Reliability Notes

- Token budget scales with question count so large quizzes don't produce truncated JSON.
- If the AI returns malformed JSON, `services.generate_quiz()` makes one repair attempt before raising `QuizGenerationError` (HTTP 400).
- Provider failures raise `APIIntegrationError`; the view returns 503 to the frontend.
- YouTube extraction fails gracefully with a user-facing message if captions are disabled or the URL is invalid.
- Frontend should keep the user on the page and allow retry on any generation error.
