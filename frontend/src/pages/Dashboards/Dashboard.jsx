import React, { useEffect, useState } from 'react';
import AppShell from '../../components/AppShell/AppShell';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faBook,
  faCloudUploadAlt,
  faCalendar,
  faLayerGroup,
  faRobot,
  faTrophy,
  faBolt,
} from '@fortawesome/free-solid-svg-icons';
import './Dashboard.css';
import { dashboardService } from '../../services/dashboard';
import { materialsService } from '../../services/materials';

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

const Dashboard = () => {
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading, logout, getUserRole } = useAuth();

  const [stats, setStats] = useState({
    totalQuizzes: 0,
    averageScore: 0,
    studyStreak: 0,
    totalFlashcards: 0,
  });
  const [clashStats, setClashStats] = useState({
    totalClashes: 0,
    clashWins: 0,
    bestRank: null,
  });
  const [weakAreas, setWeakAreas] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [loadingStats, setLoadingStats] = useState(true);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/auth/login');
      return;
    }
    if (!isLoading && isAuthenticated && getUserRole() === 'admin') {
      navigate('/admin-dashboard');
    }
  }, [isLoading, isAuthenticated, navigate, getUserRole]);

  useEffect(() => {
    if (!isAuthenticated) return;

    setLoadingStats(true);

    Promise.all([
      dashboardService.getStats(),
      dashboardService.getQuizHistory(),
      dashboardService.getFlashcardHistory().catch(() => []),
      materialsService.getMine().catch(() => []),
      dashboardService.getClashHistory().catch(() => []),
    ])
      .then(([statsData, quizzes, flashcardDecks, materials, clashes]) => {
        setStats({
          totalQuizzes: statsData.total_quizzes,
          averageScore: statsData.average_score,
          studyStreak: statsData.study_streak,
          totalFlashcards: statsData.total_flashcard_sets,
        });
        setClashStats({
          totalClashes: statsData.total_clashes || 0,
          clashWins: statsData.clash_wins || 0,
          bestRank: statsData.best_rank ?? null,
        });
        setWeakAreas(statsData.weak_areas || []);

        const quizActivity = (quizzes || []).map((quiz) => ({
          id: `quiz-${quiz.id}`,
          type: 'quiz',
          title: quiz.subject || 'Quiz',
          subtitle: `Score: ${quiz.score_percent}%`,
          score: quiz.score_percent,
          created_at: quiz.created_at,
        }));

        const deckActivity = (flashcardDecks || []).map((deck) => ({
          id: `deck-${deck.id}`,
          type: 'flashcard',
          title: deck.title || deck.subject || 'Flashcard Deck',
          subtitle: `${deck.card_count ?? deck.flashcard_count ?? ''} cards`.trim(),
          created_at: deck.created_at,
        }));

        const materialActivity = (materials || []).map((material) => ({
          id: `material-${material.id}`,
          type: 'material',
          title: material.title,
          subtitle: `${material.file_size_display || ''}${material.file_size_display ? ' · ' : ''}${material.download_count ?? 0} downloads`,
          created_at: material.created_at,
        }));

        const clashActivity = (clashes || []).map((c) => ({
          id: `clash-${c.room_code}`,
          type: 'clash',
          title: c.subject,
          subtitle: `${c.player_count} player${c.player_count !== 1 ? 's' : ''} · ${c.num_questions}Q`,
          rank: c.rank,
          score: c.score,
          player_count: c.player_count,
          created_at: c.finished_at,
        }));

        const mergedActivity = [...quizActivity, ...deckActivity, ...materialActivity, ...clashActivity].sort(
          (a, b) => new Date(b.created_at) - new Date(a.created_at)
        );

        setRecentActivity(mergedActivity);
      })
      .catch(console.error)
      .finally(() => setLoadingStats(false));
  }, [isAuthenticated]);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const statCards = [
    { icon: faBook,       label: 'Total Quizzes',  value: stats.totalQuizzes,       variant: 'blue'   },
    { icon: faTrophy,     label: 'Average Score',  value: `${stats.averageScore}%`, variant: 'green'  },
    { icon: faCalendar,   label: 'Study Streak',   value: `${stats.studyStreak}d`,  variant: 'amber'  },
    { icon: faLayerGroup, label: 'Flashcard Sets', value: stats.totalFlashcards,    variant: 'purple' },
  ];

  const quickActions = [
    { icon: faBook,           title: 'Quiz',       desc: 'Generate a quiz from your notes',   path: '/quiz',           variant: 'blue'   },
    { icon: faLayerGroup,     title: 'Flashcards', desc: 'Create smart flashcard sets',       path: '/flashcards',     variant: 'purple' },
    { icon: faCloudUploadAlt, title: 'Materials',  desc: 'Open your uploaded materials',      path: '/materials/mine', variant: 'green'  },
    { icon: faRobot,          title: 'AI Tutor',   desc: 'Get instant personalised help',     path: '/ai-tutor',       variant: 'amber'  },
  ];

  const activityIcon = (type) => {
    if (type === 'quiz') return faBook;
    if (type === 'material') return faCloudUploadAlt;
    if (type === 'clash') return faBolt;
    return faLayerGroup;
  };
  const activityLabel = (type) => {
    if (type === 'quiz') return 'Quiz';
    if (type === 'material') return 'Material uploaded';
    if (type === 'clash') return 'Clash';
    return 'Flashcards';
  };

  return (
    <AppShell>
      <main className="db-main">
        <div className="db-tab">
          <div className="db-page-header">
            <div>
              <p className="db-greeting-time">{getGreeting()}</p>
              <h1>{user?.display_name || user?.username} 👋</h1>
              <p>Here's your learning summary for today.</p>
            </div>
            {!loadingStats && stats.studyStreak > 0 && (
              <div className="db-streak-badge">
                <span className="db-streak-fire">🔥</span>
                <div>
                  <strong>{stats.studyStreak}</strong>
                  <span>day streak</span>
                </div>
              </div>
            )}
          </div>

          <div className="db-stats-grid">
            {statCards.map(({ icon, label, value, variant }) => (
              <div className={`db-stat-card db-stat-card--${variant}`} key={label}>
                <div className="db-stat-icon"><FontAwesomeIcon icon={icon} /></div>
                <div className="db-stat-body">
                  <p>{label}</p>
                  <h3>{loadingStats ? '—' : value}</h3>
                </div>
              </div>
            ))}
          </div>

          {!loadingStats && clashStats.totalClashes > 0 && (
            <div className="db-clash-strip">
              <div className="db-clash-strip-label">
                <FontAwesomeIcon icon={faBolt} />
                <span>Clash Performance</span>
              </div>
              <div className="db-clash-strip-stats">
                <div className="db-clash-strip-stat">
                  <strong>{clashStats.totalClashes}</strong>
                  <span>Played</span>
                </div>
                <div className="db-clash-strip-divider" />
                <div className="db-clash-strip-stat">
                  <strong>{clashStats.clashWins}</strong>
                  <span>Wins</span>
                </div>
                <div className="db-clash-strip-divider" />
                <div className="db-clash-strip-stat">
                  <strong>{clashStats.bestRank != null ? `#${clashStats.bestRank}` : '—'}</strong>
                  <span>Best Rank</span>
                </div>
              </div>
              <button className="db-btn db-btn-ghost db-btn-sm" onClick={() => navigate('/clash/history')}>
                View History
              </button>
            </div>
          )}

          <div className="db-lower-grid">
            {/* Left column: Quick Actions + Weak Areas */}
            <div className="db-lower-left">
              <div className="db-card">
                <div className="db-card-header"><h2>Quick Actions</h2></div>
                <div className="db-actions-grid">
                  {quickActions.map(({ icon, title, desc, path, variant }) => (
                    <button className={`db-action-card db-action-card--${variant}`} key={title} onClick={() => navigate(path)}>
                      <div className="db-action-icon"><FontAwesomeIcon icon={icon} /></div>
                      <h3>{title}</h3>
                      <p>{desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {!loadingStats && weakAreas.length > 0 && (
                <div className="db-card">
                  <div className="db-card-header">
                    <h2>Weak Areas</h2>
                    <span style={{ fontSize: 13, color: 'var(--text-muted, #888)' }}>Topics to focus on</span>
                  </div>
                  <div className="db-activity-list">
                    {weakAreas.map((area) => (
                      <div className="db-activity-item" key={area.topic}>
                        <div
                          className="db-activity-dot"
                          style={{
                            background: area.accuracy < 50 ? 'rgba(239,68,68,0.15)' : 'rgba(234,179,8,0.15)',
                            color: area.accuracy < 50 ? '#ef4444' : '#eab308',
                          }}
                        >
                          <FontAwesomeIcon icon={faBook} />
                        </div>
                        <div className="db-activity-body">
                          <p>{area.topic}</p>
                          <span>{area.total_questions} questions · {area.accuracy}% accuracy</span>
                        </div>
                        <button
                          className="db-btn db-btn-primary"
                          style={{ padding: '5px 12px', fontSize: 12, flexShrink: 0 }}
                          onClick={() => navigate(`/quiz/create?subject=${encodeURIComponent(area.topic)}`)}
                        >
                          Practice
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Right column: Recent Activity */}
            <div className="db-lower-right">
              <div className="db-card">
                <div className="db-card-header"><h2>Recent Activity</h2></div>
                {loadingStats ? (
                  <div className="db-empty"><p>Loading activity…</p></div>
                ) : recentActivity.length === 0 ? (
                  <div className="db-empty">
                    <div className="db-empty-icon">📋</div>
                    <p>No activity yet. Create a quiz or flashcard deck to get started!</p>
                    <button className="db-btn db-btn-primary" onClick={() => navigate('/quiz/create')}>
                      Create Quiz
                    </button>
                  </div>
                ) : (
                  <div className="db-activity-list">
                    {recentActivity.slice(0, 8).map((item) => (
                      <div className="db-activity-item" key={item.id}>
                        <div className={`db-activity-dot db-activity-dot--${item.type}`}>
                          <FontAwesomeIcon icon={activityIcon(item.type)} />
                        </div>
                        <div className="db-activity-body">
                          <p>{item.title}</p>
                          <span>
                            {activityLabel(item.type)}
                            {item.subtitle ? ` · ${item.subtitle}` : ''}
                            {' · '}
                            {new Date(item.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        {item.type === 'quiz' && item.score != null && (
                          <span className="db-activity-score">{item.score}%</span>
                        )}
                        {item.type === 'clash' && item.rank != null && (
                          <div style={{ textAlign: 'right', flexShrink: 0 }}>
                            <div className="db-activity-score" style={{ display: 'block' }}>
                              #{item.rank} of {item.player_count}
                            </div>
                            <div style={{ fontSize: '0.75em', color: 'var(--text-secondary)', marginTop: '2px' }}>
                              {item.score.toLocaleString()} pts
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </AppShell>
  );
};

export default Dashboard;