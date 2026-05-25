import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import AppShell from '../../components/AppShell/AppShell';
import { useAuth } from '../../context/AuthContext';
import djangoApi from '../../services/api';
import './CreateQuiz.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faKeyboard,
    faCloudUploadAlt,
    faListUl,
    faPen,
    faClock,
    faChartLine,
    faSpinner,
    faExclamationCircle,
    faInfoCircle,
    faFilePdf,
    faLink,
    faPlay,
} from '@fortawesome/free-solid-svg-icons';

const CreateQuiz = () => {
    const navigate  = useNavigate();
    const location  = useLocation();
    const { isAuthenticated, isLoading } = useAuth();

    // Pre-fill from Materials "Use for Quiz" navigation or weak-area "Practice" link
    const prefill = location.state || {};
    const searchParams = new URLSearchParams(location.search);
    const subjectParam = searchParams.get('subject') || '';

    // --- State Variables ---
    const [activeTab, setActiveTab]     = useState(prefill.studyText ? 'textContent' : 'fileContent');
    const [subject, setSubject]         = useState(prefill.subject || subjectParam);
    const [customSubject, setCustomSubject] = useState('');
    const [isOtherSelected, setIsOtherSelected] = useState(false);
    const [studyText, setStudyText]     = useState(prefill.studyText || '');
    const [numMcq, setNumMcq]           = useState(7);
    const [numShort, setNumShort]       = useState(3);
    const [quizTime, setQuizTime]       = useState(10);
    const [difficulty, setDifficulty]   = useState('random');

    const [youtubeUrl, setYoutubeUrl]   = useState('');
    const [youtubeLoaded, setYoutubeLoaded] = useState(null); // { title, video_id }

    const [isExtracting, setIsExtracting] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [fileNameDisplay, setFileNameDisplay] = useState('');
    const [sourceFilename, setSourceFilename] = useState(prefill.sourceTitle || '');
    const [errorMessages, setErrorMessages] = useState([]);
    const [toast, setToast] = useState({ message: '', type: '', visible: false });
    const isProcessing = isExtracting || isGenerating;
    const processingMessage = isExtracting
        ? (activeTab === 'youtubeContent' ? 'Fetching YouTube transcript...' : 'Extracting text from file...')
        : 'Generating your quiz with AI...';

    const fileInputRef = useRef(null);

    useEffect(() => {
        if (!isLoading && !isAuthenticated) navigate('/auth/login');
    }, [isLoading, isAuthenticated, navigate]);

    // --- Helpers ---
    const showToast = useCallback((message, type = 'info') => {
        setToast({ message, type, visible: true });
    }, []);

    useEffect(() => {
        if (toast.visible) {
            const timer = setTimeout(() => setToast(prev => ({ ...prev, visible: false })), 5000);
            return () => clearTimeout(timer);
        }
    }, [toast.visible]);

    // Show banner if pre-filled from a material
    useEffect(() => {
        if (prefill.studyText && prefill.sourceTitle) {
            showToast(`Loaded: "${prefill.sourceTitle}"`, 'success');
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleSubjectChange = (e) => {
        const val = e.target.value;
        setSubject(val);
        setIsOtherSelected(val === 'Other');
    };

    const handleYoutubeLoad = async () => {
        if (!youtubeUrl.trim()) {
            showToast('Paste a YouTube URL first', 'error');
            return;
        }
        setIsExtracting(true);
        setYoutubeLoaded(null);
        try {
            const response = await djangoApi.post('/quiz/extract-youtube/', { url: youtubeUrl.trim() });
            const { text, title, video_id } = response.data;
            setStudyText(text);
            setSourceFilename(title);
            setYoutubeLoaded({ title, video_id });
            showToast(`Transcript loaded: "${title}"`, 'success');
        } catch (err) {
            showToast(err.response?.data?.error || 'Failed to load transcript', 'error');
        } finally {
            setIsExtracting(false);
        }
    };

    const handleFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const fileName = file.name;
        setSourceFilename(fileName);
        setFileNameDisplay(`Selected: ${fileName} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
        setIsExtracting(true);

        const formData = new FormData();
        formData.append('slide_file', file);

        try {
            const response = await djangoApi.post('/quiz/ajax-extract-text/', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            if (response.data.text) {
                setStudyText(response.data.text);
                setActiveTab('textContent');
                showToast('Text extracted successfully!', 'success');
            }
        } catch {
            showToast('Failed to extract text.', 'error');
        } finally {
            setIsExtracting(false);
        }
    };

    const validateForm = () => {
        const errors = [];
        const finalSubject = isOtherSelected ? customSubject.trim() : subject;
        if (!finalSubject) errors.push('Please select or enter a subject');
        if (activeTab === 'textContent' || activeTab === 'youtubeContent') {
            if (studyText.trim().length < 30) errors.push(
                activeTab === 'youtubeContent'
                    ? 'Please load a YouTube transcript first'
                    : 'Please enter at least 30 characters of text'
            );
            if (studyText.length > 50000) errors.push('Text is too long (max 50,000)');
        } else {
            if (!fileInputRef.current?.files.length) errors.push('Please upload a file');
        }
        if (numMcq <= 0 && numShort <= 0) errors.push('Select at least one question type');
        if (numMcq > 30)  errors.push('Maximum MCQ is 30');
        if (numShort > 10) errors.push('Maximum Short Answer is 10');
        setErrorMessages(errors);
        return errors.length === 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validateForm()) return;

        const finalSubject = isOtherSelected ? customSubject.trim() : subject;
        if (!finalSubject) { setErrorMessages(['Please select a subject']); return; }

        setIsGenerating(true);
        try {
            // Always use the current in-memory filename to avoid stale session values.
            const currentSourceFilename = sourceFilename || prefill.sourceTitle || '';
            
            const sourceType = activeTab === 'youtubeContent' ? 'youtube'
                : activeTab === 'fileContent' ? 'file'
                : 'text';

            const response = await djangoApi.post('/quiz/generate/', {
                subject: finalSubject,
                extractedText: studyText,
                num_mcq: numMcq,
                num_short: numShort,
                quiz_time: quizTime,
                difficulty,
                source_filename: currentSourceFilename,
                source_type: sourceType,
            });
            
            navigate('/quiz/play', { state: { quizData: response.data } });
        } catch (err) {
            showToast(err.response?.data?.error || 'Generation failed', 'error');
            setIsGenerating(false);
        }
    };

    const handleClear = () => {
        if (window.confirm('Clear all fields?')) {
            setSubject(''); setCustomSubject(''); setIsOtherSelected(false);
            setStudyText(''); setFileNameDisplay('');
            setSourceFilename('');
            setYoutubeUrl(''); setYoutubeLoaded(null);
            setNumMcq(7); setNumShort(3); setQuizTime(10);
            setErrorMessages([]);
            if (fileInputRef.current) fileInputRef.current.value = '';
            showToast('Form cleared', 'info');
        }
    };

    return (
        <AppShell>
            {isProcessing && (
                <div className="cq-processing-overlay" role="status" aria-live="polite">
                    <div className="cq-processing-card">
                        <div className="cq-processing-spinner" aria-hidden="true" />
                        <p>{processingMessage}</p>
                    </div>
                </div>
            )}
            <div className="page-wrapper">
                <header className="quiz-create-header">
                    <h1 className="main-page-title">Quiz Mode</h1>
                    <p className="main-page-description">
                        Upload your study material, enter a YouTube video link, or paste text content to create customised quiz questions with AI.
                    </p>
                </header>

                <div className="quiz-card-container">
                    {/* Banner when pre-filled from a material */}
                    {prefill.sourceTitle && (
                        <div className="file-name-display success" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 10 }}>
                            <FontAwesomeIcon icon={faFilePdf} style={{ color: '#e53e3e' }} />
                            Content loaded from: <strong>{prefill.sourceTitle}</strong>
                        </div>
                    )}

                    <form onSubmit={handleSubmit}>

                        {/* Subject */}
                        <div className="subject-section">
                            <label className="subject-label">
                                <span>Subject / Topic</span>
                            </label>
                            <select
                                className="subject-select"
                                value={subject}
                                onChange={handleSubjectChange}
                            >
                                <option value="" disabled>Select a subject or topic</option>
                                <option value="Mathematics">Mathematics</option>
                                <option value="Computer Science">Computer Science</option>
                                <option value="Engineering">Engineering</option>
                                <option value="Biology">Biology</option>
                                <option value="Chemistry">Chemistry</option>
                                <option value="Physics">Physics</option>
                                <option value="English">English</option>
                                <option value="History">History</option>
                                <option value="Geography">Geography</option>
                                <option value="Economics">Economics</option>
                                <option value="Other">Other (type your own)</option>
                            </select>

                            {isOtherSelected && (
                                <div className="custom-subject-container" style={{ marginTop: '12px' }}>
                                    <input
                                        type="text"
                                        className="subject-input"
                                        placeholder="Type subject/topic (e.g. Quantum Mechanics)"
                                        value={customSubject}
                                        onChange={e => setCustomSubject(e.target.value)}
                                        autoFocus
                                    />
                                </div>
                            )}

                            <div className="subject-hint">
                                <FontAwesomeIcon icon={faInfoCircle} /> Select your subject or enter a custom one.
                            </div>
                        </div>

                        {/* Tabs */}
                        <div className="tab-group">
                            <button
                                type="button"
                                className={`tab${activeTab === 'fileContent' ? ' active' : ''}`}
                                onClick={() => setActiveTab('fileContent')}
                            >
                                <FontAwesomeIcon icon={faCloudUploadAlt} /> File
                            </button>
                            <button
                                type="button"
                                className={`tab${activeTab === 'youtubeContent' ? ' active' : ''}`}
                                onClick={() => setActiveTab('youtubeContent')}
                            >
                                <FontAwesomeIcon icon={faPlay} /> YouTube
                            </button>
                            <button
                                type="button"
                                className={`tab${activeTab === 'textContent' ? ' active' : ''}`}
                                onClick={() => setActiveTab('textContent')}
                            >
                                <FontAwesomeIcon icon={faKeyboard} /> Text
                            </button>
                        </div>

                        {activeTab === 'fileContent' && (
                            <div className="tab-content active slide-in">
                                <div
                                    className="upload-zone"
                                    onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = '#2563eb'; }}
                                    onDragLeave={e => { e.preventDefault(); e.currentTarget.style.borderColor = '#1d4ed8'; }}
                                    onDrop={e => {
                                        e.preventDefault();
                                        handleFileChange({ target: { files: e.dataTransfer.files } });
                                    }}
                                >
                                    <div className="upload-icon">📖</div>
                                    <div className="upload-text">Upload your study materials</div>
                                    <div className="upload-description">PDF, DOCX, PPT, PPTX, or TXT</div>
                                    <input
                                        type="file"
                                        ref={fileInputRef}
                                        onChange={handleFileChange}
                                        className="hidden-file-input"
                                        accept=".pdf,.docx,.ppt,.pptx,.txt"
                                        id="slideFile"
                                    />
                                    <label htmlFor="slideFile" className="select-file-button">
                                        {isExtracting ? 'Extracting...' : 'Select file'}
                                    </label>
                                    <span className="file-name-display">{fileNameDisplay}</span>
                                </div>
                            </div>
                        )}

                        {activeTab === 'textContent' && (
                            <div className="tab-content active slide-in">
                                <textarea
                                    placeholder="Paste your study materials here..."
                                    value={studyText}
                                    onChange={e => setStudyText(e.target.value)}
                                />
                                <div className="character-count">
                                    <span>{studyText.length}</span> / 50000 characters
                                </div>
                            </div>
                        )}

                        {activeTab === 'youtubeContent' && (
                            <div className="tab-content active slide-in">
                                <div className="yt-input-row">
                                    <FontAwesomeIcon icon={faLink} className="yt-link-icon" />
                                    <input
                                        type="url"
                                        className="yt-url-input"
                                        placeholder="https://www.youtube.com/watch?v=..."
                                        value={youtubeUrl}
                                        onChange={e => { setYoutubeUrl(e.target.value); setYoutubeLoaded(null); }}
                                        onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), handleYoutubeLoad())}
                                        disabled={isExtracting}
                                    />
                                    <button
                                        type="button"
                                        className="yt-load-btn"
                                        onClick={handleYoutubeLoad}
                                        disabled={isExtracting || !youtubeUrl.trim()}
                                    >
                                        {isExtracting
                                            ? <><FontAwesomeIcon icon={faSpinner} spin /> Loading…</>
                                            : 'Load Transcript'}
                                    </button>
                                </div>
                                {youtubeLoaded && (
                                    <div className="yt-preview">
                                        <div className="yt-embed-wrapper">
                                            <iframe
                                                className="yt-embed"
                                                src={`https://www.youtube.com/embed/${youtubeLoaded.video_id}`}
                                                title={youtubeLoaded.title}
                                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                                allowFullScreen
                                            />
                                        </div>
                                        <div className="yt-preview-meta">
                                            <span className="yt-preview-title">{youtubeLoaded.title}</span>
                                            <span className="yt-preview-chars">
                                                {studyText.length.toLocaleString()} chars extracted
                                            </span>
                                        </div>
                                    </div>
                                )}
                                {!youtubeLoaded && (
                                    <p className="yt-hint">
                                        Paste any YouTube URL with captions enabled. The transcript will be extracted and used as study material.
                                    </p>
                                )}
                            </div>
                        )}

                        {/* Options */}
                        <div className="options-row">
                            <div className="option-group">
                                <span><FontAwesomeIcon icon={faListUl} /> MCQ Questions</span>
                                <input type="number" value={numMcq} onChange={e => setNumMcq(e.target.value)} min="0" max="30" className="number-input" />
                            </div>
                            <div className="option-group">
                                <span><FontAwesomeIcon icon={faPen} /> Short Answer</span>
                                <input type="number" value={numShort} onChange={e => setNumShort(e.target.value)} min="0" max="10" className="number-input" />
                            </div>
                            <div className="option-group">
                                <span><FontAwesomeIcon icon={faClock} /> Quiz Time (min)</span>
                                <input type="number" value={quizTime} onChange={e => setQuizTime(Math.max(1, parseInt(e.target.value, 10) || 10))} min="1" max="120" className="number-input" />
                            </div>
                            <div className="option-group">
                                <span><FontAwesomeIcon icon={faChartLine} /> Difficulty</span>
                                <select id="difficultySelect" value={difficulty} onChange={e => setDifficulty(e.target.value)}>
                                    <option value="random">Random</option>
                                    <option value="easy">Easy</option>
                                    <option value="medium">Medium</option>
                                    <option value="hard">Hard</option>
                                </select>
                            </div>
                        </div>

                        <div className="actions-row">
                            <button type="submit" className="main-btn" disabled={isGenerating || isExtracting}>
                                {isGenerating
                                    ? <><FontAwesomeIcon icon={faSpinner} spin /> Generating…</>
                                    : 'Generate Questions'}
                            </button>
                            <button type="button" className="clear-btn" onClick={handleClear}>Clear</button>
                        </div>
                    </form>

                    {errorMessages.length > 0 && (
                        <div className="messages-container">
                            {errorMessages.map((msg, i) => (
                                <div key={i} className="api-error-message">
                                    <FontAwesomeIcon icon={faExclamationCircle} /> {msg}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
            {toast.visible && (
                <div className={`toast ${toast.type}`} style={{ display: 'block' }}>
                    {toast.message}
                </div>
            )}
        </AppShell>
    );
};

export default CreateQuiz;