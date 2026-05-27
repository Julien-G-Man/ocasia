# Frontend Routes and Pages

Source of truth: `frontend/src/App.jsx`.

---

## Public

| Route | Component | Notes |
|---|---|---|
| `/` | Home | Landing page |
| `/auth/login` | Login | |
| `/auth/signup` | Signup | |
| `/auth/verify-email` | VerifyEmail | Handles `?uid=&token=` params from email link |
| `/auth/forgot-password` | ForgotPassword | Request password reset email |
| `/auth/reset-password` | ResetPassword | Confirm reset via `?uid=&token=` params |

### Legacy redirects
| From | To |
|---|--|
| `/auth` | `/auth/login` |
| `/login` | `/auth/login` |
| `/signup` | `/auth/signup` |
| `/verify-email` | `/auth/verify-email` |

---

## Authenticated App Pages

| Route | Component | Notes |
|---|---|---|
| `/dashboard` | Dashboard | User stats, quiz history, weak areas |
| `/profile` | Profile | Edit account info, avatar, password |

`Dashboard` and `Profile` are rendered inside the standard authenticated `AppShell`.

---

## Admin (staff/superuser only)

| Route | Component |
|---|---|
| `/admin-dashboard` | Redirect to `/admin-dashboard/overview` |
| `/admin-dashboard/overview` | AdminOverview |
| `/admin-dashboard/users` | AdminUsers |
| `/admin-dashboard/content` | AdminContent |
| `/admin-dashboard/settings` | AdminSettings |
| `/admin-dashboard/profile` | Profile (inside AdminAppShell) |
| `/admin-dashboard/user/:id` | AdminUserDetails |
| `/admin-dashboard/activity` | AdminActivity |
| `/admin-dashboard/ratings` | AdminRatings |

Admin pages use `AdminAppShell`, which keeps the shared authenticated top navbar and an admin-styled sidebar.

---

## Quiz

| Route | Component | Access |
|---|---|---|
| `/quiz` | QuizHistory | Authenticated — redirects to `/auth/login` if not signed in |
| `/quiz/create` | CreateQuiz | Public; guests limited to one quiz via `lamla_guest_quiz_used` localStorage flag. Accepts `?subject=` to pre-fill subject (used by Dashboard weak-areas "Practice" button) |
| `/quiz/play` | Quiz | Authenticated |
| `/quiz/results` | QuizResults | Authenticated |

---

## Flashcards

| Route | Component |
|---|---|
| `/flashcards` | FlashcardDecks |
| `/flashcards/create` | FlashcardCreate |
| `/flashcards/deck/:id` | FlashcardDeck |
| `/flashcards/study/:id` | FlashcardStudy |

Alias: `/flashcard` → redirect `/flashcards`

---

## Materials

| Route | Component | Notes |
|---|---|---|
| `/materials` | — | Redirects to `/materials/community` |
| `/materials/community` | Materials | Community-uploaded materials library |
| `/materials/mine` | MyMaterials | User's own uploads |
| `/materials/upload` | MaterialUpload | Upload form |

---

## AI Tutor

| Route | Component |
|---|---|
| `/ai-tutor` | Chatbot |

Aliases: `/ai`, `/chat`, `/chatbot` → all redirect to `/ai-tutor`

---

## Donations

| Route | Component | Notes |
|---|---|---|
| `/donate` | Donate | Full-height split layout — open to all |
| `/donate/thank-you` | DonateThankyou | Verifies Paystack payment on load via `?reference=` |

---

## Clash (Multiplayer)

| Route | Component | Notes |
|---|---|---|
| `/clash` | ClashCreate | Toggle between **Host a Room** and **Join a Room**. `?join=CODE` auto-switches to the join tab and pre-fills the room code (used by lobby share links). |
| `/clash/lobby/:code` | ClashLobby | Waiting room. Participant list updates live via WebSocket. Host sees Start button; others see waiting status. |
| `/clash/play/:code` | ClashPlay | Live quiz — 2-column layout (question + options on left, standings sidebar on right). Timer bar, answer feedback, and explanation shown after each question. |
| `/clash/results/:code` | ClashResults | Final results — 2-column layout (podium + personal result on left, full leaderboard on right). |

All Clash routes require authentication.

---

## Fallback

| Route | Component |
|---|---|
| `*` | NotFound |

---

## Global Warmup Behaviour

`App.jsx` pings the Django warmup endpoint and FastAPI health check on mount and every 10 minutes to prevent cold starts on Render's free tier.

---

## Unrouted Pages (exist, not wired)

| Page | File | Status |
|---|---|---|
| About | `pages/About/About.jsx` | Built, not added to App.jsx |
| LeaderBoard | `pages/LeaderBoard/` | WIP, not started |
