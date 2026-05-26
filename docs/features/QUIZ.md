# Quiz Feature

## Frontend Pages

| File | Route | Access |
|---|---|---|
| `src/pages/Quiz/QuizHistory.jsx` | `/quiz` | Authenticated only |
| `src/pages/Quiz/CreateQuiz.jsx` | `/quiz/create` | Public (guest one-quiz limit) |
| `src/pages/Quiz/Quiz.jsx` | `/quiz/play` | Public |
| `src/pages/Quiz/QuizResults.jsx` | `/quiz/results` | Public |

### `/quiz` — Quiz History Page

The dedicated quiz history page. Replaces the former inline "Past Quizzes" tab that lived inside `/dashboard`.

- Requires authentication — unauthenticated visitors are redirected to `/auth/login`.
- Uses the shared `Sidebar` component (`activeId="history"`) with the same navigation items as Dashboard and Profile.
- Header row: "Past Quizzes" heading left-aligned, "Take a New Quiz" button right-aligned at the same level.
- Sidebar nav behaviour: clicking "Past Quizzes" stays on page; other items navigate to `/dashboard?tab=<id>` or `/profile`.

### Guest Access & One-Quiz Limit

Unauthenticated users may create and take exactly one quiz.

- The Navbar "Quiz" link routes guests to `/quiz/create` and authenticated users to `/quiz`.
- When a guest successfully generates a quiz (navigates to `/quiz/play`), the flag `lamla_guest_quiz_used = "true"` is stored in `localStorage`.
- On subsequent visits to `/quiz/create`, the component detects the flag and shows a **blocking modal** (not a silent redirect):
  - Heading: "You've used your free quiz"
  - Body: invitation to sign up for unlimited access
  - Primary CTA: "Sign Up — it's free" → `/auth/signup` (with `state.fromGuest = true`)
  - Secondary link: "Already have an account? Sign in" → `/auth/login`
- The Signup page reads `location.state?.fromGuest` and surfaces a contextual banner above the form.
- On any successful auth (login, signup, Google OAuth), `lamla_guest_quiz_used` is removed from `localStorage` so the user is no longer treated as a repeat guest.

## Django Endpoints

From `backend/apps/quiz/urls.py`:

- `POST /api/quiz/ajax-extract-text/` — extract text from uploaded file
- `POST /api/quiz/extract-youtube/` — extract transcript from YouTube URL
- `POST /api/quiz/generate/` — generate quiz via FastAPI (Create Quiz page)
- `POST /api/quiz/submit/` — evaluate and store quiz results
- `POST /api/quiz/download/` — download quiz as PDF/DOCX
- `GET /api/quiz/history/` — authenticated user's past sessions
- `GET /api/quiz/sessions/<id>/` — fetch stored questions for a past session (used by Try Again)
- `GET /api/quiz/weak-areas/` — bottom 5 topics by accuracy (min 3 questions attempted)
- `GET /api/quiz/due-topics/` — topics where `next_review <= now`, ordered most overdue first

From `backend/apps/chatbot/urls.py`:

- `POST /api/quiz/create-from-agent/` — chatbot-triggered quiz generation (see [Chatbot feature](CHATBOT.md))

## FastAPI Endpoint

- `POST /quiz/` (internal, called by Django async view)

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
2. Django's async view forwards a normalized payload to FastAPI `POST /quiz/`:
   - `subject`, `study_text`, `num_mcq`, `num_short`, `difficulty`
   - `source_type` — `"file"` | `"youtube"` | `"text"`
   - `source_title` — filename or video title (used in prompt context)
3. FastAPI normalizes text (Unicode cleanup, truncation to 16,000 chars), scales `max_tokens` dynamically based on question count (2,048–8,192), and calls the AI provider.
4. The prompt tells the LLM the source type so it can adjust tone (e.g., spoken-language transcript vs. academic document).
5. FastAPI validates the JSON response, normalizes questions, and returns `QuizResponse`.
6. Django adds metadata (`id`, `time_limit`, `source_filename`) and returns to the frontend.
7. Frontend navigates to `/quiz/play`.

## Submission Flow

1. Frontend submits `quiz_data` + `user_answers` to `/api/quiz/submit/`.
2. Django evaluates MCQ by letter comparison.
3. Short answers are LLM-evaluated via the FastAPI chatbot route (with fallback string matching).
4. Result payload returned and saved as `QuizSession` for authenticated users.

## Quiz Settings

| Setting | Range | Default |
|---|---|---|
| MCQ questions | 0–30 | 7 |
| Short answer questions | 0–10 | 3 |
| Quiz time | 1–120 min | 10 |
| Difficulty | easy / medium / hard / random | random |

## Agentic Quiz Creation (via Chatbot)

Quizzes can also be generated directly from the AI Tutor chat without navigating to `/quiz/create`.

1. User expresses quiz intent in chat → agent calls `request_quiz_form(topic)`.
2. An inline quiz-param card appears in the chat (topic, num_questions, time_limit).
3. User submits → `POST /api/quiz/create-from-agent/` → FastAPI auto-determines difficulty from user stats → questions generated.
4. A **Start Quiz** card replaces the form; clicking it navigates to `/quiz/play`.

The generated quiz card is persisted as a `__QUIZ__:` chat message so it reappears when the user returns to that conversation. Difficulty is picked automatically:
- Topic accuracy < 60% → hard; 60–79% → medium; ≥ 80% → hard (challenge mode)
- No topic history: overall avg ≥ 80% → hard; ≥ 60% → medium; else → easy

See [AGENT_IMPLEMENTATION.md § 17](../architecture-design/AGENT_IMPLEMENTATION.md) for the full two-phase flow.

## Weak Area Detection

After every quiz submission, `submit_quiz_api_async` updates `TopicPerformance` for the quiz subject using atomic `F()` expressions (race-condition safe). Accuracy is recomputed after each update.

`GET /api/quiz/weak-areas/` returns the 5 lowest-accuracy topics for the user, filtered to topics with at least 3 questions attempted (noise filter). Used by the dashboard weak areas card.

The chatbot receives **all** `TopicPerformance` rows (no minimum threshold) plus the last 5 `QuizSession` records so the AI can discuss results the user just took.

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
- If the AI returns malformed JSON, FastAPI makes one repair attempt before returning 502.
- If FastAPI returns a non-200 response, Django returns 503 to the frontend.
- YouTube extraction fails gracefully with a user-facing message if captions are disabled or the URL is invalid.
- Frontend should keep the user on the page and allow retry on any generation error.
