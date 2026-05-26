import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import Navbar from '../../components/Navbar';
import AppShell from '../../components/AppShell/AppShell';
import './Chatbot.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faSpinner,
    faTimesCircle,
    faFolder,
    faPaperPlane,
    faCopy,
    faCheck,
    faAngleDoubleLeft,
    faArrowDown,
    faPlay,
} from '@fortawesome/free-solid-svg-icons';
import djangoApi from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import RichTextRenderer, { normalizeRichTextContent } from '../../utils/richTextRenderer';

let messageIdCounter = Date.now();

// ── Inline quiz card components ────────────────────────────────────────────

const QuizFormCard = ({ prefillTopic = '', onGenerate, isGenerating }) => {
    const [topic, setTopic] = useState(prefillTopic);
    const [numQ, setNumQ] = useState(10);
    const [timeLimit, setTimeLimit] = useState(15);

    return (
        <div className="quiz-form-card">
            <p className="quiz-form-title">Set up your quiz</p>
            <div className="quiz-form-field">
                <label htmlFor="qfc-topic">Topic</label>
                <input
                    id="qfc-topic"
                    type="text"
                    value={topic}
                    onChange={e => setTopic(e.target.value)}
                    placeholder="e.g. Thermodynamics"
                    disabled={isGenerating}
                />
            </div>
            <div className="quiz-form-row">
                <div className="quiz-form-field">
                    <label htmlFor="qfc-numq">Questions</label>
                    <select id="qfc-numq" value={numQ} onChange={e => setNumQ(Number(e.target.value))} disabled={isGenerating}>
                        {[5, 10, 15, 20].map(n => <option key={n} value={n}>{n}</option>)}
                    </select>
                </div>
                <div className="quiz-form-field">
                    <label htmlFor="qfc-time">Time limit (min)</label>
                    <select id="qfc-time" value={timeLimit} onChange={e => setTimeLimit(Number(e.target.value))} disabled={isGenerating}>
                        {[5, 10, 15, 20, 30].map(n => <option key={n} value={n}>{n}</option>)}
                    </select>
                </div>
            </div>
            <button
                className="quiz-form-generate-btn"
                onClick={() => onGenerate(topic, numQ, timeLimit)}
                disabled={!topic.trim() || isGenerating}
            >
                {isGenerating
                    ? <><FontAwesomeIcon icon={faSpinner} spin style={{ marginRight: 6 }} />Generating…</>
                    : 'Generate Quiz'}
            </button>
        </div>
    );
};

const StartQuizCard = ({ quizData, onStart }) => (
    <div className="start-quiz-card">
        <p className="start-quiz-label">
            Your <strong>{quizData.subject}</strong> quiz is ready!
            {' '}({quizData.mcq_questions?.length || 0} questions · {quizData.difficulty})
        </p>
        <button className="start-quiz-btn" onClick={onStart}>
            <FontAwesomeIcon icon={faPlay} style={{ marginRight: 6 }} />
            Start Quiz
        </button>
    </div>
);

