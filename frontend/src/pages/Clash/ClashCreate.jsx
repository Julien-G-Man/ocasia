import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppShell from "../../components/AppShell/AppShell";
import "./Clash.css";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL;

export default function ClashCreate() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = localStorage.getItem("auth_token");
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!token) navigate("/auth/login");
  }, []); // eslint-disable-line

  const prefillCode = searchParams.get("join")?.toUpperCase() ?? "";
  const [tab, setTab] = useState(prefillCode ? "join" : "host");

  // Host form
  const [subject, setSubject] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [numQuestions, setNumQuestions] = useState(10);
  const [timePerQuestion, setTimePerQuestion] = useState(20);

  // Source material tabs
  const [sourceTab, setSourceTab] = useState("file");
  const [studyText, setStudyText] = useState("");
  const [fileName, setFileName] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);

  // Join form
  const [joinCode, setJoinCode] = useState(prefillCode);

  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState("");

  async function extractFile(file) {
    setFileName(`${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
    setIsExtracting(true);
    setStudyText("");
    const formData = new FormData();
    formData.append("slide_file", file);
    try {
      const res = await fetch(`${DJANGO_API_URL}/quiz/ajax-extract-text/`, {
        method: "POST",
        headers: { Authorization: `Token ${token}` },
        body: formData,
      });
      const data = await res.json();
      if (data.text) {
        setStudyText(data.text);
        setSourceTab("text");
      } else {
        setError("Could not extract text from this file.");
      }
    } catch {
      setError("File extraction failed. Try pasting the text instead.");
    } finally {
      setIsExtracting(false);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!subject.trim()) { setError("Topic is required."); return; }
    setError("");
    setLoading(true);
    setLoadingMsg("Generating questions — this may take 30–60 seconds.");
    try {
      const body = {
        subject,
        difficulty,
        num_questions: numQuestions,
        time_per_question: timePerQuestion,
        ...(studyText.trim().length >= 50 ? { study_text: studyText } : {}),
      };
      const res = await fetch(`${DJANGO_API_URL}/clash/create/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Token ${token}` },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Failed to create room."); setLoading(false); return; }
      navigate(`/clash/lobby/${data.room_code}`, { state: data });
    } catch {
      setError("Network error. Please try again.");
      setLoading(false);
    }
  }

  async function handleJoin(e) {
    e.preventDefault();
    const code = joinCode.trim().toUpperCase();
    if (!code) { setError("Enter a room code."); return; }
    setError("");
    setLoading(true);
    setLoadingMsg("Joining room…");
    try {
      const res = await fetch(`${DJANGO_API_URL}/clash/join/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Token ${token}` },
        body: JSON.stringify({ room_code: code }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Failed to join room."); setLoading(false); return; }
      navigate(`/clash/lobby/${data.room_code}`, { state: data });
    } catch {
      setError("Network error. Please try again.");
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="clash-create-page">
        {(loading || isExtracting) && (
          <div className="clash-loading-overlay">
            <div className="clash-loading-card">
              <div className="clash-spinner" />
              <h3>Please wait</h3>
              <p>{isExtracting ? "Extracting text from file…" : loadingMsg}</p>
            </div>
          </div>
        )}

        {/* ── Hero ── */}
        <div className="clash-hero">
          <div className="clash-hero-text">
            <h1 className="clash-hero-heading">Clash</h1>
            <p className="clash-hero-tagline">Real-time multiplayer quiz battles</p>
            <div className="clash-hero-stats">
              <div className="clash-hero-stat">
                <span className="clash-hero-stat-num">20</span>
                <span className="clash-hero-stat-label">Max Players</span>
              </div>
              <div className="clash-hero-stat">
                <span className="clash-hero-stat-num">1500</span>
                <span className="clash-hero-stat-label">Max pts / Q</span>
              </div>
              <div className="clash-hero-stat">
                <span className="clash-hero-stat-num">Live</span>
                <span className="clash-hero-stat-label">Leaderboard</span>
              </div>
            </div>
            <button
              className="clash-hero-history-btn"
              type="button"
              onClick={() => navigate("/clash/history")}
            >
              My History →
            </button>
          </div>
          <div className="clash-hero-visual">
            <div className="clash-hero-player">
              <div className="clash-hero-circle">🎮</div>
              <span className="clash-hero-player-label">Host</span>
            </div>
            <div className="clash-hero-vs-badge">VS</div>
            <div className="clash-hero-player">
              <div className="clash-hero-circle">🏆</div>
              <span className="clash-hero-player-label">Players</span>
            </div>
          </div>
        </div>

        {/* ── Host / Join toggle ── */}
        <div className="clash-tab-toggle">
          <button
            className={`clash-tab-btn${tab === "host" ? " active" : ""}`}
            onClick={() => { setTab("host"); setError(""); }}
            type="button"
          >
            Host a Room
          </button>
          <button
            className={`clash-tab-btn${tab === "join" ? " active" : ""}`}
            onClick={() => { setTab("join"); setError(""); }}
            type="button"
          >
            Join a Room
          </button>
        </div>

        {/* ── Active panel ── */}
        {tab === "host" ? (
          <form className="clash-panel clash-panel-single" onSubmit={handleCreate}>
            <p className="clash-panel-sub">
              Pick a topic and settings. Share the room code when ready to start.
            </p>

            <div className="clash-field">
              <label htmlFor="cc-subject">Topic</label>
              <input
                id="cc-subject"
                value={subject}
                onChange={e => { setSubject(e.target.value); setError(""); }}
                placeholder="e.g. Cell biology, World War II, Python…"
                disabled={loading}
              />
            </div>

            {/* ── Source material tabs ── */}
            <div className="clash-source-tab-group">
              <button
                type="button"
                className={`clash-source-tab${sourceTab === "file" ? " active" : ""}`}
                onClick={() => setSourceTab("file")}
                disabled={loading}
              >
                File
              </button>
              <button
                type="button"
                className={`clash-source-tab${sourceTab === "text" ? " active" : ""}`}
                onClick={() => setSourceTab("text")}
                disabled={loading}
              >
                Text
              </button>
            </div>

            {sourceTab === "file" && (
              <div className="clash-source-content clash-source-slide-in">
                <div
                  className="clash-upload-zone"
                  onDragOver={e => e.preventDefault()}
                  onDrop={e => {
                    e.preventDefault();
                    const file = e.dataTransfer.files[0];
                    if (file) extractFile(file);
                  }}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    id="clash-file-input"
                    className="clash-hidden-file-input"
                    accept=".pdf,.docx,.ppt,.pptx,.txt"
                    onChange={e => { if (e.target.files[0]) extractFile(e.target.files[0]); }}
                    disabled={loading || isExtracting}
                  />
                  <div className="clash-upload-icon">↑</div>
                  <div className="clash-upload-text">Upload your study material</div>
                  <div className="clash-upload-desc">PDF, DOCX, PPT, PPTX, TXT</div>
                  <label htmlFor="clash-file-input" className="clash-select-file-btn">
                    {isExtracting ? "Extracting…" : "Select file"}
                  </label>
                  {fileName && (
                    <span className="clash-file-name-display">
                      {studyText
                        ? `${fileName} — ${studyText.length.toLocaleString()} chars extracted`
                        : fileName}
                    </span>
                  )}
                </div>
              </div>
            )}

            {sourceTab === "text" && (
              <div className="clash-source-content clash-source-slide-in">
                <textarea
                  className="clash-source-textarea"
                  placeholder="Paste your notes, lecture slides, or any study material here…"
                  value={studyText}
                  onChange={e => { setStudyText(e.target.value); setError(""); }}
                  disabled={loading}
                />
                <div className="clash-char-count">
                  <span>{studyText.length}</span> / 50 000 characters
                </div>
              </div>
            )}

            <div className="clash-fields-row">
              <div className="clash-field">
                <label htmlFor="cc-diff">Difficulty</label>
                <select id="cc-diff" value={difficulty} onChange={e => setDifficulty(e.target.value)} disabled={loading}>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
              <div className="clash-field">
                <label htmlFor="cc-num">Questions</label>
                <select id="cc-num" value={numQuestions} onChange={e => setNumQuestions(Number(e.target.value))} disabled={loading}>
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={15}>15</option>
                  <option value={20}>20</option>
                  <option value={25}>25</option>
                  <option value={30}>30</option>
                  <option value={40}>40</option>
                  <option value={50}>50</option>
                </select>
              </div>
              <div className="clash-field">
                <label htmlFor="cc-time">Time per Question</label>
                <select id="cc-time" value={timePerQuestion} onChange={e => setTimePerQuestion(Number(e.target.value))} disabled={loading}>
                  <option value={10}>10s — Fast</option>
                  <option value={15}>15s</option>
                  <option value={20}>20s — Standard</option>
                  <option value={30}>30s — Relaxed</option>
                </select>
              </div>
            </div>

            <button className="clash-btn-primary" type="submit" disabled={loading || isExtracting}>
              Create Room
            </button>
          </form>
        ) : (
          <form className="clash-panel clash-panel-single" onSubmit={handleJoin}>
            <p className="clash-panel-sub">
              Enter the 6-character code shared by the host.
            </p>

            <div className="clash-join-code-wrap">
              <p className="clash-join-code-hint">Room code</p>
              <input
                className="clash-code-input"
                value={joinCode}
                onChange={e => { setJoinCode(e.target.value.toUpperCase()); setError(""); }}
                placeholder="XXXXXX"
                maxLength={6}
                disabled={loading}
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            <button
              className="clash-btn-primary"
              type="submit"
              disabled={loading || joinCode.length < 6}
            >
              Join Room
            </button>
          </form>
        )}

        {error && <p className="clash-error">{error}</p>}
      </div>
    </AppShell>
  );
}
