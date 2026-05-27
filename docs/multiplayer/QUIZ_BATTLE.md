# Clash — Real-Time Multiplayer Quiz

> Live, synchronised multiplayer quiz battles. One host, up to 20 players,
> one room code. Built on Django Channels + WebSockets.

---

## What It Does

A host creates a room and chooses a topic (or pastes/uploads study material).
Friends join using a 6-character room code. When the host starts, every
participant sees the same question at the same time with a shared timer.
Answers are locked on submit. After each question the correct answer and
explanation are revealed, and a live leaderboard updates. At the end, a podium
celebrates the top 3 and every participant is ranked.

**Flow:**

```
Host                                   Players
─────────────────────────────────────────────────────────
Create room (topic + settings)
Questions generated via FastAPI
Room code displayed + share link
Share code ───────────────────────→ Enter code → Join lobby
See players joining live             See other players
Press "Start Clash" ─────────────→ All see 3-2-1 countdown
                                     See Question 1 + timer
Submit answer (locked in)            Submit answer (locked in)
Timer expires (or all answered)
← Correct answer + explanation to all →
← Live leaderboard snapshot →
Next question auto-advances
… (repeats for all questions)
← Final podium + full leaderboard →
```

---

## Architecture

```
React Clients
    │
    ├─ REST  (create / join)
    │       ↓
    │   Django REST views  (backend/apps/clash/views.py)
    │       ↓
    │   PostgreSQL  (ClashRoom, ClashParticipant)
    │
    └─ WebSocket  (live game)
            ↓
        ClashConsumer  (backend/apps/clash/consumers.py)
            ↓
        Redis Channel Layer  (one group per room: "clash_{room_code}")
            ↓
        Django cache  (live game state, TTL 2h)
```

The server is the single source of truth. No client can advance questions,
extend timers, or modify scores.

---

## Data Models

```python
# backend/apps/clash/models.py

class ClashRoom(models.Model):
    room_code        # CharField(6), unique, auto-generated (uppercase alphanumeric)
    host             # ForeignKey(User)
    subject          # CharField(200)
    difficulty       # CharField — "easy" / "medium" / "hard"
    questions        # JSONField — MCQ list from FastAPI
    num_questions    # PositiveIntegerField
    time_per_question # PositiveIntegerField (seconds, default 20)
    status           # "waiting" | "active" | "finished"
    created_at, started_at, finished_at


class ClashParticipant(models.Model):
    room         # ForeignKey(ClashRoom, related_name='participants')
    user         # ForeignKey(User)
    display_name # CharField(50)
    score        # IntegerField (accumulated)
    answers      # JSONField — [{q_idx, answer, correct, points, ms_taken}]
    is_host      # BooleanField
    rank         # IntegerField (null until game finishes)
    joined_at    # DateTimeField

    class Meta:
        unique_together = ('room', 'user')
        ordering = ['-score', 'joined_at']
```

---

## REST Endpoints

| Method | URL | Purpose |
|---|---|---|
| `POST` | `/api/clash/create/` | Create room, generate questions via FastAPI. Body: `{subject, difficulty, num_questions, time_per_question, study_text?}`. Returns `{room_code, …}` |
| `POST` | `/api/clash/join/` | Join a waiting room. Body: `{room_code}`. Returns room info + participant list |
| `GET`  | `/api/clash/{code}/` | Room detail — used by lobby on load |
| `GET`  | `/api/clash/{code}/results/` | Final leaderboard after game ends |

If `study_text` (≥ 50 chars) is provided, questions are generated from that material.
Otherwise the subject/difficulty are used as the generation prompt.

---

## WebSocket URL

```
ws://<host>/ws/clash/<room_code>/?token=<DRF auth token>
```

Token is validated in `connect()` before the connection is accepted.
Unauthenticated connections are rejected with close code `4001`.

---

## WebSocket Events

### Client → Server

| `type` | Payload | Who |
|---|---|---|
| `start_game` | `{}` | Host only — triggers countdown + game loop |
| `submit_answer` | `{question_index, answer, elapsed_ms}` | Any player |

### Server → All in Room (group_send)

| `type` | Key fields | When |
|---|---|---|
| `clash.player_joined` | `participants[]`, `count` | Someone connects or disconnects |
| `clash.game_starting` | `countdown` (default 3) | Host started the game |
| `clash.new_question` | `index`, `total`, `question`, `options[]`, `time_limit`, `server_time` | Each new question |
| `clash.question_ended` | `index`, `correct_answer`, `explanation`, `top3[]`, `your_scores{}` | Timer expired or all answered |
| `clash.game_finished` | `rankings[]`, `room_code` | All questions done |