const MessageBubble = ({
    message,
    copiedId,
    onCopy,
    onQuizGenerate,
    quizFormGenerating,
    onStartQuiz,
}) => {
    const isAI = message.type === 'ai';

    if (message.type === 'quiz_form') {
        return (
            <div className="message-row ai-row">
                <div className="ai-avatar-wrap">
                    <img src="/assets/lamla_logo.png" alt="AI Tutor" className="ai-avatar-img" />
                </div>
                <div className="message-bubble ai-message">
                    <QuizFormCard
                        prefillTopic={message.prefillTopic || ''}
                        onGenerate={onQuizGenerate}
                        isGenerating={quizFormGenerating}
                    />
                </div>
            </div>
        );
    }

    if (message.type === 'start_quiz') {
        return (
            <div className="message-row ai-row">
                <div className="ai-avatar-wrap">
                    <img src="/assets/lamla_logo.png" alt="AI Tutor" className="ai-avatar-img" />
                </div>
                <div className="message-bubble ai-message">
                    <StartQuizCard
                        quizData={message.quizData}
                        onStart={() => onStartQuiz(message.quizData)}
                    />
                </div>
            </div>
        );
    }

    return (
        <div className={`message-row ${isAI ? 'ai-row' : 'user-row'}`}>
            {isAI && (
                <div className="ai-avatar-wrap">
                    <img src="/assets/lamla_logo.png" alt="AI Tutor" className="ai-avatar-img" />
                </div>
            )}
            <div className={`message-bubble ${message.type}-message`}>
                {message.sender && (
                    <div className="sender-row">
                        <span className="sender-name">{message.sender}</span>
                        {!message.isThinking && (
                            <button
                                className={`copy-btn${copiedId === message.id ? ' copied' : ''}`}
                                title="Copy to clipboard"
                                onClick={() => onCopy(normalizeRichTextContent(message.text), message.id)}
                            >
                                {copiedId === message.id
                                    ? <><FontAwesomeIcon icon={faCheck} size="xs" /> Copied</>
                                    : <FontAwesomeIcon icon={faCopy} size="xs" />}
                            </button>
                        )}
                    </div>
                )}
                {message.attachment && (
                    <div className="message-attachment-chip">
                        <span className="attachment-chip-icon"><FontAwesomeIcon icon={faFolder} /></span>
                        <span className="attachment-chip-name">{message.attachment.name}</span>
                        <span className="attachment-chip-size">{formatFileSize(message.attachment.size)}</span>
                    </div>
                )}
                {message.isThinking ? (
                    <div className="ai-thinking-dots" aria-label="AI is typing">
                        <span /><span /><span />
                    </div>
                ) : (
                    <RichTextRenderer
                        text={message.text}
                        className="message-content"
                        normalizeMath={message.type === 'ai'}
                    />
                )}
            </div>
        </div>
    );
};

const STARTER_PROMPTS = [
    { icon: '📝', text: 'Quiz me on a topic from my weak areas' },
    { icon: '📄', text: 'Summarise my uploaded document' },
    { icon: '💡', text: 'Explain a concept I\'m struggling with' },
    { icon: '🎯', text: 'Help me prepare for my exams' },
];

const QUICK_REPLIES = ['Explain more', 'Give me an example', 'Quiz me on this'];

const formatFileSize = (size) => {
    if (!size || Number.isNaN(size)) return '';
    if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
    return `${(size / 1024 / 1024).toFixed(2)} MB`;
};

const getWelcomeMessage = (user = null) => {
    const name = user?.first_name || user?.username || null;
    const greeting = name ? `Hello, ${name}!` : 'Hello!';
    return {
        id: messageIdCounter++,
        text: `👋 ${greeting} I'm your AI Tutor and personal study assistant. Ask me anything about your materials, or pick a prompt below to get started.`,
        type: 'ai',
        sender: 'AI Tutor',
    };
};

