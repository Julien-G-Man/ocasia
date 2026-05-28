import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faUsers,
  faChartBar,
  faFileAlt,
  faComments,
  faLayerGroup,
  faTriangleExclamation,
  faTrophy,
  faBook,
  faBolt,
  faStopwatch,
} from '@fortawesome/free-solid-svg-icons';
import AdminAppShell from '../../components/AppShell/AdminAppShell';
import { useAuth } from '../../context/AuthContext';
import RichTextRenderer from '../../utils/richTextRenderer';
import './AdminDashboard.css';
import { dashboardService } from '../../services/dashboard';

const nfmt = (v) => (typeof v === 'number' ? v.toLocaleString() : (v ?? '0'));

const formatRelativeTime = (isoDate) => {
  const dt = new Date(isoDate);
  if (Number.isNaN(dt.getTime())) return '';
  const seconds = Math.floor((Date.now() - dt.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};

const AnalyticsLineChart = ({ labels = [], series = {} }) => {
  const width = 920;
  const height = 280;
  const padding = 28;
  const keys = [
    { id: 'new_users', label: 'New Users', color: '#f59e0b' },
    { id: 'quizzes', label: 'Quizzes', color: '#22c55e' },
    { id: 'decks', label: 'Decks', color: '#38bdf8' },
    { id: 'chat_messages', label: 'Chat Messages', color: '#0d2170' },
    { id: 'uploaded_materials', label: 'Materials', color: '#921e1e' },
    { id: 'clashes', label: 'Clashes', color: '#a855f7' },
  ];

  const maxVal = Math.max(1, ...keys.flatMap((k) => series[k.id] || [0]));

  const xFor = (idx) => {
    if (labels.length <= 1) return padding;
    const span = width - padding * 2;
    return padding + (idx / (labels.length - 1)) * span;
  };

  const yFor = (val) => {
    const span = height - padding * 2;
    return height - padding - (val / maxVal) * span;
  };

  const pointsFor = (arr = []) => arr.map((v, i) => `${xFor(i)},${yFor(v)}`).join(' ');

  const yTicks = Array.from({ length: 5 }, (_, i) => {
    const v = Math.round((maxVal / 4) * i);
    return { value: v, y: yFor(v) };
  });

  const compactLabel = (isoDate) => {
    const d = new Date(isoDate);
    if (Number.isNaN(d.getTime())) return isoDate;
    return `${d.getMonth() + 1}/${d.getDate()}`;
  };

  return (
    <div className="usage-chart-wrap">
      <div className="usage-chart-legend">
        {keys.map((k) => (
          <span key={k.id} className="usage-legend-item">
            <i style={{ background: k.color }} />
            {k.label}
          </span>
        ))}
      </div>
      <div className="usage-chart-scroll">
        <svg viewBox={`0 0 ${width} ${height}`} className="usage-chart-svg" role="img" aria-label="Usage analytics chart">
          {yTicks.map((t) => (
            <g key={t.value}>
              <line x1={padding} x2={width - padding} y1={t.y} y2={t.y} stroke="rgba(148,163,184,0.25)" strokeWidth="1" />
              <text x={4} y={t.y + 4} fontSize="11" fill="#94a3b8">{t.value}</text>
            </g>
          ))}

          {keys.map((k) => (
            <polyline
              key={k.id}
              fill="none"
              stroke={k.color}
              strokeWidth="2.5"
              points={pointsFor(series[k.id] || [])}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}

          {labels.map((label, i) => {
            if (!(i === 0 || i === labels.length - 1 || i % 3 === 0)) return null;
            return (
              <text key={`${label}-${i}`} x={xFor(i)} y={height - 6} textAnchor="middle" fontSize="10.5" fill="#94a3b8">
                {compactLabel(label)}
              </text>
            );
          })}
        </svg>
      </div>
    </div>
  );
};

export default function AdminOverview() {
  const navigate = useNavigate();
  const { isAuthenticated, getUserRole } = useAuth();
  const [adminStats, setAdminStats] = useState({});
  const [feedbackData, setFeedbackData] = useState({ ratings: [], total: 0, average_rating: 0 });
  const [usageTrends, setUsageTrends] = useState({ labels: [], series: {} });
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingFeedback, setLoadingFeedback] = useState(true);
  const [loadingTrends, setLoadingTrends] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/auth/login');
      return;
    }
    if (getUserRole() !== 'admin') navigate('/dashboard');
  }, [isAuthenticated, getUserRole, navigate]);

  useEffect(() => {
    if (!isAuthenticated || getUserRole() !== 'admin') return;

    dashboardService.getAdminStats()
      .then(setAdminStats)
      .catch(console.error)
      .finally(() => setLoadingStats(false));

    dashboardService.getAdminQuizFeedback(20)
      .then(setFeedbackData)
      .catch(console.error)
      .finally(() => setLoadingFeedback(false));

    dashboardService.getAdminUsageTrends(14)
      .then(setUsageTrends)
      .catch(console.error)
      .finally(() => setLoadingTrends(false));
  }, [isAuthenticated, getUserRole]);

  const statCards = [
    { icon: faUsers, label: 'Total Users', value: nfmt(adminStats.total_users) },
    { icon: faComments, label: 'Chat Messages', value: nfmt(adminStats.total_chat_messages) },
    { icon: faChartBar, label: 'Quizzes', value: nfmt(adminStats.total_quizzes) },
    { icon: faFileAlt, label: 'Flashcard Decks', value: nfmt(adminStats.total_flashcard_decks) },
    { icon: faLayerGroup, label: 'Flashcards', value: nfmt(adminStats.total_flashcards) },
    { icon: faBook, label: 'Uploaded Materials', value: nfmt(adminStats.total_materials) },
    { icon: faBolt, label: 'Clashes', value: nfmt(adminStats.total_clashes) },
    {
      icon: faTriangleExclamation,
      label: 'Anonymous API Hits (24h)',
      value: nfmt(adminStats.activity_24h?.anonymous_api_hits),
    },
  ];

  const recentRatings = useMemo(() => {
    if (Array.isArray(adminStats.recent_ratings) && adminStats.recent_ratings.length) {
      return adminStats.recent_ratings.slice(0, 8);
    }
    return (feedbackData.ratings || []).slice(0, 8);
  }, [adminStats.recent_ratings, feedbackData]);

  return (
    <AdminAppShell>
      <main className="db-main">
        <div className="db-page-header">
          <h1>Admin Overview</h1>
          <p>Global usage, engagement, and AI consumption metrics.</p>
        </div>

        <div className="db-stats-grid db-stats-grid--two">
          {statCards.map(({ icon, label, value }) => (
            <div className="db-stat-card" key={label}>
              <div className="db-stat-icon"><FontAwesomeIcon icon={icon} /></div>
              <div className="db-stat-body">
                <p>{label}</p>
                <h3>{loadingStats ? '-' : value}</h3>
              </div>
            </div>
          ))}
        </div>

        <div className="db-card">
          <div className="db-card-header"><h2>Usage Analytics (14 Days)</h2></div>
          {loadingTrends ? (
            <p style={{ color: 'var(--text-secondary)' }}>Loading analytics...</p>
          ) : (
            <AnalyticsLineChart labels={usageTrends.labels} series={usageTrends.series} />
          )}
        </div>

        <div className="db-card">
          <div className="db-card-header">
            <h2>Recent Real Activity (Last 24 Hours)</h2>
            <button type="button" className="db-btn db-btn-ghost db-btn-sm" onClick={() => navigate('/admin-dashboard/activity')}>
              View All Activity
            </button>
          </div>
          <div className="db-timeline">
            {(adminStats.recent_activity || []).length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', margin: 0 }}>No activity in the past 24 hours.</p>
            ) : (
              (adminStats.recent_activity || []).map((item, idx) => (
                <div className="db-timeline-item" key={`${item.type}-${item.created_at}-${idx}`}>
                  <div className="db-timeline-dot" />
                  <div className="db-timeline-body">
                    <h4>{item.actor}</h4>
                    <p>{item.text}</p>
                    <span>{formatRelativeTime(item.created_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="db-card">
          <div className="db-card-header"><h2>Estimated Token Usage</h2></div>
          <div className="db-stats-grid db-stats-grid--two">
            <div className="db-stat-card"><div className="db-stat-body"><p>Chat</p><h3>{nfmt(adminStats.estimated_tokens?.chat)}</h3></div></div>
            <div className="db-stat-card"><div className="db-stat-body"><p>Quiz</p><h3>{nfmt(adminStats.estimated_tokens?.quiz)}</h3></div></div>
            <div className="db-stat-card"><div className="db-stat-body"><p>Flashcards</p><h3>{nfmt(adminStats.estimated_tokens?.flashcards)}</h3></div></div>
            <div className="db-stat-card"><div className="db-stat-body"><p>Clash</p><h3>{nfmt(adminStats.estimated_tokens?.clash)}</h3></div></div>
            <div className="db-stat-card"><div className="db-stat-body"><p>Total</p><h3>{nfmt(adminStats.estimated_tokens?.total)}</h3></div></div>
            <div className="db-stat-card"><div className="db-stat-body"><p>Est. Cost (USD)</p><h3>{loadingStats ? '-' : `$${adminStats.estimated_tokens?.estimated_cost_usd ?? '0.0000'}`}</h3></div></div>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: 10 }}>
            {adminStats.estimated_tokens?.note || 'Approximation based on stored text volume.'}
          </p>
        </div>

        <div className="db-card">
          <div className="db-card-header"><h2>AI Response Time (7-Day Avg)</h2></div>
          <div className="db-stats-grid db-stats-grid--two">
            <div className="db-stat-card">
              <div className="db-stat-icon"><FontAwesomeIcon icon={faStopwatch} /></div>
              <div className="db-stat-body">
                <p>Avg Response Time</p>
                <h3>{loadingStats ? '-' : `${nfmt(adminStats.avg_response_ms)} ms`}</h3>
              </div>
            </div>
            <div className="db-stat-card">
              <div className="db-stat-body">
                <p>Sample Size (7d)</p>
                <h3>{loadingStats ? '-' : nfmt(adminStats.latency_sample_count)}</h3>
              </div>
            </div>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: 10 }}>
            Measured across Chat, Quiz, and Flashcard AI calls. Zero means no data recorded yet.
          </p>
        </div>

        <div className="db-card">
          <div className="db-card-header">
            <h2>Recent Quiz Experience Ratings</h2>
            <button type="button" className="db-btn db-btn-ghost db-btn-sm" onClick={() => navigate('/admin-dashboard/ratings')}>
              View All Ratings
            </button>
          </div>
          <div style={{ marginBottom: '12px', padding: '10px', background: 'rgba(251, 191, 36, 0.1)', borderRadius: '8px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {nfmt(adminStats.total_ratings || 0)} total ratings • Average: {adminStats.average_experience_rating || '0.00'}/5 ★
            </span>
          </div>
          {(loadingFeedback || loadingStats) ? (
            <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Loading ratings...</p>
          ) : !recentRatings || recentRatings.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', margin: 0 }}>No ratings submitted yet. Users will see star ratings after completing quizzes.</p>
          ) : (
            <div className="db-ratings-list">
              {recentRatings.map((item, idx) => (
                <div className="db-rating-item" key={`${item.actor}-${item.created_at}-${idx}`}>
                  <div>
                    <p className="db-rating-actor">{item.actor}</p>
                    <span className="db-rating-time">{formatRelativeTime(item.created_at)}</span>
                  </div>
                  <strong className="db-rating-score">{item.rating}/5 ★</strong>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </AdminAppShell>
  );
}
