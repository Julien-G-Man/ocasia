import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Navbar from '../../components/Navbar';
import Footer from '../../components/Footer';
import RichTextRenderer from '../../utils/richTextRenderer';
import './QuizResults.css';
import djangoApi from '../../services/api';
import { dashboardService } from '../../services/dashboard';

const downloadAsText = (results) => {
    const { score, total, score_percent, details, subject, difficulty } = results;
    const timestamp = new Date().toLocaleString();

    let content = 'QUIZ RESULTS REPORT\n';
    content += `${'='.repeat(60)}\n\n`;
    content += `Subject: ${subject}\n`;
    content += `Difficulty: ${difficulty}\n`;
    content += `Date: ${timestamp}\n`;
    content += `Score: ${score}/${total} (${score_percent.toFixed(1)}%)\n`;
    content += `${'='.repeat(60)}\n\n`;
    content += 'DETAILED ANSWER REVIEW\n';
    content += `${'-'.repeat(60)}\n\n`;

    details.forEach((detail, idx) => {
        content += `Q${idx + 1}. ${detail.question}\n`;
        content += `Your Answer: ${detail.user_answer_display || detail.user_answer || '(Unanswered)'}\n`;
        content += `Correct Answer: ${detail.correct_answer_display || detail.correct_answer}\n`;
        content += `Status: ${detail.is_correct ? 'CORRECT' : 'INCORRECT'}\n`;
        if (detail.reasoning) content += `Evaluation: ${detail.reasoning}\n`;
        if (detail.explanation) content += `Explanation: ${detail.explanation}\n`;
        content += '\n';
    });

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `Quiz_Results_${subject.replace(/\s+/g, '_')}.txt`);
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
};

