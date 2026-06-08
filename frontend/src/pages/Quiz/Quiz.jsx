import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Navbar from '../../components/Navbar';
import RichTextRenderer from '../../utils/richTextRenderer';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faListUl } from '@fortawesome/free-solid-svg-icons';
import './Quiz.css';
import djangoApi, { DJANGO_HEALTH_ENDPOINT, FASTAPI_HEALTH_ENDPOINT } from '../../services/api';

const pingServers = () => {
    fetch(DJANGO_HEALTH_ENDPOINT).catch(() => {});
    fetch(FASTAPI_HEALTH_ENDPOINT).catch(() => {});
};

const Quiz = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAuthenticated, isLoading } = useAuth();

    const { quizData } = location.state || { quizData: null };
    const REDIRECT_PATH = '/quiz/create';

    const [currentIndex, setCurrentIndex] = useState(0);
    const [userAnswers, setUserAnswers] = useState({});
    const [flaggedQuestions, setFlaggedQuestions] = useState({});
    const [timeRemaining, setTimeRemaining] = useState(0);
    const [timerInitialized, setTimerInitialized] = useState(false);
    const [isTimeHidden, setIsTimeHidden] = useState(false);
    const [isPanelOpen, setIsPanelOpen] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState(null);
    const [timeUpBanner, setTimeUpBanner] = useState(false);

    const allQuestions = quizData
        ? [...(quizData.mcq_questions || []), ...(quizData.short_questions || [])]
        : [];

    const storageKey = `lamla_quiz_${quizData?.id || 'temp'}`;
    const autoSubmittedRef = useRef(false);
    const initializedRef = useRef(false);

    const submitQuiz = useCallback(async () => {
        if (isSubmitting) return;
        setIsSubmitting(true);
        try {
            const response = await djangoApi.post('/quiz/submit/', {
                quiz_id: quizData.id,
                quiz_data: quizData,
                user_answers: userAnswers,
                total_questions: allQuestions.length,
            });
            localStorage.removeItem(storageKey);
            navigate('/quiz/results', { state: { results: response.data } });
        } catch (err) {
            console.error('Submission failed', err);
            setIsSubmitting(false);
            setSubmitError(err.response?.data?.error || 'Failed to submit quiz. Please check your connection.');
        }
    }, [isSubmitting, quizData, userAnswers, allQuestions.length, storageKey, navigate]);

    useEffect(() => {
        if (!isLoading && !isAuthenticated) navigate('/auth/login');
    }, [isLoading, isAuthenticated, navigate]);

    useEffect(() => {
        if (initializedRef.current) return;

        if (!quizData) {
            navigate(REDIRECT_PATH);
            return;
        }

        initializedRef.current = true;

        const saved = localStorage.getItem(storageKey);
        if (saved) {
            const parsed = JSON.parse(saved);
            setUserAnswers(parsed.userAnswers || {});
            setFlaggedQuestions(parsed.flaggedQuestions || {});
            setCurrentIndex(parsed.currentIndex || 0);
            const remaining = Math.max(0, Math.floor((parsed.endTime - Date.now()) / 1000));
            setTimeRemaining(remaining);
            setTimerInitialized(true);
        } else {
            const timeLimitMinutes = parseInt(quizData.time_limit, 10);
            if (isNaN(timeLimitMinutes) || timeLimitMinutes <= 0) {
                setTimeRemaining(10 * 60);
            } else {
                setTimeRemaining(timeLimitMinutes * 60);
            }
            setTimerInitialized(true);
        }
    }, [quizData, navigate, storageKey]);

    useEffect(() => {
        if (!timerInitialized || timeRemaining === undefined) {
            return;
        }

        const timer = setInterval(() => {
            setTimeRemaining((prev) => Math.max(0, prev - 1));
        }, 1000);

        return () => clearInterval(timer);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [timerInitialized]);

    useEffect(() => {
        if (timerInitialized && timeRemaining <= 0 && !autoSubmittedRef.current && !isSubmitting) {
            autoSubmittedRef.current = true;
            setTimeUpBanner(true);
            submitQuiz();
        }
    }, [timeRemaining, timerInitialized, isSubmitting, submitQuiz]);

    useEffect(() => {
        if (quizData && timerInitialized && timeRemaining > 0) {
            const state = {
                userAnswers,
                flaggedQuestions,
                currentIndex,
                endTime: Date.now() + timeRemaining * 1000,
            };
            localStorage.setItem(storageKey, JSON.stringify(state));
        }
    }, [userAnswers, flaggedQuestions, currentIndex, timeRemaining, storageKey, quizData, timerInitialized]);

    const handleAnswer = (val) => {
        setUserAnswers((prev) => ({ ...prev, [currentIndex]: val }));
    };

    const toggleFlag = () => {
        setFlaggedQuestions((prev) => ({ ...prev, [currentIndex]: !prev[currentIndex] }));
    };

    const formatTime = (seconds) => {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    };

    if (!quizData || allQuestions.length === 0) {
        return null;
    }

    if (!timerInitialized) {
        return (
            <>
                <Navbar brandOnly />
                <div className="quiz-page"><p className="quiz-state-text">Loading quiz...</p></div>
            </>
        );
    }

    if (timeRemaining === undefined || timeRemaining === null || isNaN(timeRemaining)) {
        return (
            <>
                <Navbar brandOnly />
                <div className="quiz-page"><p className="quiz-state-text">Error: Timer initialization failed. Please refresh the page.</p></div>
            </>
        );
    }

    const currentQ = allQuestions[currentIndex];
    const isAnswered = !!userAnswers[currentIndex];
    const hasOptions = Array.isArray(currentQ.options) && currentQ.options.length > 0;
    const timerClass = timeRemaining <= 60 ? 'quiz-timer-pill--danger'
        : timeRemaining <= 300 ? 'quiz-timer-pill--warn'
        : '';

    return (
        <>
            <Navbar brandOnly />
            <div className="quiz-page" onClick={pingServers}>
                <header className="quiz-page-header">
                    <div>
                        <h1>{quizData.subject || 'Quiz'}</h1>
                    </div>
                    <p className="quiz-progress-copy">Question {currentIndex + 1} of {allQuestions.length}</p>
                </header>

                <section className="quiz-top-shell">
                    <div className={`quiz-timer-pill ${timerClass}`}>
                        <span className="quiz-timer-label">Time Left</span>
                        <span className={`quiz-timer-value ${isTimeHidden ? 'invisible' : ''}`}>{formatTime(timeRemaining)}</span>
                    </div>
                    <button className="quiz-hide-btn" onClick={() => setIsTimeHidden(!isTimeHidden)}>
                        {isTimeHidden ? 'Show' : 'Hide'}
                    </button>
                </section>

                <section className="quiz-meta-shell">
                    <div className="quiz-meta-row">
                        <h2 className="quiz-meta-title">Question {currentIndex + 1}</h2>
                        <p className="quiz-meta-status">{isAnswered ? 'Answered' : 'Not yet answered'}</p>
                    </div>
                    <button className={`quiz-flag-link ${flaggedQuestions[currentIndex] ? 'active' : ''}`} onClick={toggleFlag}>
                        {flaggedQuestions[currentIndex] ? 'Unflag question' : 'Flag question'}
                    </button>
                </section>

                <section className="quiz-question-shell">
                    <div className="quiz-question-body">
                        <RichTextRenderer text={currentQ.question} className="quiz-rich-text" />
                    </div>

                    {hasOptions ? (
                        <div className="quiz-options-list" role="radiogroup" aria-label="Answer choices">
                            {currentQ.options.map((opt, idx) => {
                                const letter = String.fromCharCode(65 + idx);
                                const checked = userAnswers[currentIndex] === letter;
                                return (
                                    <button
                                        key={idx}
                                        type="button"
                                        className={`quiz-option-row ${checked ? 'selected' : ''}`}
                                        onClick={() => handleAnswer(letter)}
                                    >
                                        <span className="quiz-option-dot" aria-hidden="true" />
                                        <span className="quiz-option-letter" aria-hidden="true">{letter}.</span>
                                        <div className="quiz-option-text">
                                            <RichTextRenderer text={opt} className="quiz-rich-text quiz-option-rich-text" />
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="quiz-short-answer-wrap">
                            <label className="quiz-short-answer-label" htmlFor="quiz-short-answer">Your answer</label>
                            <input
                                id="quiz-short-answer"
                                type="text"
                                className="quiz-short-answer-input"
                                placeholder="Type your short answer here"
                                value={userAnswers[currentIndex] || ''}
                                onChange={(e) => handleAnswer(e.target.value)}
                            />
                        </div>
                    )}
                </section>

                <section className="quiz-actions-shell">
                    <button
                        className="quiz-btn quiz-btn-muted"
                        disabled={currentIndex === 0}
                        onClick={() => setCurrentIndex((prev) => prev - 1)}
                    >
                        Previous
                    </button>

                    {currentIndex === allQuestions.length - 1 ? (
                        <button className="quiz-btn quiz-btn-primary" onClick={submitQuiz} disabled={isSubmitting}>
                            {isSubmitting ? 'Submitting...' : 'Finish and Submit'}
                        </button>
                    ) : (
                        <button className="quiz-btn quiz-btn-primary" onClick={() => setCurrentIndex((prev) => prev + 1)}>
                            Next
                        </button>
                    )}
                </section>

                {timeUpBanner && (
                    <div className="quiz-timesup-banner">Time's up! Submitting your answers…</div>
                )}
                {submitError && (
                    <div className="quiz-error-banner">{submitError}</div>
                )}

                <button
                    className="quiz-float-toggle"
                    onClick={() => setIsPanelOpen((prev) => !prev)}
                    aria-label={isPanelOpen ? 'Close question navigator' : 'Open question navigator'}
                    aria-expanded={isPanelOpen}
                >
                    <FontAwesomeIcon icon={faListUl} />
                </button>

                <aside className={`quiz-navigator ${isPanelOpen ? 'open' : ''}`}>
                    <div className="quiz-navigator-head">
                        <h3>Questions</h3>
                        <button type="button" className="quiz-navigator-close" onClick={() => setIsPanelOpen(false)} aria-label="Close navigator">
                            ×
                        </button>
                    </div>

                    <div className="quiz-navigator-grid">
                        {allQuestions.map((_, i) => (
                            <button
                                key={i}
                                type="button"
                                className={[
                                    'quiz-nav-cell',
                                    currentIndex === i ? 'current' : '',
                                    userAnswers[i] ? 'answered' : '',
                                    flaggedQuestions[i] ? 'flagged' : '',
                                ].join(' ').trim()}
                                onClick={() => {
                                    setCurrentIndex(i);
                                    setIsPanelOpen(false);
                                }}
                            >
                                {i + 1}
                            </button>
                        ))}
                    </div>

                    <div className="quiz-navigator-footer">
                        <button type="button" className="quiz-navigator-close-btn" onClick={() => setIsPanelOpen(false)}>
                            Close sidebar
                        </button>
                    </div>
                </aside>
            </div>
        </>
    );
};

export default Quiz;
