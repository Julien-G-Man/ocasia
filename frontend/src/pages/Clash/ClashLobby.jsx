import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../../components/Navbar";
import "./Clash.css";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL;
const DJANGO_ROOT_URL = DJANGO_API_URL.replace(/\/api\/?$/, "");
// Canonical frontend origin — set VITE_APP_URL=https://ocasia.vercel.app in Vercel env vars.
// Falls back to the current origin so local dev still works without the var.
const APP_URL = (import.meta.env.VITE_APP_URL || window.location.origin).replace(/\/$/, "");

function PlayerAvatar({ participant, className = "" }) {
  const [imgFailed, setImgFailed] = useState(false);
  const name = participant.display_name || participant.username;
  if (participant.profile_image && !imgFailed) {
    return (
      <img
        src={participant.profile_image}
        alt={name}
        className={className}
        style={{ objectFit: "cover", borderRadius: "50%" }}
        onError={() => setImgFailed(true)}
      />
    );
  }
  return <div className={className}>{name[0].toUpperCase()}</div>;
}

function buildWsUrl(code, token) {
  const proto = DJANGO_ROOT_URL.startsWith("https") ? "wss" : "ws";
  const host = DJANGO_ROOT_URL.replace(/^https?:\/\//, "");
  return `${proto}://${host}/ws/clash/${code}/?token=${token}`;
}

export default function ClashLobby() {
  const { code } = useParams();
  const navigate = useNavigate();

  const token = localStorage.getItem("auth_token");
  const userRaw = localStorage.getItem("user");
  const currentUser = userRaw ? JSON.parse(userRaw) : null;

  const [room, setRoom] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [countdown, setCountdown] = useState(null);
  const [copied, setCopied] = useState(false);
  const [shared, setShared] = useState(false);
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState("");
  const [startError, setStartError] = useState("");
  const [joinError, setJoinError] = useState("");

  const wsRef = useRef(null);
  const countdownRef = useRef(null);
  const roomRef = useRef(null);

  async function loadRoomInfo() {
    const response = await fetch(`${DJANGO_API_URL}/clash/${code}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const data = await response.json();
    if (data.detail) {
      setError(data.detail);
      return null;
    }
    setRoom(data);
    roomRef.current = data;
    setParticipants(data.participants || []);
    if (data.status === "active") navigate(`/clash/play/${code}`);
    if (data.status === "finished") navigate(`/clash/results/${code}`);
    return data;
  }

  useEffect(() => {
    if (!token) navigate("/auth/login");
  }, []); // eslint-disable-line

  // Fetch room info
  useEffect(() => {
    if (!token) return;
    loadRoomInfo().catch(() => setError("Failed to load room info."));
  }, []); // eslint-disable-line

  // WebSocket
  useEffect(() => {
    if (!token) return;
    const ws = new WebSocket(buildWsUrl(code, token));
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }

      if (msg.type === "clash.player_joined") {
        setParticipants(msg.participants || []);
      }
      if (msg.type === "error") {
        setStartError(msg.message || "Something went wrong.");
      }
      if (msg.type === "clash.game_starting") {
        let rem = msg.countdown ?? 3;
        setCountdown(rem);
        clearInterval(countdownRef.current);
        countdownRef.current = setInterval(() => {
          rem -= 1;
          setCountdown(rem);
          if (rem <= 0) {
            clearInterval(countdownRef.current);
            navigate(`/clash/play/${code}`, {
              state: { timePerQuestion: roomRef.current?.time_per_question ?? 20 },
            });
          }
        }, 1000);
      }
    };

    ws.onerror = () => setError("Connection error. Please refresh.");

    return () => {
      clearInterval(countdownRef.current);
      ws.close();
    };
  }, [token, code]); // eslint-disable-line

  function handleStart() {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "start_game" }));
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  async function handleJoin() {
    setJoinError("");
    setJoining(true);
    try {
      const response = await fetch(`${DJANGO_API_URL}/clash/join/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Token ${token}`,
        },
        body: JSON.stringify({ room_code: code }),
      });
      const data = await response.json();
      if (!response.ok) {
        setJoinError(data.detail || "Failed to join room.");
        return;
      }
      await loadRoomInfo();
    } catch {
      setJoinError("Network error. Please try again.");
    } finally {
      setJoining(false);
    }
  }

  function handleShare() {
    const shareUrl = `${APP_URL}/clash/share/${code}/`;
    const hostName = currentUser?.display_name || currentUser?.username || "Someone";
    const subject = room?.subject ? ` on "${room.subject}"` : "";
    const text = `${hostName} is inviting you to a Clash quiz battle${subject}! Join with code ${code} — tap the link to enter directly.`;
    if (navigator.share) {
      navigator.share({ title: `${hostName} invited you to Clash`, text, url: shareUrl });
    } else {
      navigator.clipboard.writeText(`${text}\n${shareUrl}`).then(() => {
        setShared(true);
        setTimeout(() => setShared(false), 2000);
      });
    }
  }

  const isHost = participants.some(
    p => p.username === currentUser?.username && p.is_host
  );
  const isParticipant = participants.some(
    p => p.username === currentUser?.username
  );
  const canJoin = room?.status === "waiting" && !isParticipant;

  return (
    <>
    <Navbar />
    <div className="clash-lobby-page">

      {/* Countdown overlay */}
      {countdown !== null && (
        <div className="clash-loading-overlay">
          <div className="clash-loading-card">
            <div className="clash-countdown-num">{countdown}</div>
            <p>Get ready — game starting</p>
          </div>
        </div>
      )}

      <p className="clash-kicker">Lobby</p>
      <h1 className="clash-page-title">{room?.subject ?? "Loading…"}</h1>
      <p className="clash-page-sub">
        Share the code with friends. The game starts when the host clicks Start.
      </p>

      {/* Room code */}
      <div className="clash-room-code-card">
        <div>
          <div className="clash-room-code-label">Room Code</div>
          <div className="clash-room-code-value">{code}</div>
        </div>
        <div className="clash-room-code-actions">
          <button className="clash-copy-btn" onClick={handleCopy}>
            {copied ? "Copied!" : "Copy Code"}
          </button>
          <button className="clash-copy-btn" onClick={handleShare}>
            {shared ? "Link Copied!" : "Share Link"}
          </button>
        </div>
      </div>

      {/* Room meta */}
      {room && (
        <div className="clash-lobby-meta">
          <span className="clash-meta-pill" style={{ textTransform: "capitalize" }}>{room.difficulty}</span>
          <span className="clash-meta-pill">{room.num_questions} questions</span>
          <span className="clash-meta-pill">{room.time_per_question}s per question</span>
        </div>
      )}

      {/* Participants */}
      <div className="clash-participants-card">
        <div className="clash-participants-header">
          <h3>Players</h3>
          <span className="clash-participants-count">{participants.length} / 20</span>
        </div>
        <div className="clash-participant-list">
          {participants.length === 0 && (
            <p className="clash-lobby-empty">Waiting for players to join…</p>
          )}
          {participants.map(p => (
            <div key={p.username} className="clash-participant-row">
              <PlayerAvatar participant={p} className="clash-participant-avatar" />
              <span className="clash-participant-name">
                {p.display_name || p.username}
                {p.username === currentUser?.username && (
                  <span className="clash-you-tag"> (you)</span>
                )}
              </span>
              {p.is_host && <span className="clash-host-badge">Host</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="clash-lobby-actions">
        {isHost ? (
          <>
            <button
              className="clash-btn-primary"
              onClick={handleStart}
              disabled={countdown !== null}
            >
              Start Clash
              {participants.length === 1 && " (solo)"}
            </button>
            {startError && <p className="clash-error">{startError}</p>}
          </>
        ) : (
          <>
            {canJoin ? (
              <button className="clash-btn-primary" onClick={handleJoin} disabled={joining}>
                {joining ? "Joining…" : "Join Clash"}
              </button>
            ) : (
              <p className="clash-lobby-status">Waiting for the host to start the game…</p>
            )}
          </>
        )}
        {joinError && <p className="clash-error">{joinError}</p>}
      </div>

      {error && <p className="clash-error">{error}</p>}
    </div>
    </>
  );
}
