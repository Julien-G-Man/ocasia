# Tier 2 — Moderate LLM Cost, High Leverage

> These features use LLM calls deliberately: batched, cached, or one-time per resource.
> Each API call serves many users or is stored permanently after the first request.
> The cost per insight is low. The learning value per insight is high.

---

## Status

| Feature | Status |
|---|---|
| Socratic Tutor Mode | ✅ Shipped |
| Post-Quiz Mistake Analysis | ⏳ Not started |
| Smart Material Summarizer | ⏳ Not started |
| AI Mistake Patterns (Weekly Batch) | ⏳ Not started |

> **Note:** Agentic inline quiz creation (user says "quiz me on X" in the AI Tutor →
> quiz generated immediately) is also shipped, but lives in the tutor feature, not
> this tier. It uses a synchronous call to the quiz service rather than a Celery task —
> one LLM call per tutor-initiated quiz, no caching needed since each quiz is
> personalised to the user's current difficulty level.

---

## Cost Philosophy

Before building any feature here, establish one rule:
**every LLM response is cached permanently against a deterministic key.**

If 500 students take a quiz on the same Chemistry PDF, the material summary
is generated once and served 500 times. If a student submits the same quiz
answers twice, the analysis is fetched from cache.

The ResearchCache model already exists in the tutor app (`TutorResearchCache`). Extend this pattern.

---

## 1. Post-Quiz Mistake Analysis

### What It Does
After a student submits a quiz and sees their score, they receive a
personalised analysis of what went wrong and why — not just the correct answer,
but the misconception their wrong answer reveals.

Example output:
> "Question 3 (Le Chatelier's Principle): You chose B (increase in temperature
> always favours forward reaction). This is a common misconception. Temperature
> changes shift equilibrium in the direction that absorbs heat — which depends
> on whether the reaction is exothermic or endothermic. For this exothermic
> reaction, increased temperature actually favours the reverse reaction.
>
> Suggested review: Exothermic vs. endothermic equilibrium shifts."

This is different from just showing the correct answer. It names the
misconception, explains the underlying principle, and tells the student
exactly what to review.

### Why It Matters
Research consistently shows that corrective feedback that explains the *why*
behind an error is significantly more effective for learning than simply
marking an answer wrong. This is the difference between a quiz tool and
a tutor.

### LLM Cost Control
- **One call per quiz session**, not per question
- The entire set of wrong answers is bundled into a single prompt
- Response is cached against a hash of: (wrong_question_ids + wrong_answers)
- If a student retakes the same quiz with the same wrong answers, cache is hit
- If they got different questions wrong, a new analysis is generated

### Data Model

```python
class QuizMistakeAnalysis(models.Model):
    quiz_session = models.OneToOneField(
        QuizSession, on_delete=models.CASCADE, related_name="mistake_analysis"
    )
    analysis_json = models.JSONField()   # list of {question, misconception, tip}
    generated_at = models.DateTimeField(auto_now_add=True)
    cache_key = models.CharField(max_length=64, db_index=True)  # SHA256 hash
```

### Implementation Strategy

**Step 1 — Generate on submission**
After quiz score is computed and `QuizSession` saved, enqueue a Celery task:
`generate_mistake_analysis.delay(quiz_session_id)`

Return the score to the student immediately. Analysis arrives async.

**Step 2 — Prompt design**
The prompt receives only the wrong answers. Format:
```
You are an educational analysis engine. For each wrong answer below,
identify the specific misconception it reveals and suggest one targeted
review topic. Be concise. Return valid JSON only.

Questions and wrong answers:
[{question_text, correct_answer, student_answer, explanation}, ...]

Return: [{question_summary, misconception, review_suggestion}]
```

**Step 3 — Cache lookup**
Before calling the LLM, hash the wrong answer payload with SHA256.
Check `QuizMistakeAnalysis` for an existing row with that cache_key.
If found, link it to the new QuizSession. No API call needed.

**Step 4 — Frontend retrieval**
`GET /api/quiz/sessions/{id}/analysis/` returns the analysis if ready,
or a `status: "pending"` response if still generating.
Frontend polls every 3 seconds until ready (max 30 seconds).

