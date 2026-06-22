import { useState, useEffect } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import Navbar from "../../components/Navbar";
import "./Clash.css";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL;

const MEDAL_EMOJI = { 1: "🥇", 2: "🥈", 3: "🥉" };
const RANK_LABEL  = { 1: "1st place", 2: "2nd place", 3: "3rd place" };
const LETTERS     = ["A", "B", "C", "D", "E"];

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

function AnswerReview({ questions, myAnswers }) {
  if (!questions || questions.length === 0) return null;

  // Build a lookup: q_idx → {correct, points}
  const answerMap = {};
  (myAnswers || []).forEach(a => { answerMap[a.q_idx] = a; });

  return (
    <div className="clash-review-section">
      <h3 className="clash-review-title">Answer Review</h3>
      <div className="clash-review-list">
        {questions.map((q, idx) => {
          const myRecord = answerMap[idx];
          const answered  = myRecord !== undefined;
          const correct   = myRecord?.correct ?? false;
          const pts       = myRecord?.points ?? 0;
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
  );
}

export default function ClashResults() {
  const { code } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const token = localStorage.getItem("auth_token");
  const userRaw = localStorage.getItem("user");
  const currentUser = userRaw ? JSON.parse(userRaw) : null;

  const [rankings, setRankings] = useState(location.state?.rankings ?? []);
  const [room, setRoom] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [myAnswers, setMyAnswers] = useState([]);
  const [loading, setLoading] = useState(!location.state?.rankings?.length);
  const [error, setError] = useState("");
  const [showReview, setShowReview] = useState(false);

  useEffect(() => {
    if (!token) { navigate("/auth/login"); return; }
    fetch(`${DJANGO_API_URL}/clash/${code}/results/`, {
      headers: { Authorization: `Token ${token}` },
    })
      .then(r => r.json())
      .then(data => {
        if (data.detail) { setError(data.detail); setLoading(false); return; }
        setRankings(data.rankings?.length ? data.rankings : rankings);
        setRoom(data);
        setQuestions(data.questions || []);
        setMyAnswers(data.my_answers || []);
        setLoading(false);
      })
      .catch(() => {
        if (rankings.length) setLoading(false);
        else { setError("Failed to load results."); setLoading(false); }
      });
  }, []); // eslint-disable-line

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="clash-results-page clash-center-screen">
          <div className="clash-spinner" />
          <p>Loading results…</p>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <Navbar />
        <div className="clash-results-page">
          <p className="clash-error">{error}</p>
          <button className="clash-btn-primary" onClick={() => navigate("/clash")}>
            Back to Clash
          </button>
        </div>
      </>
    );
  }

  const top3 = rankings.slice(0, 3);
  const myEntry = rankings.find(r => r.username === currentUser?.username);
  const podiumOrder = [top3[1] ?? null, top3[0] ?? null, top3[2] ?? null];

  return (
    <>
    <Navbar />
    <div className="clash-results-page">
      <p className="clash-kicker">Final Results</p>
      <h1 className="clash-page-title">Game Over</h1>
      <p className="clash-page-sub">
        Room {code}{room?.subject ? ` · ${room.subject}` : ""}{room?.num_questions ? ` · ${room.num_questions} questions` : ""}
      </p>

      {/* ── My result ── */}
      {myEntry && (
        <div className={`clash-my-result-card ${myEntry.rank <= 3 ? "top" : ""}`}>
          <div className="clash-my-result-rank">
            {MEDAL_EMOJI[myEntry.rank] ?? `#${myEntry.rank}`}
          </div>
          <div>
            <p className="clash-my-result-label">
              You finished {RANK_LABEL[myEntry.rank] ?? `#${myEntry.rank}`}
            </p>
            <p className="clash-my-result-score">{myEntry.score} points · {myEntry.correct}/{room?.num_questions} correct</p>
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

      {/* ── Full leaderboard ── */}
      <div className="clash-rankings-card">
        <h3>Leaderboard</h3>
        {rankings.map(entry => {
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
                <div className="clash-ranking-detail">{entry.score} pts · {entry.correct}/{room?.num_questions} correct</div>
              </div>
              <div className="clash-ranking-score">{entry.score}</div>
            </div>
          );
        })}
      </div>

      {/* ── Answer review toggle ── */}
      {questions.length > 0 && (
        <button
          className="clash-btn-secondary"
          style={{ marginBottom: "8px" }}
          onClick={() => setShowReview(v => !v)}
        >
          {showReview ? "Hide Answer Review" : "Review Answers"}
        </button>
      )}
      {showReview && <AnswerReview questions={questions} myAnswers={myAnswers} />}

      {/* ── Actions ── */}
      <div className="clash-results-actions">
        <button className="clash-btn-secondary" onClick={() => navigate("/clash/history")}>
          My History
        </button>
        <button className="clash-btn-secondary" onClick={() => navigate("/clash")}>
          New Clash
        </button>
        <button className="clash-btn-primary" onClick={() => navigate("/dashboard")}>
          Dashboard
        </button>
      </div>
    </div>
    </>
  );
}
