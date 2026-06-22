# Tier 5 — Real-Time Multiplayer

> **Status: ✅ SHIPPED** — Clash is live.

---

## What Was Built

**Clash** is the live multiplayer quiz battle feature. One host creates a room,
up to 20 players join via a 6-character code, and everyone competes on the same
questions in real time. Faster correct answers earn more points (up to 1500 per
question). A podium and full leaderboard are shown at the end.

Full technical specification: `../multiplayer/QUIZ_BATTLE.md`

---

## Infrastructure

| Layer | Technology | Status |
|---|---|---|
| WebSocket connections | Django Channels (ASGI) | ✅ Live |
| Channel pub/sub | Redis channel layer (Upstash Redis) | ✅ Live |
| Live game state | Django cache (Redis, TTL 2h per room) | ✅ Live |
| Persistence | PostgreSQL (`ClashRoom`, `ClashParticipant`) | ✅ Live |
| AI question generation | FastAPI → Claude (same pipeline as solo quiz) | ✅ Live |

---

## What Shipped

- Room creation (topic, difficulty, question count, time-per-question, optional study material)
- Live lobby with real-time participant list
- Server-driven game loop — questions broadcast in sync, scoring server-side
- Speed-based scoring: 1000 base + up to 500 speed bonus = 1500 pts max per question
- Answer review on results page — correct answer + explanation per question
- Clash history for users (`/clash/history`, `/clash/history/:code`)
- Social share link with Open Graph preview (`/clash/share/:code/` → Django OG page)
- Admin dashboard integration — clash list, detail page, stat cards, activity feed, usage chart

---

## What Remains

- **Dashboard clash stats for users** — `DashboardStatsView` does not yet include the
  user's clash count, average rank, or win count. Only the admin overview shows clash stats.
- **`my_clashes` / `my_clash_detail` caching** — these endpoints hit the DB on every
  request; not yet covered by the Redis view cache.
- **Clash badges** — no badge/XP system exists yet (Tier 1 prerequisite).

---

## Related Documents

- `../multiplayer/QUIZ_BATTLE.md` — full technical spec (models, WS events, scoring, edge cases)
- `../architecture-design/ARCHITECTURE.md` — WebSocket architecture section
- `../frontend/ROUTES_AND_PAGES.md` — Clash route table
- `../deployment-guides/DEPLOYMENT_CHECKLIST.md` — `REDIS_URL` requirement
