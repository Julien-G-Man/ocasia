import React, { useState, useRef, useEffect, useCallback } from 'react';
import Sidebar from './Sidebar';
import Navbar from '../../components/Navbar';
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
} from '@fortawesome/free-solid-svg-icons';
import djangoApi from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import RichTextRenderer, { normalizeRichTextContent } from '../../utils/richTextRenderer';

let messageIdCounter = Date.now();

const STARTER_PROMPTS = [
    { icon: '📝', text: 'Quiz me on a topic from my notes' },
    { icon: '📄', text: 'Summarise my uploaded document' },
    { icon: '💡', text: 'Explain a concept I\'m struggling with' },
    { icon: '🎯', text: 'Help me prepare for my exams' },
];

const QUICK_REPLIES = ['Explain more', 'Give me an example', 'Quiz me on this'];

const SEARCH_MODES = [
    { value: 'disabled',      label: 'AI Only' },
    { value: 'web_search',    label: '🌐 Web'  },
    { value: 'deep_research', label: '🔬 Deep' },
];

const formatFileSize = (size) => {
    if (!size || Number.isNaN(size)) return '';
    if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
    return `${(size / 1024 / 1024).toFixed(2)} MB`;
};

const getWelcomeMessage = () => ({
    id: messageIdCounter++,
    text: "👋 Hello! I'm your AI Tutor and personal study assistant. Ask me anything about your materials, or pick a prompt below to get started.",
    type: 'ai',
    sender: 'AI Tutor',
});

const toUiMessage = (msg) => ({
    id: msg.id || messageIdCounter++,
    text: msg.content || '',
    type: msg.sender === 'user' ? 'user' : 'ai',
    sender: msg.sender === 'ai' ? 'AI Tutor' : null,
});

