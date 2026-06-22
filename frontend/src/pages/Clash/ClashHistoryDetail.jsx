import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../../components/Navbar";
import "./Clash.css";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL;

const MEDAL_EMOJI = { 1: "🥇", 2: "🥈", 3: "🥉" };
const LETTERS = ["A", "B", "C", "D", "E"];

function PlayerAvatar({ entry, className = "" }) {
  const [imgFailed, setImgFailed] = useState(false);
  const name = entry.display_name || entry.username;
  if (entry.profile_image && !imgFailed) {
    return (
      <img
        src={entry.profile_image}
        alt={name}
        className={className}
        style={{ objectFit: "cover", borderRadius: "50%" }}
        onError={() => setImgFailed(true)}
      />
    );
  }
  return <div className={className}>{name[0].toUpperCase()}</div>;
}

function medalClass(rank) {
  if (rank === 1) return "gold";
  if (rank === 2) return "silver";
  if (rank === 3) return "bronze";
  return "";
}

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function ClashHistoryDetail() {
  const { code } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem("auth_token");
  const userRaw = localStorage.getItem("user");
  const currentUser = userRaw ? JSON.parse(userRaw) : null;

  const [room, setRoom] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showReview, setShowReview] = useState(false);

  useEffect(() => {
    if (!token) { navigate("/auth/login"); return; }
    fetch(`${DJANGO_API_URL}/clash/my/${code}/`, {
      headers: { Authorization: `Token ${token}` },
    })
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(data => { setRoom(data); setLoading(false); })
      .catch(() => { setError("Failed to load clash details."); setLoading(false); });
  }, []); // eslint-disable-line

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="clash-results-page clash-center-screen">
          <div className="clash-spinner" />
          <p>Loading…</p>
        </div>
      </>
    );
  }

  if (error || !room) {
    return (
      <>
        <Navbar />
        <div className="clash-results-page">
          <p className="clash-error">{error || "Room not found."}</p>
          <button className="clash-btn-primary" onClick={() => navigate("/clash/history")}>
            Back to History
          </button>
        </div>
      </>
    );
  }

  // Build answer lookup: q_idx → {correct, points}
  const answerMap = {};
  (room.my_answers || []).forEach(a => { answerMap[a.q_idx] = a; });

  const myEntry = room.participants.find(p => p.username === currentUser?.username);
  const top3 = room.participants.slice(0, 3);
  const podiumOrder = [top3[1] ?? null, top3[0] ?? null, top3[2] ?? null];

  return (
    <>
    <Navbar />
    <div className="clash-results-page">
      {/* ── Header ── */}
      <button
        className="clash-history-back-btn"
        onClick={() => navigate("/clash/history")}
      >
        ← History
      </button>
      <p className="clash-kicker">Clash · {code}</p>
      <h1 className="clash-page-title">{room.subject}</h1>
      <p className="clash-page-sub">
        {room.difficulty.charAt(0).toUpperCase() + room.difficulty.slice(1)}
        {" · "}{room.num_questions} questions
        {" · "}{room.time_per_question}s per question
        {" · "}{fmt(room.finished_at)}
      </p>

      {/* ── My result ── */}
      {myEntry && (
        <div className={`clash-my-result-card ${myEntry.rank <= 3 ? "top" : ""}`}>
          <div className="clash-my-result-rank">
            {MEDAL_EMOJI[myEntry.rank] ?? `#${myEntry.rank}`}
          </div>
          <div>
            <p className="clash-my-result-label">
              You finished #{myEntry.rank}
            </p>
            <p className="clash-my-result-score">
              {myEntry.score.toLocaleString()} points · {myEntry.correct}/{room.num_questions} correct
            </p>
          </div>
        </div>
      )}

      {/* ── Podium ── */}
      {top3.length > 0 && (
        <div className="clash-podium">
          {podiumOrder.map((entry, i) => {
            if (!entry) return <div key={i} />;
            const cls = medalClass(entry.rank);
            return (
              <div key={entry.username} className="clash-podium-slot">
                <div className="clash-podium-info">
                  <PlayerAvatar entry={entry} className={`clash-podium-avatar ${cls}`} />
                  <div className="clash-podium-name">{entry.display_name || entry.username}</div>
                  <div className="clash-podium-pts">{entry.score} pts</div>
                </div>
                <div className={`clash-podium-block ${cls}`}>{entry.rank}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Leaderboard ── */}
      <div className="clash-rankings-card">
        <h3>Leaderboard</h3>
        {room.participants.map(entry => {
          const isMe = entry.username === currentUser?.username;
          return (
            <div key={entry.username} className={`clash-ranking-row ${isMe ? "is-me" : ""}`}>
              <div className={`clash-ranking-num ${entry.rank <= 3 ? "top" : ""}`}>
                {MEDAL_EMOJI[entry.rank] ?? `#${entry.rank}`}
              </div>
              <PlayerAvatar entry={entry} className="clash-ranking-avatar" />
              <div className="clash-ranking-info">
                <div className="clash-ranking-name">
                  {entry.display_name || entry.username}
                  {isMe && <span className="clash-you-inline">you</span>}
                  {entry.is_host && <span className="clash-host-inline">host</span>}
                </div>
                <div className="clash-ranking-detail">
                  {entry.score.toLocaleString()} pts · {entry.correct}/{room.num_questions} correct
                </div>
              </div>
              <div className="clash-ranking-score">{entry.score}</div>
            </div>
          );
        })}
      </div>

      {/* ── Answer review toggle ── */}
      {room.questions?.length > 0 && (
        <button
          className="clash-btn-secondary"
          style={{ marginBottom: "8px" }}
          onClick={() => setShowReview(v => !v)}
        >
          {showReview ? "Hide Answer Review" : "Review Answers"}
        </button>
      )}

      {showReview && room.questions?.length > 0 && (
        <div className="clash-review-section">
          <h3 className="clash-review-title">Answer Review</h3>
          <div className="clash-review-list">
            {room.questions.map((q, idx) => {
              const myRecord = answerMap[idx];
              const answered = myRecord !== undefined;
              const correct  = myRecord?.correct ?? false;
              const pts      = myRecord?.points ?? 0;
              const correctLetter = (q.answer || "").trim().toUpperCase();

              return (
                <div
                  key={idx}
                  className={`clash-review-item ${answered ? (correct ? "review-correct" : "review-incorrect") : "review-unanswered"}`}
                >
                  <div className="clash-review-q-header">
                    <span className="clash-review-q-num">Q{idx + 1}</span>
                    <span className={`clash-review-verdict ${answered ? (correct ? "verdict-correct" : "verdict-wrong") : "verdict-skipped"}`}>
                      {!answered ? "Not answered" : correct ? `Correct · +${pts} pts` : "Incorrect"}
                    </span>
                  </div>
                  <p className="clash-review-q-text">{q.question}</p>
                  <div className="clash-review-options">
                    {(q.options || []).map((opt, oi) => {
                      const letter = LETTERS[oi];
                      const isCorrect = letter === correctLetter;
                      return (
                        <div
                          key={oi}
                          className={`clash-review-option ${isCorrect ? "review-option-correct" : ""}`}
                        >
                          <span className="clash-review-option-letter">{letter}</span>
                          {opt}
                          {isCorrect && <span className="clash-review-correct-badge">✓ correct</span>}
                        </div>
                      );
                    })}
                  </div>
                  {q.explanation && (
                    <p className="clash-review-explanation">
                      <strong>Explanation: </strong>{q.explanation}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="clash-results-actions">
        <button className="clash-btn-secondary" onClick={() => navigate("/clash/history")}>
          Back to History
        </button>
        <button className="clash-btn-primary" onClick={() => navigate("/clash")}>
          New Clash
        </button>
      </div>
    </div>
    </>
  );
}