**Step 5 — Feed into TopicPerformance**
The analysis response also returns the `review_suggestion` topics.
These are written into `TopicPerformance` to sharpen the weak area map.

---

## 2. Smart Material Summarizer

### What It Does
When a user uploads a PDF to the community library, the system
automatically generates:

1. A one-paragraph summary of the material
2. Five key concepts covered
3. Three likely exam questions based on the content
4. Subject tags (used for concept-based search)

This is displayed on the material detail page for every user who views
or downloads it — the cost is shared across the entire community.

### Why It Matters
Students browsing community materials currently see only a filename and
description. They cannot tell if a PDF is relevant to their topic without
downloading and reading it. The summary solves this instantly.

The exam questions generated from the material become a direct pipeline
into quiz generation: "Take a quiz on this material →" becomes a one-click
feature powered by questions already generated.

### LLM Cost Control
- **One call per uploaded material, ever**
- Result stored in a new `MaterialIntelligence` model
- Text extraction already exists (PyPDF2 + pdfplumber fallback)
- Processing uses the first 8,000 characters of extracted text
  (sufficient for summary and tagging without burning context on full documents)
- If extraction fails or text is too short (<200 chars), skip silently

### Data Model

```python
class MaterialIntelligence(models.Model):
    material = models.OneToOneField(
        Material, on_delete=models.CASCADE, related_name="intelligence"
    )
    summary = models.TextField()
    key_concepts = models.JSONField()          # ["Concept A", "Concept B", ...]
    suggested_questions = models.JSONField()   # ["Q1?", "Q2?", "Q3?"]
    subject_tags = models.JSONField()          # ["Cell Biology", "Mitosis", ...]
    generated_at = models.DateTimeField(auto_now_add=True)
```

### Implementation Strategy

**Step 1 — Trigger on upload**
After material is saved successfully, enqueue:
`generate_material_intelligence.delay(material_id)`
Upload endpoint returns immediately. Processing is async.

**Step 2 — Text extraction reuse**
The materials app already has PDF text extraction logic. Import and reuse it.
Truncate extracted text to 8,000 characters for this task.

**Step 3 — Single structured prompt**
```
Analyse the following educational text and return valid JSON with:
- summary: one paragraph
- key_concepts: list of 5 concepts
- suggested_questions: list of 3 exam-style questions
- subject_tags: list of 2-4 subject/topic tags

Text: {extracted_text[:8000]}
```

Request JSON output mode if the LLM provider supports it.

**Step 4 — Material list API update**
Include `intelligence` in the material list response (summary + tags only).
Full intelligence (with exam questions) on the material detail endpoint.

**Step 5 — Search upgrade**
Extend the materials search to also search across `subject_tags` and
key concepts in `MaterialIntelligence`. Students can now search
"Le Chatelier" and find materials that contain that concept even if the
filename says nothing about it.

**Step 6 — One-click quiz from material**
On the material detail page, a "Take a quiz on this →" button pre-fills
the quiz generation form with:
- Subject: from the material's subject field
- Study text: extracted text from the material (already done for the tutor)
- Suggested questions: the 3 pre-generated questions seeded as a starting point

---

## 3. Socratic Tutor Mode ✅ SHIPPED

### What It Does
A toggle in the AI tutor interface that shifts the AI from answer-giving
to guided discovery. Instead of:

> "Osmosis is the movement of water molecules across a semipermeable
> membrane from an area of low solute concentration to high."

The Socratic tutor responds:

> "Before I explain, tell me — what do you already know about how cells
> interact with water? Even a rough idea is fine. Let's build from there."

When the student responds, the tutor continues guiding:

> "Good. You mentioned water moving in and out of cells. What do you think
> drives that movement — what's the difference between the two sides of
> the membrane that causes this?"

The student arrives at the answer through their own reasoning.
Research shows this produces significantly better long-term retention
than passive reading.

### Why It Matters
Passive answer-giving is the cheapest thing an LLM can do.
It is also the least effective form of tutoring.
The Socratic method forces active recall and self-explanation —
two of the highest-impact learning techniques in cognitive science.

### LLM Cost Control
- **Prompt engineering only — zero architectural cost**
- No new models, no new endpoints, no extra API calls
- One short block appended to the system prompt when mode is active