### Server → Sender Only (direct send_json)

| `type` | Key fields | When |
|---|---|---|
| `answer_confirmed` | `correct`, `points_earned`, `total_score`, `correct_answer` | After submit_answer |
| `game_catchup` | `index`, `total`, `question`, `options[]`, `time_limit`, `time_remaining`, `scores{}` | Player connects mid-game |
| `error` | `message` | Invalid action (e.g. non-host trying to start) |

**Dot-notation note:** Django Channels maps the `type` field to a method using
`dots → underscores` — so `clash.new_question` dispatches to `clash_new_question()`.
The frontend must match against the dot-notation string (e.g. `case "clash.new_question"`).

---

## Server-Side State Machine

```
WAITING
  │  host sends start_game
  ↓
  Mark room ACTIVE, init Redis state, broadcast clash.game_starting
  asyncio.sleep(3)  — countdown
  ↓
ACTIVE — question loop (asyncio task, keyed by room_code):
  │  broadcast clash.new_question
  │  poll every 0.5s → break early if all answered
  │  timer expires (time_per_question + 1s grace)
  │  broadcast clash.question_ended
  │  asyncio.sleep(3)  — answer reveal pause
  │  … next question
  │
  │  last question done
  ↓
FINISHED
  persist scores + ranks to ClashParticipant
  broadcast clash.game_finished
```

The game loop runs as a persistent `asyncio.Task` stored in
`ClashConsumer._game_tasks[room_code]`. The task survives if the host
disconnects and reconnects; it is only cleaned up in the `finally` block
when the game naturally finishes.

---

## Scoring

```python
BASE_POINTS      = 1000
SPEED_BONUS_MAX  = 500
time_ratio       = max(0.0, 1 - elapsed_seconds / time_per_question)
points           = BASE_POINTS + int(SPEED_BONUS_MAX * time_ratio)  # if correct
```

- Correct answer: **1000 + up to 500 speed bonus = max 1500 pts per question**
- Wrong or no answer: **0 pts**
- Scores accumulate across all questions

---

## Consumer Resilience

**`_safe_send(event)`** — guards against sending to a closed WebSocket:

```python
async def _safe_send(self, event):
    if not self.connected:
        return
    try:
        await self.send_json(event)
    except Exception:
        pass
```

`self.connected` is set to `True` after `accept()` and `False` at the top of
`disconnect()` — ensuring broadcasted group events never cause a crash when
a player has already disconnected.

**Participant count is re-fetched per question** inside the game loop so that
a player disconnecting mid-game doesn't stall the "all answered" check for
remaining players.

---

## Cache Keys (Django cache / Redis, TTL 2h)

| Key | Value |
|---|---|
| `clash_state_{room_code}` | `{status, current_question, answered{}, scores{}, question_start_time, ended_question}` |
| `clash_presence_{room_code}` | `{user_id: username}` — online player map |

---

## Frontend Pages

| Route | Component | Notes |
|---|---|---|
| `/clash` | `ClashCreate` | Host/Join tab toggle. `?join=CODE` auto-fills the join tab |
| `/clash/lobby/:code` | `ClashLobby` | Live participant list via WebSocket. Host sees Start button |
| `/clash/play/:code` | `ClashPlay` | 2-column desktop layout (question + standings sidebar) |
| `/clash/results/:code` | `ClashResults` | 2-column desktop layout (podium on left, leaderboard on right) |

All Clash routes require authentication.

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Host disconnects mid-game | Game loop persists (`_game_tasks` class dict). Loop continues for remaining players. |
| Player disconnects mid-game | `self.connected = False`, lobby re-broadcast. Participant count refreshed per question so others aren't stalled. |
| All players answer before timer | Server advances early — breaks the polling loop immediately. |
| Player joins mid-game | Receives `game_catchup` event with current question and remaining time. |
| Room code collision | `_generate_room_code()` is retried until unique (6-char uppercase+digits = ~2 billion combinations). |
| LLM generation fails | Room creation returns an error before any WebSocket connection. No zombie rooms. |

---

## Related Documents

- `../architecture-design/ARCHITECTURE.md` — overall system architecture and WebSocket section
- `../deployment-guides/DEPLOYMENT_CHECKLIST.md` — REDIS_URL requirement and Clash smoke tests
- `../frontend/ROUTES_AND_PAGES.md` — full frontend route table
- `../features/QUIZ.md` — solo quiz engine this feature builds on