const Chatbot = ({ user: userProp }) => {
    const { user: authUser } = useAuth();
    const user = userProp ?? authUser;
    const isAuthenticated = Boolean(user || localStorage.getItem('auth_token'));

    const [messageInput, setMessageInput]       = useState('');
    const [attachedFile, setAttachedFile]       = useState(null);
    const [currentSearchMode, setCurrentSearchMode] = useState('disabled');
    const [isProcessing, setIsProcessing]       = useState(false);
    const [history, setHistory]                 = useState([getWelcomeMessage()]);
    const [copiedId, setCopiedId]               = useState(null);

    // Session state
    const [currentSessionId, setCurrentSessionId]   = useState(null);
    const [chatSessions, setChatSessions]           = useState([]);
    const [isSidebarOpen, setIsSidebarOpen]         = useState(
        typeof window !== 'undefined' && window.innerWidth > 768
    );
    const [isLoadingHistory, setIsLoadingHistory]   = useState(false);
    const [showScrollToBottom, setShowScrollToBottom] = useState(false);

    const chatMessagesRef          = useRef(null);
    const textareaRef              = useRef(null);
    const scrollToBottomButtonRef  = useRef(null);
    const showScrollToBottomRef    = useRef(false);
    const visibilityRafRef         = useRef(null);

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
                if (response.data.history.length > 0) {
                    const first = response.data.history[0];
                    const id = first.session_id || first.id;
                    setCurrentSessionId(id);
                    await loadSessionMessages(id);
                }
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
            setHistory(messages.length === 0 ? [getWelcomeMessage()] : messages.map(toUiMessage));
        } catch (err) {
            console.error('Failed to load session:', err);
            setHistory([{ id: messageIdCounter++, text: '[Error: Failed to load conversation.]', type: 'ai', sender: 'AI Tutor' }]);
        }
    };

    const handleNewChat = () => {
        const newId = 'chat-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        setCurrentSessionId(newId);
        setHistory([getWelcomeMessage()]);
        setMessageInput('');
        clearAttachment();
    };

    const handleSwitchSession = async (sessionId) => {
        setCurrentSessionId(sessionId);
        await loadSessionMessages(sessionId);
    };

    const handleDeleteSession = async (sessionId) => {
        try {
            await djangoApi.delete('/chat/history/', { params: { session_id: sessionId } });
            setChatSessions((prev) => {
                const remaining = prev.filter((s) => (s.session_id || s.id) !== sessionId);
                if (currentSessionId === sessionId) {
                    if (remaining.length > 0) {
                        const nextId = remaining[0].session_id || remaining[0].id;
                        setCurrentSessionId(nextId);
                        loadSessionMessages(nextId);
                    } else {
                        setCurrentSessionId(null);
                        setHistory([getWelcomeMessage()]);
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

        try {
            if (fileToSend) {
                const form = new FormData();
                form.append('file_upload', fileToSend);
                form.append('message', text);
                form.append('search_mode', currentSearchMode);
                form.append('session_id', currentSessionId);
                const res = await djangoApi.post('chat/file/', form, { headers: { 'Content-Type': 'multipart/form-data' } });
                const aiText = res.data?.response || '[Error: Empty response from file API]';
                if (res.data?.session_id && res.data.session_id !== currentSessionId) setCurrentSessionId(res.data.session_id);
                setHistory(prev => prev.map(m => m.id === placeholderId ? { ...m, text: aiText, isThinking: false } : m));
            } else {
                const baseUrl = djangoApi.defaults.baseURL.replace(/\/+$/, '');
                const token = localStorage.getItem('auth_token');
                const res = await fetch(`${baseUrl}/chat/stream/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) },
                    credentials: 'include',
                    body: JSON.stringify({ message: text, search_mode: currentSearchMode, session_id: currentSessionId, conversation_history: [], context_document: null }),
                });
                if (!res.ok || !res.body) throw new Error(`Stream API error: ${res.status}`);

                const reader = res.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let accumulated = '';
                let frameId = null;
                let pending = '';
                const flush = (force = false) => {
                    if (!force && frameId !== null) return;
                    const run = () => {
                        frameId = null;
                        if (!pending) return;
                        const next = pending; pending = '';
                        setHistory(prev => prev.map(m => m.id === placeholderId ? { ...m, text: next, isThinking: false } : m));
                        scrollToBottom();
                    };
                    force ? run() : (frameId = window.requestAnimationFrame(run));
                };
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    accumulated += decoder.decode(value, { stream: true });
                    pending = accumulated;
                    flush(false);
                }
                flush(true);
            }
        } catch (err) {
            console.error('API Error:', err);
            const msg = err.response?.data?.detail || err.message || 'An unknown error occurred.';
            setHistory(prev => prev.map(m => m.id === placeholderId ? { ...m, text: `[Error: ${msg}]`, isThinking: false } : m));
        } finally {
            setIsProcessing(false);
            scrollToBottom();
        }
    }, [messageInput, attachedFile, currentSearchMode, isProcessing, currentSessionId]);

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

    // ── Computed ───────────────────────────────────────────────────
    const isSearchActive   = currentSearchMode !== 'disabled';
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

    // ── Sub-components ─────────────────────────────────────────────
    const MessageBubble = ({ message }) => {
        const isAI = message.type === 'ai';
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
                                    onClick={() => copyToClipboard(normalizeRichTextContent(message.text), message.id)}
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

    // ── Render ─────────────────────────────────────────────────────
    return (
        <>
        <Navbar user={user} />
        <div className="chat-wrapper">
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
                        {history.map(msg => <MessageBubble key={msg.id} message={msg} />)}

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

                    {/* ── Search indicator ── */}
                    {isProcessing && isSearchActive && (
                        <div className="search-indicator">
                            <FontAwesomeIcon icon={faSpinner} spin />
                            <span>{currentSearchMode === 'deep_research' ? 'Conducting deep research…' : 'Searching the web…'}</span>
                        </div>
                    )}

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
                                    <label htmlFor="file-input" className="tool-btn" title="Attach file (PDF, DOCX, PPTX, TXT)">
                                        <FontAwesomeIcon icon={faFolder} />
                                        <input
                                            type="file"
                                            id="file-input"
                                            accept=".pdf,.docx,.pptx,.txt"
                                            onChange={(e) => {
                                                const file = e.target.files[0];
                                                if (!file) { clearAttachment(); return; }
                                                if (file.size > 10 * 1024 * 1024) {
                                                    alert(`${file.name} is too large. Max 10 MB.`);
                                                    e.target.value = '';
                                                    return;
                                                }
                                                setAttachedFile(file);
                                            }}
                                            disabled={isProcessing}
                                        />
                                    </label>
                                    <div className="search-mode-pills">
                                        {SEARCH_MODES.map(({ value, label }) => (
                                            <button
                                                key={value}
                                                type="button"
                                                className={`search-pill${currentSearchMode === value ? ' active' : ''}`}
                                                onClick={() => setCurrentSearchMode(value)}
                                                disabled={isProcessing}
                                            >
                                                {label}
                                            </button>
                                        ))}
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
        </>
    );
};

export default Chatbot;
