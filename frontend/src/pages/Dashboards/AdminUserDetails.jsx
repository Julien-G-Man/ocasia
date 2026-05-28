import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft } from '@fortawesome/free-solid-svg-icons';
import AdminAppShell from '../../components/AppShell/AdminAppShell';
import { useAuth } from '../../context/AuthContext';
import { dashboardService } from '../../services/dashboard';
import './AdminUserDetails.css';

const nfmt = (v) => (typeof v === 'number' ? v.toLocaleString() : (v ?? '0'));

const relTime = (isoDate) => {
  const dt = new Date(isoDate);
  if (Number.isNaN(dt.getTime())) return '';
  const secs = Math.floor((Date.now() - dt.getTime()) / 1000);
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
};

export default function AdminUserDetails() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { user, isAuthenticated, logout, getUserRole } = useAuth();
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/auth/login');
      return;
    }
    if (getUserRole() !== 'admin') navigate('/dashboard');
  }, [isAuthenticated, getUserRole, navigate]);

  useEffect(() => {
    if (!id || !isAuthenticated || getUserRole() !== 'admin') return;
    setLoading(true);
    dashboardService.getAdminUserDetails(id)
      .then(setPayload)
      .catch((err) => {
        console.error(err);
        setPayload(null);
      })
      .finally(() => setLoading(false));
  }, [id, isAuthenticated, getUserRole]);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const summary = payload?.summary || {};
  const tokens = payload?.estimated_tokens || {};
  const recentActivity = payload?.recent_activity || [];

  const cards = [
    { label: 'Total Quizzes', value: nfmt(summary.total_quizzes) },
    { label: 'Quiz Questions', value: nfmt(summary.total_quiz_questions) },
    { label: 'Flashcard Decks', value: nfmt(summary.total_flashcard_decks) },
    { label: 'Flashcards', value: nfmt(summary.total_flashcards) },
    { label: 'Chat Sessions', value: nfmt(summary.total_chat_sessions) },
    { label: 'Chat Messages', value: nfmt(summary.total_chat_messages) },
    { label: 'Materials Uploaded', value: nfmt(summary.total_materials) },
    { label: 'Total Clashes', value: nfmt(summary.total_clashes) },
    { label: 'Clashes Hosted', value: nfmt(summary.clashes_as_host) },
    { label: 'Clash Wins', value: nfmt(summary.clash_wins) },
    { label: 'Clash Avg Score', value: summary.clash_avg_score != null ? `${summary.clash_avg_score}` : '—' },
    { label: 'Average Quiz Score', value: `${summary.average_score ?? 0}%` },
    {
      label: 'User Rating',
      value: summary.user_rating ? `${summary.user_rating}/5 ★` : 'Not rated',
      highlight: !!summary.user_rating
    },
    { label: 'Token Burn (Total)', value: nfmt(tokens.total) },
  ];

  return (
    <AdminAppShell>
      <main className="db-main">
          <div className="db-tab">
            <div className="db-page-header">
              <button className="db-btn db-btn-ghost db-btn-sm admin-user-back" onClick={() => navigate('/admin-dashboard')}>
                <FontAwesomeIcon icon={faArrowLeft} />
                Back to Users
              </button>
              <h1>User Analytics</h1>
              <p>
                {loading
                  ? 'Loading user analytics...'
                  : `${payload?.user?.username || 'Unknown'} (${payload?.user?.email || 'no-email'})`}
              </p>
            </div>

            <div className="db-stats-grid db-stats-grid--two">
              {cards.map((c) => (
                <div className="db-stat-card" key={c.label} style={c.highlight ? { borderColor: '#fbbf24' } : {}}>
                  <div className="db-stat-body">
                    <p>{c.label}</p>
                    <h3 style={c.highlight ? { color: '#fbbf24' } : {}}>{loading ? '-' : c.value}</h3>
                  </div>
                </div>
              ))}
            </div>

            <div className="db-card">
              <div className="db-card-header"><h2>Estimated Tokens by Feature</h2></div>
              <div className="db-stats-grid db-stats-grid--two">
                <div className="db-stat-card"><div className="db-stat-body"><p>Quiz</p><h3>{loading ? '-' : nfmt(tokens.quiz)}</h3></div></div>
                <div className="db-stat-card"><div className="db-stat-body"><p>Flashcards</p><h3>{loading ? '-' : nfmt(tokens.flashcards)}</h3></div></div>
                <div className="db-stat-card"><div className="db-stat-body"><p>Chat</p><h3>{loading ? '-' : nfmt(tokens.chat)}</h3></div></div>
                <div className="db-stat-card"><div className="db-stat-body"><p>Clash (hosted)</p><h3>{loading ? '-' : nfmt(tokens.clash)}</h3></div></div>
                <div className="db-stat-card"><div className="db-stat-body"><p>Total</p><h3>{loading ? '-' : nfmt(tokens.total)}</h3></div></div>
                <div className="db-stat-card"><div className="db-stat-body"><p>Est. Cost (USD)</p><h3>{loading ? '-' : `$${tokens.estimated_cost_usd ?? '0.0000'}`}</h3></div></div>
              </div>
            </div>

            <div className="db-card">
              <div className="db-card-header"><h2>Recent Activity</h2></div>
              {loading ? (
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Loading activity...</p>
              ) : recentActivity.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>No recent activity.</p>
              ) : (
                <div className="db-timeline">
                  {recentActivity.map((a, idx) => {
                    const typeLabel = {
                      quiz: 'Quiz',
                      flashcards: 'Flashcards',
                      chat: 'Chat Session',
                      material: 'Material Uploaded',
                      clash: 'Clash',
                    }[a.type] ?? a.type;
                    return (
                      <div className="db-timeline-item" key={`${a.type}-${a.created_at}-${idx}`}>
                        <div className="db-timeline-dot" />
                        <div className="db-timeline-body">
                          <h4>{typeLabel}</h4>
                          <p>{a.text}</p>
                          <span>{relTime(a.created_at)}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
      </main>
    </AdminAppShell>
  );
}