### Shipped Implementation

**`tutor_mode` is a per-request field, not a DB column.**
Django forwards `tutor_mode: "direct" | "socratic"` in the tutor chat payload
on every request. No `TutorSession` migration, no `PATCH` endpoint.

**System prompt injection lives in `backend/apps/tutor/agent/prompts.py`:**
```python
def build_tutor_system_prompt(tutor_mode: str = "direct", user_stats: dict | None = None) -> str:
    sections = [_PLATFORM_FACTS, _FORMATTING, _TOOL_GUIDANCE, f"Today's date: {date.today().isoformat()}."]
    if user_stats:
        ...
    if tutor_mode == "socratic":
        sections.append(
            "SOCRATIC MODE: Guide with one question at a time, build on correct reasoning, "
            "and reveal the full answer after at least two guided exchanges unless the student asks directly."
        )
    return "\n\n".join(sections)
```

**Frontend toggle in `Chatbot.jsx`:**
```jsx
const [isSocratic, setIsSocratic] = useState(false);
// toggle button in the toolbar
<button className={`search-pill${isSocratic ? ' active' : ''}`}
        onClick={() => setIsSocratic(v => !v)}>
  Socratic
</button>
// included in every request
{ message, session_id, tutor_mode: isSocratic ? "socratic" : "direct" }
```

Mode resets to `"direct"` when the page refreshes. It is intentionally
not persisted — students toggle it per conversation, not per account.

---

## 4. AI Mistake Patterns (Weekly Batch)

### What It Does
Once a week, a background job processes each active user's last 7 days of
quiz performance. For each user with enough data (at least 3 quizzes taken),
one LLM call generates:

1. Their top recurring mistake pattern (e.g., "You consistently confuse
   correlation with causation across 4 different quizzes")
2. A targeted flashcard set addressing that pattern (3–5 cards)
3. One concrete study tip

The flashcard deck is automatically created in their account.
They receive an in-app notification and it appears in their weekly digest.

### Why It Matters
Individual quiz mistake analysis (Feature 1) looks at one quiz at a time.
This feature looks across a week of quizzes to find patterns the student
cannot see themselves. It is the difference between a diagnostic tool
and an intelligent tutor.

### LLM Cost Control
- **One call per active user per week, maximum**
- Only runs for users who took 3+ quizzes in the last 7 days
- Result cached — if the same pattern was identified last week
  (same wrong answers, same topics), skip the LLM call
- Batch job runs Sunday night, off-peak hours
- Failed calls are logged but do not retry — they wait until next week

### Implementation Strategy

**Step 1 — Celery beat task**
```python
"weekly-pattern-analysis": {
    "task": "apps.quiz.tasks.analyse_weekly_mistake_patterns",
    "schedule": crontab(hour=23, minute=0, day_of_week="saturday"),
}
```
Runs Saturday night so flashcard decks are ready Sunday morning.

**Step 2 — Data aggregation**
For each qualifying user, aggregate:
- All QuizSession rows from the last 7 days
- All wrong answers from the stored question JSON
- TopicPerformance scores for context

Build a compact summary (not raw text) to keep the prompt short:
```
User wrong answers this week, grouped by topic:
- Thermodynamics (6 wrong): [q1_summary, q2_summary, ...]
- Probability (3 wrong): [q1_summary, ...]
```

**Step 3 — Single structured prompt**
```
A student answered the following questions incorrectly this week.
Identify their single most significant recurring mistake pattern.
Then create 4 flashcards that directly address this pattern.

Return JSON: {
  "pattern_description": "...",
  "study_tip": "...",
  "flashcards": [{"question": "...", "answer": "...", "explanation": "..."}, ...]
}

Wrong answers by topic: {aggregated_summary}
```

**Step 4 — Auto-create flashcard deck**
Use the existing flashcard bulk-create logic to create a new deck:
- Name: "Week of {date} — Mistake Patterns"
- Cards: from LLM response
- Linked to user automatically

**Step 5 — Notification**
Add the new deck to the `new_badges` / notification pattern.
Next time user loads their dashboard, a notification appears:
"Your weekly mistake analysis is ready — 4 new flashcards created."
