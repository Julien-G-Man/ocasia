import { useState, useEffect } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import Navbar from "../../components/Navbar";
import "./Clash.css";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL;

const MEDAL_EMOJI = { 1: "🥇", 2: "🥈", 3: "🥉" };
const RANK_LABEL  = { 1: "1st place", 2: "2nd place", 3: "3rd place" };

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

export default function ClashResults() {
  const { code } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const token = localStorage.getItem("auth_token");
  const userRaw = localStorage.getItem("user");
  const currentUser = userRaw ? JSON.parse(userRaw) : null;

  const [rankings, setRankings] = useState(location.state?.rankings ?? []);
  const [room, setRoom] = useState(null);
  const [loading, setLoading] = useState(!location.state?.rankings?.length);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) { navigate("/auth/login"); return; }
    fetch(`${DJANGO_API_URL}/clash/${code}/results/`, {
      headers: { Authorization: `Token ${token}` },
    })
      .then(r => r.json())
      .then(data => {
        if (data.detail) { setError(data.detail); setLoading(false); return; }
        // Prefer fresh rankings (include profile_image); fall back to state rankings
        setRankings(data.rankings?.length ? data.rankings : rankings);
        setRoom(data);
        setLoading(false);
      })
      .catch(() => {
        // If fetch fails but we already have rankings from state, show them
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
  // Podium order: 2nd (left) · 1st (centre, taller) · 3rd (right)
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
            <p className="clash-my-result-score">{myEntry.score} points</p>
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
                <div className="clash-ranking-detail">{entry.score} points</div>
              </div>
              <div className="clash-ranking-score">{entry.score}</div>
            </div>
          );
        })}
      </div>

      {/* ── Actions ── */}
      <div className="clash-results-actions">
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
