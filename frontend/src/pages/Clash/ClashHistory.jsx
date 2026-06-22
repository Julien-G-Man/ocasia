import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../../components/AppShell/AppShell";
import "./Clash.css";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL;

const MEDAL_EMOJI = { 1: "🥇", 2: "🥈", 3: "🥉" };

const DIFF_BADGE = {
  easy:   { label: "Easy",   color: "#16a34a" },
  medium: { label: "Medium", color: "#d97706" },
  hard:   { label: "Hard",   color: "#dc2626" },
};

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export default function ClashHistory() {
  const navigate = useNavigate();
  const token = localStorage.getItem("auth_token");

  const [clashes, setClashes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) { navigate("/auth/login"); return; }
    fetch(`${DJANGO_API_URL}/clash/my/`, {
      headers: { Authorization: `Token ${token}` },
    })
      .then(r => r.json())
      .then(data => {
        setClashes(data.clashes || []);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load clash history.");
        setLoading(false);
      });
  }, []); // eslint-disable-line

  return (
    <AppShell>
      <div className="clash-history-page">
        <div className="clash-history-header">
          <div>
            <p className="clash-kicker">Clash</p>
            <h1 className="clash-page-title">My History</h1>
            <p className="clash-page-sub" style={{ margin: 0 }}>
              All the battles you've taken part in.
            </p>
          </div>
          <button
            className="clash-history-new-btn"
            onClick={() => navigate("/clash")}
          >
            + New Clash
          </button>
        </div>

        {loading ? (
          <div className="clash-history-empty">
            <div className="clash-spinner" style={{ margin: "0 auto 12px" }} />
            <p>Loading history…</p>
          </div>
        ) : error ? (
          <div className="clash-history-empty">
            <p style={{ color: "var(--clash-red)" }}>{error}</p>
          </div>
        ) : clashes.length === 0 ? (
          <div className="clash-history-empty">
            <p className="clash-history-empty-icon">⚔️</p>
            <p>You haven't played any clashes yet.</p>
            <button className="clash-btn-primary" style={{ marginTop: "12px", maxWidth: "240px" }} onClick={() => navigate("/clash")}>
              Start a Clash
            </button>
          </div>
        ) : (
          <div className="clash-history-list">
            {clashes.map(clash => {
              const diff = DIFF_BADGE[clash.difficulty] || { label: clash.difficulty, color: "#64748b" };
              const rankLabel = MEDAL_EMOJI[clash.rank] ?? `#${clash.rank}`;
              return (
                <button
                  key={clash.room_code}
                  className="clash-history-item"
                  onClick={() => navigate(`/clash/history/${clash.room_code}`)}
                >
                  <div className="clash-history-item-left">
                    <span className="clash-history-rank">{rankLabel}</span>
                    <div className="clash-history-meta">
                      <span className="clash-history-subject">{clash.subject}</span>
                      <div className="clash-history-tags">
                        <span className="clash-history-tag" style={{ color: diff.color, borderColor: diff.color }}>
                          {diff.label}
                        </span>
                        <span className="clash-history-tag">{clash.num_questions}Q</span>
                        <span className="clash-history-tag">{clash.player_count} player{clash.player_count !== 1 ? "s" : ""}</span>
                        {clash.is_host && <span className="clash-history-tag clash-history-tag-host">Host</span>}
                      </div>
                    </div>
                  </div>
                  <div className="clash-history-item-right">
                    <span className="clash-history-score">{clash.score.toLocaleString()} pts</span>
                    <span className="clash-history-date">{fmt(clash.finished_at)}</span>
                    <span className="clash-history-arrow">→</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
