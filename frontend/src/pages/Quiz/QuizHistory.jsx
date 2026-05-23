import React, { useState, useEffect } from 'react';
import AppShell from '../../components/AppShell/AppShell';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus } from '@fortawesome/free-solid-svg-icons';
import { dashboardService } from '../../services/dashboard';
import '../Dashboards/Dashboard.css';

const QuizHistory = () => {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading } = useAuth();
  const [quizHistory, setQuizHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) navigate('/auth/login');
  }, [isLoading, isAuthenticated, navigate]);

  useEffect(() => {
    if (!isAuthenticated) return;
    dashboardService.getQuizHistory()
      .then(data => setQuizHistory(data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  return (
    <AppShell>
      <main className="db-main">
          <div className="db-tab">
            <div className="db-page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h1>Past Quizzes</h1>
                <p>Review your performance history.</p>
              </div>
              <button className="db-btn db-btn-primary" onClick={() => navigate('/quiz/create')}>
                <FontAwesomeIcon icon={faPlus} style={{ marginRight: 6 }} />
                Take a New Quiz
              </button>
            </div>
            <div className="db-card" style={{ padding: 0, overflow: 'hidden' }}>
              {loading ? (
                <div className="db-empty"><p>Loading…</p></div>
              ) : quizHistory.length === 0 ? (
                <div className="db-empty">
                  <div className="db-empty-icon">📋</div>
                  <p>No quiz history yet.</p>
                  <button className="db-btn db-btn-primary" onClick={() => navigate('/quiz/create')}>
                    Take a Quiz
                  </button>
                </div>
              ) : (
                quizHistory.map((q) => (
                  <div className="db-quiz-row" key={q.id}>
                    <div className="db-quiz-info">
                      <h3>{q.subject}</h3>
                      <p>{q.total_questions} questions · {new Date(q.created_at).toLocaleDateString()}</p>
                    </div>
                    <div className="db-quiz-score">{q.score_percent}%</div>
                    <button className="db-btn db-btn-ghost db-btn-sm">Review</button>
                  </div>
                ))
              )}
            </div>
          </div>
      </main>
    </AppShell>
  );
};

export default QuizHistory;
