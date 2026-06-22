import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../../components/AppShell/AppShell";
import "../Dashboards/AdminDashboard.css";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL;

const DIFF_BADGE = {
  easy:   "db-badge-green",
  medium: "db-badge-blue",
  hard:   "db-badge-gray",
};

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
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
      .then(data => { setClashes(data.clashes || []); setLoading(false); })
      .catch(() => { setError("Failed to load clash history."); setLoading(false); });
  }, []); // eslint-disable-line

  return (
    <AppShell>
      <main className="db-main">
        <div className="db-page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h1>My Clash History</h1>
            <p>All the battles you've taken part in.</p>
          </div>
          <button className="db-btn db-btn-primary db-btn-sm" onClick={() => navigate("/clash")}>
            + New Clash
          </button>
        </div>

        {loading ? (
          <div className="db-card" style={{ textAlign: "center", padding: "48px 24px", color: "var(--text-secondary)" }}>
            <p>Loading history…</p>
          </div>
        ) : error ? (
          <div className="db-card">
            <p style={{ color: "var(--color-error)", textAlign: "center", padding: "24px" }}>{error}</p>
          </div>
        ) : clashes.length === 0 ? (
          <div className="db-card" style={{ textAlign: "center", padding: "48px 24px", color: "var(--text-secondary)" }}>
            <p style={{ fontSize: "2em", marginBottom: "8px" }}>⚔️</p>
            <p>You haven't played any clashes yet.</p>
            <button className="db-btn db-btn-primary" style={{ marginTop: "16px" }} onClick={() => navigate("/clash")}>
              Start a Clash
            </button>
          </div>
        ) : (
          <div className="db-table-wrap">
            <table className="db-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Subject</th>
                  <th>Difficulty</th>
                  <th>Questions</th>
                  <th>Players</th>
                  <th>Your Rank</th>
                  <th>Score</th>
                  <th>Finished</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {clashes.map(c => (
                  <tr
                    key={c.room_code}
                    style={{ cursor: "pointer" }}
                    onClick={() => navigate(`/clash/history/${c.room_code}`)}
                  >
                    <td data-label="Code">
                      <span style={{ fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.08em", color: "var(--text-primary)" }}>
                        {c.room_code}
                      </span>
                    </td>
                    <td data-label="Subject" style={{ color: "var(--text-primary)", fontWeight: 600 }}>
                      {c.subject}
                    </td>
                    <td data-label="Difficulty">
                      <span className={`db-badge ${DIFF_BADGE[c.difficulty] || "db-badge-gray"}`} style={{ textTransform: "capitalize" }}>
                        {c.difficulty}
                      </span>
                    </td>
                    <td data-label="Questions" style={{ textAlign: "center" }}>{c.num_questions}</td>
                    <td data-label="Players" style={{ textAlign: "center" }}>{c.player_count}</td>
                    <td data-label="Your Rank" style={{ textAlign: "center", fontSize: "1.1em" }}>
                      {c.rank === 1 ? "🥇" : c.rank === 2 ? "🥈" : c.rank === 3 ? "🥉" : `#${c.rank}`}
                      {c.is_host && (
                        <span className="db-badge db-badge-blue" style={{ marginLeft: "6px", fontSize: "0.75em" }}>Host</span>
                      )}
                    </td>
                    <td data-label="Score" style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                      {c.score.toLocaleString()} pts
                    </td>
                    <td data-label="Finished">{fmt(c.finished_at)}</td>
                    <td>
                      <button
                        className="db-btn db-btn-ghost db-btn-sm"
                        onClick={e => { e.stopPropagation(); navigate(`/clash/history/${c.room_code}`); }}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </AppShell>
  );
}