const freshSessionId = () =>
    `chat-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

const QUIZ_MSG_PREFIX = '__QUIZ__:';

const toUiMessage = (msg) => {
    if (msg.content?.startsWith(QUIZ_MSG_PREFIX)) {
        try {
            const quizData = JSON.parse(msg.content.slice(QUIZ_MSG_PREFIX.length));
            return { id: msg.id || messageIdCounter++, type: 'start_quiz', quizData, text: '', sender: 'AI Tutor' };
        } catch { /* fall through to normal message */ }
    }
    return {
        id: msg.id || messageIdCounter++,
        text: msg.content || '',
        type: msg.sender === 'user' ? 'user' : 'ai',
        sender: msg.sender === 'ai' ? 'AI Tutor' : null,
    };
};

const Chatbot = ({ user: userProp }) => {
    const { user: authUser } = useAuth();
    const user = userProp ?? authUser;
    const isAuthenticated = Boolean(user || localStorage.getItem('auth_token'));
    const navigate = useNavigate();

    const [messageInput, setMessageInput]         = useState('');
    const [attachedFile, setAttachedFile]         = useState(null);
    const [isSocratic, setIsSocratic]             = useState(false);
    const [isProcessing, setIsProcessing]         = useState(false);
    const [history, setHistory]                   = useState(() => [getWelcomeMessage(user)]);
    const [copiedId, setCopiedId]                 = useState(null);
    const [authPrompt, setAuthPrompt]             = useState(null); // 'file' | null
    const [fileSizeError, setFileSizeError]       = useState(null);
    const [quizFormGenerating, setQuizFormGenerating] = useState(false);

    const [currentSessionId, setCurrentSessionId]   = useState(freshSessionId);
    const [chatSessions, setChatSessions]           = useState([]);
    const [isSidebarOpen, setIsSidebarOpen]         = useState(
        typeof window !== 'undefined' && window.innerWidth > 768
    );
    const [isLoadingHistory, setIsLoadingHistory]   = useState(false);
    const [showScrollToBottom, setShowScrollToBottom] = useState(false);

    const chatMessagesRef         = useRef(null);
    const textareaRef             = useRef(null);
    const scrollToBottomButtonRef = useRef(null);
    const showScrollToBottomRef   = useRef(false);
    const visibilityRafRef        = useRef(null);
    const didPersonalizeRef       = useRef(false);

    // ── Scroll helpers ─────────────────────────────────────────────
    const scrollToBottom = () => {
        const container = chatMessagesRef.current;
        if (container && container.scrollHeight > container.clientHeight + 8) {
            container.scrollTop = container.scrollHeight;
        } else {
            const scroller = document.scrollingElement || document.documentElement;
            window.scrollTo({ top: scroller.scrollHeight, behavior: 'smooth' });
        }
        showScrollToBottomRef.current = false;
        setShowScrollToBottom(false);
    };

    const updateScrollVisibility = useCallback(() => {
        const container = chatMessagesRef.current;
        const hasContainerScroll = Boolean(container && container.scrollHeight > container.clientHeight + 8);
        let dist = 0;
        if (hasContainerScroll && container) {
            dist = container.scrollHeight - container.scrollTop - container.clientHeight;
        } else {
            const scroller = document.scrollingElement || document.documentElement;
            dist = scroller.scrollHeight - scroller.scrollTop - window.innerHeight;
        }
        const shouldShow = showScrollToBottomRef.current ? dist > 12 : dist > 48;
        if (shouldShow !== showScrollToBottomRef.current) {
            showScrollToBottomRef.current = shouldShow;
            setShowScrollToBottom(shouldShow);
        }
    }, []);

    const scheduleScrollVisibility = useCallback(() => {
        if (visibilityRafRef.current !== null) return;
        visibilityRafRef.current = window.requestAnimationFrame(() => {
            visibilityRafRef.current = null;
            updateScrollVisibility();
        });
    }, [updateScrollVisibility]);

    // ── File helpers ───────────────────────────────────────────────
    const clearAttachment = () => {
        setAttachedFile(null);
        const fi = document.getElementById('file-input');
        if (fi) fi.value = '';
    };

    // ── Session management ─────────────────────────────────────────
    const fetchChatHistory = useCallback(async () => {
        if (!localStorage.getItem('auth_token')) return;
        try {
            setIsLoadingHistory(true);
            const response = await djangoApi.get('/chatbot/history/');
            if (response.data?.history) {
                setChatSessions(response.data.history);
            }
        } catch (err) {
            console.error('Failed to fetch chat history:', err);
        } finally {
            setIsLoadingHistory(false);
        }
    }, []);

    const loadSessionMessages = async (sessionId) => {
        try {
            setHistory([{ id: messageIdCounter++, text: 'Loading past messages…', type: 'ai', sender: 'AI Tutor' }]);
            const res = await djangoApi.get('/chat/history/', { params: { session_id: sessionId } });
            const messages = Array.isArray(res?.data?.messages) ? res.data.messages : [];
            // toUiMessage detects __QUIZ__: messages and returns start_quiz type automatically
            setHistory(messages.length === 0 ? [getWelcomeMessage(user)] : messages.map(toUiMessage));
        } catch (err) {
            console.error('Failed to load session:', err);
            setHistory([{ id: messageIdCounter++, text: '[Error: Failed to load conversation.]', type: 'ai', sender: 'AI Tutor' }]);
        }
    };

    const handleNewChat = () => {
        setCurrentSessionId(freshSessionId());
        setHistory([getWelcomeMessage(user)]);
        setMessageInput('');
        clearAttachment();
        setAuthPrompt(null);
    };

    const handleSwitchSession = async (sessionId) => {
        setCurrentSessionId(sessionId);
        await loadSessionMessages(sessionId);
    };

    const handleDeleteSession = async (sessionId) => {
        try {
            await djangoApi.delete('/chat/history/clear/', { params: { session_id: sessionId } });
            setChatSessions((prev) => {
                const remaining = prev.filter((s) => (s.session_id || s.id) !== sessionId);
                if (currentSessionId === sessionId) {
                    if (remaining.length > 0) {
                        const nextId = remaining[0].session_id || remaining[0].id;
                        setCurrentSessionId(nextId);
                        loadSessionMessages(nextId);
                    } else {
                        setCurrentSessionId(freshSessionId());
                        setHistory([getWelcomeMessage(user)]);
                    }
                }
                return remaining;
            });
        } catch (err) {
            console.error('Failed to delete session:', err);
        }
    };

    const handleRenameSession = async (sessionId, title) => {
        try {
            const res = await djangoApi.post('/chat/history/rename/', { session_id: sessionId, title });
            const updated = res?.data?.title || title;
            setChatSessions((prev) =>
                prev.map((s) => (s.session_id || s.id) === sessionId ? { ...s, title: updated } : s)
            );
        } catch (err) {
            console.error('Failed to rename session:', err);
        }
    };

    // ── Messaging ──────────────────────────────────────────────────
    const addMessage = (text, type, sender = null, extra = {}) => {
        const msg = { id: messageIdCounter++, text, type, sender, ...extra };
        setHistory(prev => [...prev, msg]);
        return msg;
    };

    const handleQuizFormGenerate = async (topic, numQ, timeLimit) => {
        if (!topic.trim() || quizFormGenerating) return;
        setQuizFormGenerating(true);
        try {
            const res = await djangoApi.post('/quiz/create-from-agent/', {
                topic,
                num_questions: numQ,
                time_limit: timeLimit,
                session_id: currentSessionId,
            });
            const quizData = res.data?.quiz_data;
            if (!quizData) throw new Error('No quiz data returned');

            // Replace quiz_form card with start_quiz card
            setHistory(prev => {
                const idx = prev.findLastIndex(m => m.type === 'quiz_form');
                if (idx === -1) {
                    return [...prev, { id: messageIdCounter++, type: 'start_quiz', quizData, text: '', sender: 'AI Tutor' }];
                }
                const next = [...prev];
                next[idx] = { ...next[idx], type: 'start_quiz', quizData };
                return next;
            });
        } catch (err) {
            console.error('Quiz generation failed:', err);
            const msg = err.response?.data?.error || 'Could not generate quiz. Please try again.';
            alert(msg);
        } finally {
            setQuizFormGenerating(false);
        }
    };

    const handleStartQuiz = (quizData) => {
        navigate('/quiz/play', { state: { quizData } });
    };

    // Client-side typewriter: animates fullText into message with placeholderId
    const runTypewriter = useCallback((fullText, placeholderId) => {
        let i = 0;
        const CHARS_PER_FRAME = 40;
        const step = () => {
            if (i >= fullText.length) {
                scrollToBottom();
                return;
            }
            i = Math.min(i + CHARS_PER_FRAME, fullText.length);
            setHistory(prev => prev.map(m =>
                m.id === placeholderId ? { ...m, text: fullText.slice(0, i), isThinking: false } : m
            ));
            requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const handleSendMessage = useCallback(async (e) => {
        if (e) e.preventDefault();
        let text = messageInput.trim();
        const fileToSend = attachedFile;
        const isTextPresent = text.length > 0;
        if ((!isTextPresent && !fileToSend) || isProcessing) return;
        if (!isTextPresent && fileToSend) text = 'Analyze the uploaded document and summarize its key concepts.';

        addMessage(text, 'user', null, fileToSend ? { attachment: { name: fileToSend.name, size: fileToSend.size } } : {});
        setMessageInput('');
        clearAttachment();

        const placeholder = addMessage('', 'ai', 'AI Tutor', { isThinking: true });
        const placeholderId = placeholder.id;
        setIsProcessing(true);

        const tutor_mode = isSocratic ? 'socratic' : 'direct';

        try {
            if (fileToSend) {
                const form = new FormData();
                form.append('file_upload', fileToSend);
                form.append('message', text);
                form.append('tutor_mode', tutor_mode);
                form.append('session_id', currentSessionId);
                const token = localStorage.getItem('auth_token');
                const baseUrl = djangoApi.defaults.baseURL.replace(/\/+$/, '');
                const fileRes = await fetch(`${baseUrl}/chat/file/`, {
                    method: 'POST',
                    headers: token ? { Authorization: `Token ${token}` } : {},
                    credentials: 'include',
                    body: form,
                });
                if (!fileRes.ok) {
                    const errData = await fileRes.json().catch(() => ({}));
                    throw new Error(errData.error || `Upload failed (${fileRes.status})`);
                }
                const data = await fileRes.json();
                const aiText = data.response || '[Error: Empty response from file API]';
                if (data.session_id && data.session_id !== currentSessionId) setCurrentSessionId(data.session_id);
                setIsProcessing(false);
                runTypewriter(aiText, placeholderId);
            } else {
                const res = await djangoApi.post('/chat/', {
                    message: text,
                    session_id: currentSessionId,
                    tutor_mode,
                });
                const aiText = res.data?.response || '[Error: Empty response]';
                const chatAction = res.data?.action;
                const chatPrefill = res.data?.prefill;
                if (res.data?.session_id && res.data.session_id !== currentSessionId) {
                    setCurrentSessionId(res.data.session_id);
                    fetchChatHistory(); // refresh sidebar when a new backend session is assigned
                }
                setIsProcessing(false);
                runTypewriter(aiText, placeholderId);
                if (chatAction === 'show_quiz_form') {
                    addMessage('', 'quiz_form', 'AI Tutor', { prefillTopic: chatPrefill?.topic || '' });
                }
            }
        } catch (err) {
            console.error('API Error:', err);
            const msg = err.response?.data?.detail || err.response?.data?.error || err.message || 'An unknown error occurred.';
            setHistory(prev => prev.map(m => m.id === placeholderId ? { ...m, text: `[Error: ${msg}]`, isThinking: false } : m));
            setIsProcessing(false);
            scrollToBottom();
        }
    }, [messageInput, attachedFile, isSocratic, isProcessing, currentSessionId, runTypewriter]);

    const copyToClipboard = (text, id) => {
        navigator.clipboard.writeText(text)
            .then(() => { setCopiedId(id); setTimeout(() => setCopiedId(null), 2000); })
            .catch(err => console.error('Failed to copy:', err));
    };

    // ── Effects ────────────────────────────────────────────────────
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [messageInput]);

    useEffect(() => { scrollToBottom(); }, [history]);
    useEffect(() => { scheduleScrollVisibility(); }, [history, scheduleScrollVisibility]);

    useEffect(() => {
        showScrollToBottomRef.current = showScrollToBottom;
        if (!showScrollToBottom && scrollToBottomButtonRef.current === document.activeElement) {
            scrollToBottomButtonRef.current.blur();
        }
    }, [showScrollToBottom]);

    useEffect(() => {
        const onResize = () => scheduleScrollVisibility();
        const onScroll = () => scheduleScrollVisibility();
        window.addEventListener('resize', onResize);
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => { window.removeEventListener('resize', onResize); window.removeEventListener('scroll', onScroll); };
    }, [scheduleScrollVisibility]);

    useEffect(() => () => { if (visibilityRafRef.current) window.cancelAnimationFrame(visibilityRafRef.current); }, []);
    useEffect(() => { fetchChatHistory(); }, [fetchChatHistory]);

    useEffect(() => {
        if (!user || didPersonalizeRef.current) return;
        didPersonalizeRef.current = true;
        setHistory(prev => {
            if (prev.length === 1 && prev[0].type === 'ai' && !prev[0].isThinking) {
                return [getWelcomeMessage(user)];
            }
            return prev;
        });
    }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        if (!authPrompt) return;
        const t = setTimeout(() => setAuthPrompt(null), 5000);
        return () => clearTimeout(t);
    }, [authPrompt]);

    // ── Computed ───────────────────────────────────────────────────
    const isReadyToSend    = messageInput.trim().length > 0 || attachedFile;
    const shouldBeDisabled = !isReadyToSend || isProcessing;
    const isWelcomeState   = history.length === 1 && history[0].type === 'ai' && !history[0].isThinking;
    const lastMsg          = history[history.length - 1];
    const showQuickReplies = !isProcessing && lastMsg?.type === 'ai' && history.length > 1 && !lastMsg?.isThinking;

    const scrollBtnStyle = {
        opacity: showScrollToBottom ? 1 : 0,
        transform: showScrollToBottom ? 'translateY(0)' : 'translateY(8px)',
        pointerEvents: showScrollToBottom ? 'auto' : 'none',
    };

    // ── Render ─────────────────────────────────────────────────────
    const chatBody = (
        <div className="chat-wrapper">
            {quizFormGenerating && (
                <div className="quiz-gen-overlay" role="status" aria-live="polite">
                    <div className="quiz-gen-card">
                        <div className="quiz-gen-spinner" aria-hidden="true" />
                        <p>Generating your quiz with AI…</p>
                    </div>
                </div>
            )}
            <Sidebar
                sessions={chatSessions}
                currentSessionId={currentSessionId}
                onNewChat={handleNewChat}
                onSwitchSession={handleSwitchSession}
                onDeleteSession={handleDeleteSession}
                onRenameSession={handleRenameSession}
                isOpen={isSidebarOpen}
                onToggleSidebar={() => setIsSidebarOpen(v => !v)}
                isLoading={isLoadingHistory}
                user={user}
                isAuthenticated={isAuthenticated}
            />

            <div className="chat-main">
                <div className="chat-container">

                    {/* ── Header ── */}
                    <div className="chat-header">
                        <button
                            className="sidebar-collapse-btn"
                            onClick={() => setIsSidebarOpen(v => !v)}
                            title={isSidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
                            aria-label="Toggle sidebar"
                        >
                            <FontAwesomeIcon icon={faAngleDoubleLeft} />
                        </button>
                        <h1>AI Tutor</h1>
                    </div>

                    {/* ── Messages ── */}
                    <div id="chat-messages" ref={chatMessagesRef} onScroll={scheduleScrollVisibility}>
                        {history.map(msg => (
                            <MessageBubble
                                key={msg.id}
                                message={msg}
                                copiedId={copiedId}
                                onCopy={copyToClipboard}
                                onQuizGenerate={handleQuizFormGenerate}
                                quizFormGenerating={quizFormGenerating}
                                onStartQuiz={handleStartQuiz}
                            />
                        ))}

                        {isWelcomeState && (
                            <div className="starter-prompts">
                                <p className="starter-prompts-label">Try asking</p>
                                <div className="starter-prompts-grid">
                                    {STARTER_PROMPTS.map(({ icon, text }) => (
                                        <button
                                            key={text}
                                            className="starter-prompt-chip"
                                            onClick={() => { setMessageInput(text); textareaRef.current?.focus(); }}
                                        >
                                            <span className="starter-prompt-icon">{icon}</span>
                                            <span>{text}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {showQuickReplies && (
                            <div className="quick-replies">
                                {QUICK_REPLIES.map(reply => (
                                    <button
                                        key={reply}
                                        className="quick-reply-chip"
                                        onClick={() => { setMessageInput(reply); textareaRef.current?.focus(); }}
                                    >
                                        {reply}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* ── Scroll-to-bottom ── */}
                    <button
                        ref={scrollToBottomButtonRef}
                        type="button"
                        className="scroll-to-bottom-btn"
                        style={scrollBtnStyle}
                        onClick={scrollToBottom}
                        title="Go to latest message"
                        aria-label="Go to latest message"
                        tabIndex={showScrollToBottom ? 0 : -1}
                    >
                        <FontAwesomeIcon icon={faArrowDown} />
                    </button>

                    {/* ── File attachment bar ── */}
                    {attachedFile && (
                        <div className="file-status-bar">
                            <div className="file-meta-wrap">
                                <span className="file-meta-icon"><FontAwesomeIcon icon={faFolder} /></span>
                                <div className="file-meta-text">
                                    <span className="truncate">{attachedFile.name}</span>
                                    <span className="file-size-display">{formatFileSize(attachedFile.size)}</span>
                                </div>
                                <span className="file-ready-badge">Ready</span>
                            </div>
                            <button className="file-clear-btn" title="Remove attachment" onClick={clearAttachment} disabled={isProcessing}>
                                <FontAwesomeIcon icon={faTimesCircle} />
                            </button>
                        </div>
                    )}

                    {/* ── File size error ── */}
                    {fileSizeError && (
                        <div className="file-size-error">⚠ {fileSizeError}</div>
                    )}

                    {/* ── Auth gate ── */}
                    {authPrompt && (
                        <div className="auth-gate-banner">
                            <span className="auth-gate-text">
                                🔒 <strong>File uploads</strong> require a free account
                            </span>
                            <Link to="/auth/signup" className="auth-gate-cta">Sign Up Free</Link>
                            <button className="auth-gate-close" onClick={() => setAuthPrompt(null)} aria-label="Dismiss">✕</button>
                        </div>
                    )}

                    {/* ── Input area ── */}
                    <div className="chat-input-area">
                        <div className="chat-input-card">
                            <textarea
                                ref={textareaRef}
                                id="message-input"
                                placeholder="Ask me anything about your studies…"
                                rows="1"
                                value={messageInput}
                                onChange={e => setMessageInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSendMessage(e);
                                    }
                                }}
                                disabled={isProcessing}
                            />
                            <div className="chat-input-toolbar">
                                <div className="chat-input-tools-left">
                                    <label
                                        htmlFor={isAuthenticated ? "file-input" : undefined}
                                        className="tool-btn"
                                        title={isAuthenticated ? "Attach file (PDF, DOCX, PPTX, TXT)" : "Sign up to attach files"}
                                        onClick={!isAuthenticated ? () => setAuthPrompt('file') : undefined}
                                    >
                                        <FontAwesomeIcon icon={faFolder} />
                                        {isAuthenticated && (
                                            <input
                                                type="file"
                                                id="file-input"
                                                accept=".pdf,.docx,.pptx,.txt"
                                                onChange={(e) => {
                                                    const file = e.target.files[0];
                                                    if (!file) { clearAttachment(); return; }
                                                    if (file.size > 10 * 1024 * 1024) {
                                                        setFileSizeError(`${file.name} exceeds the 10 MB limit.`);
                                                        setTimeout(() => setFileSizeError(null), 4000);
                                                        e.target.value = '';
                                                        return;
                                                    }
                                                    setAttachedFile(file);
                                                }}
                                                disabled={isProcessing}
                                            />
                                        )}
                                    </label>
                                    <div className="search-mode-pills">
                                        <button
                                            type="button"
                                            className={`search-pill${isSocratic ? ' active' : ''}`}
                                            onClick={() => setIsSocratic(v => !v)}
                                            title={isSocratic
                                                ? 'Socratic mode on — guiding you through questions. Click to switch to direct answers.'
                                                : 'Enable Socratic mode — learn through guided questions instead of direct answers'}
                                            disabled={isProcessing}
                                        >
                                            {isSocratic ? '🧠 Socratic' : 'Socratic'}
                                        </button>
                                    </div>
                                </div>
                                <button
                                    id="send-btn"
                                    type="button"
                                    title="Send message (Enter)"
                                    disabled={shouldBeDisabled}
                                    onClick={handleSendMessage}
                                >
                                    <FontAwesomeIcon icon={isProcessing ? faSpinner : faPaperPlane} spin={isProcessing} />
                                </button>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );

    return isAuthenticated
        ? <AppShell showSidebar={false}>{chatBody}</AppShell>
        : <><Navbar />{chatBody}</>;
};

export default Chatbot;