const downloadAsPDF = async (results) => {
    try {
        const response = await djangoApi.post('/quiz/download/', { results, format: 'pdf' }, { responseType: 'blob' });
        const blob = response.data;
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `Quiz_Results_${results.subject.replace(/\s+/g, '_')}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('PDF download failed:', err);
        alert('Failed to download PDF. Please try TXT or DOCX format.');
    }
};

const downloadAsDOCX = async (results) => {
    try {
        const response = await djangoApi.post('/quiz/download/', { results, format: 'docx' }, { responseType: 'blob' });
        const blob = response.data;
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `Quiz_Results_${results.subject.replace(/\s+/g, '_')}.docx`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('DOCX download failed:', err);
        alert('Failed to download DOCX. Please try TXT or PDF format.');
    }
};

const QuizResults = ({ user }) => {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAuthenticated, isLoading } = useAuth();
    const results = location.state?.results;

    const [rating, setRating] = useState(0);
    const [hoverRating, setHoverRating] = useState(0);
    const [feedbackSent, setFeedbackSent] = useState(false);
    const [feedbackMessage, setFeedbackMessage] = useState('');

    useEffect(() => {
        if (!isLoading && !isAuthenticated) navigate('/auth/login');
    }, [isLoading, isAuthenticated, navigate]);

    useEffect(() => {
        if (!results) navigate('/quiz/create');
    }, [results, navigate]);

    useEffect(() => {
        let mounted = true;

        const loadFeedback = async () => {
            try {
                const data = await dashboardService.getQuizFeedbackSummary('quiz_results');
                if (!mounted) return;

                if (data?.user_rating) {
                    setRating(Number(data.user_rating));
                    setFeedbackSent(true);
                    setFeedbackMessage('Your rating is saved.');
                }
            } catch (err) {
                console.error('Could not load feedback summary:', err);
            }
        };

        loadFeedback();

        return () => {
            mounted = false;
        };
    }, []);

    if (!results) return null;

    const { score, total, score_percent, details, subject } = results;

    const handleCopy = (text, e) => {
        navigator.clipboard.writeText(text);
        const btn = e.currentTarget;
        const originalText = btn.innerText;
        btn.innerText = 'Copied';
        setTimeout(() => {
            btn.innerText = originalText;
        }, 1500);
    };

    const APP_URL = (import.meta.env.VITE_APP_URL || window.location.origin).replace(/\/$/, "");
    const handleShare = () => {
        const shareData = {
            title: 'Ocasia Quiz',
            text: `I scored ${score}/${total} on the ${subject} quiz!`,
            url: APP_URL,
        };

        if (navigator.share) {
            navigator.share(shareData);
        } else {
            navigator.clipboard.writeText(`${shareData.text} ${shareData.url}`);
            alert('Link copied to clipboard.');
        }
    };

    const submitFeedback = async (val) => {
        try {
            const payload = await dashboardService.submitQuizFeedback({
                rating: val,
                source: 'quiz_results',
            });
            setRating(Number(payload?.rating || val));
            setFeedbackSent(true);
            setFeedbackMessage('Thanks. Your rating was saved.');
        } catch (err) {
            console.error('Failed to save feedback:', err);
            setRating(val);
            setFeedbackSent(true);
            setFeedbackMessage('Saved locally. We could not sync right now.');
        }
    };

    return (
        <>
            <Navbar user={user} />
            <div className="results-page">
                <header className="results-page-header">
                    <div>
                        <h1>{subject} Quiz Results</h1>
                    </div>
                    <p className="results-score-pill">{score_percent.toFixed(1)}%</p>
                </header>

                <section className="results-summary-card">
                    <h2>
                        {score_percent >= 80 ? 'Excellent Work' : score_percent >= 50 ? 'Good Effort' : 'Time to Review'}
                    </h2>
                    <p>You completed <strong>{subject}</strong>. Here is your breakdown.</p>

                    <div className="results-metrics-grid">
                        <article className="results-metric">
                            <span>Correct Answers</span>
                            <strong>{score}/{total}</strong>
                        </article>
                        <article className="results-metric">
                            <span>Overall Score</span>
                            <strong>{score_percent.toFixed(1)}%</strong>
                        </article>
                    </div>

                    <div className="results-progress-track">
                        <div className="results-progress-fill" style={{ width: `${score_percent}%` }} />
                    </div>
                </section>

                <section className="results-review-section">
                    <h3>Detailed Answer Review</h3>
                    <div className="results-review-list">
                        {details.map((detail, idx) => (
                            <article
                                key={idx}
                                className={[
                                    'results-review-item',
                                    detail.is_correct ? 'is-correct' : detail.user_answer ? 'is-incorrect' : 'is-unanswered',
                                ].join(' ')}
                            >
                                <div className="results-question-head">
                                    <span className="results-question-label">Q{idx + 1}</span>
                                    <RichTextRenderer text={detail.question} className="results-rich-text results-question-text" />
                                </div>

                                <div className="results-answer-rows">
                                    <div className="results-answer-row">
                                        <span className="label">Your answer</span>
                                        <div className="value">
                                            <RichTextRenderer text={detail.user_answer_display || detail.user_answer || '(Unanswered)'} className="results-rich-text" />
                                        </div>
                                    </div>
                                    <div className="results-answer-row">
                                        <span className="label">Correct answer</span>
                                        <div className="value with-action">
                                            <RichTextRenderer text={detail.correct_answer_display || detail.correct_answer} className="results-rich-text" />
                                            <button
                                                className="results-inline-btn"
                                                onClick={(e) => handleCopy(detail.correct_answer_display || detail.correct_answer, e)}
                                            >
                                                Copy
                                            </button>
                                        </div>
                                    </div>
                                    {detail.reasoning && (
                                        <div className="results-answer-row">
                                            <span className="label">Evaluation</span>
                                            <div className="value"><RichTextRenderer text={detail.reasoning} className="results-rich-text" /></div>
                                        </div>
                                    )}
                                    {detail.explanation && (
                                        <div className="results-answer-row">
                                            <span className="label">Explanation</span>
                                            <div className="value"><RichTextRenderer text={detail.explanation} className="results-rich-text" /></div>
                                        </div>
                                    )}
                                </div>
                            </article>
                        ))}
                    </div>
                </section>

                <section className="results-actions-card">
                    <h3>Rate this quiz experience</h3>
                       <div className="results-rating-section">
                           <div className="results-stars" role="group" aria-label="Rate quiz experience">
                        {[1, 2, 3, 4, 5].map((star) => (
                            <button
                                key={star}
                                type="button"
                                className={`results-star ${(hoverRating || rating) >= star ? 'active' : ''}`}
                                   aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
                                onMouseEnter={() => !feedbackSent && setHoverRating(star)}
                                onMouseLeave={() => setHoverRating(0)}
                                onClick={() => !feedbackSent && submitFeedback(star)}
                                   disabled={feedbackSent}
                            >
                                   ★
                            </button>
                        ))}
                           </div>
                           {feedbackSent && <p className="results-feedback-done">{feedbackMessage || 'Thanks for your feedback!'}</p>}
                    </div>

                    <div className="results-actions-section">
                        <div className="results-actions-row results-actions-row-downloads">
                            <button className="results-action-btn download-btn" onClick={() => downloadAsText(results)}>
                                <span>Download TXT</span>
                            </button>
                            <button className="results-action-btn download-btn" onClick={() => downloadAsPDF(results)}>
                                <span>Download PDF</span>
                            </button>
                            <button className="results-action-btn download-btn" onClick={() => downloadAsDOCX(results)}>
                                <span>Download DOCX</span>
                            </button>
                        </div>

                        <div className="results-actions-row results-actions-row-secondary">
                            <Link to="/quiz/create" className="results-action-btn secondary-btn">
                                Generate New Quiz
                            </Link>
                            <button className="results-action-btn secondary-btn" onClick={handleShare}>
                                <span>Share Results</span>
                            </button>
                        </div>
                    </div>
                </section>

                <section className="results-donate-nudge">
                    <p>Enjoying Ocasia? Help keep it free for every student.</p>
                    <Link to="/donate" className="results-donate-btn">Support Ocasia →</Link>
                </section>
            </div>
            <Footer />
        </>
    );
};

export default QuizResults;
