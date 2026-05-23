import React, { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../../components/AppShell/AppShell';
import { useAuth } from '../../context/AuthContext';
import { materialsService } from '../../services/materials';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faFilePdf, faCloudUploadAlt, faCheckCircle,
    faSpinner, faExclamationCircle, faArrowLeft,
} from '@fortawesome/free-solid-svg-icons';
import './Materials.css';

const SUBJECTS = [
    { value: 'mathematics', label: 'Mathematics', icon: '📐' },
    { value: 'sciences',    label: 'Sciences',    icon: '🔬' },
    { value: 'engineering', label: 'Engineering', icon: '⚙️' },
    { value: 'computing',   label: 'Computing',   icon: '💻' },
    { value: 'humanities',  label: 'Humanities',  icon: '📖' },
    { value: 'business',    label: 'Business',    icon: '💼' },
    { value: 'languages',   label: 'Languages',   icon: '🌍' },
    { value: 'medicine',    label: 'Medicine',    icon: '🩺' },
    { value: 'law',         label: 'Law',         icon: '⚖️' },
    { value: 'arts',        label: 'Arts',        icon: '🎨' },
    { value: 'other',       label: 'Other',       icon: '📄' },
];

const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
};

const MaterialUpload = () => {
    const navigate = useNavigate();
    const { isAuthenticated, isLoading } = useAuth();

    const [file, setFile]               = useState(null);
    const [title, setTitle]             = useState('');
    const [description, setDescription] = useState('');
    const [subject, setSubject]         = useState('other');
    const [dragging, setDragging]       = useState(false);
    const [progress, setProgress]       = useState(0);
    const [uploading, setUploading]     = useState(false);
    const [success, setSuccess]         = useState(false);
    const [error, setError]             = useState('');
    const fileInputRef = useRef(null);

    React.useEffect(() => {
        if (!isLoading && !isAuthenticated) navigate('/auth/login');
    }, [isLoading, isAuthenticated, navigate]);

    const acceptFile = useCallback((f) => {
        setError('');
        if (!f) return;
        if (f.type !== 'application/pdf') {
            setError('Only PDF files are accepted.');
            return;
        }
        if (f.size > 20 * 1024 * 1024) {
            setError('File must be under 20 MB.');
            return;
        }
        setFile(f);
        if (!title) {
            setTitle(f.name.replace(/\.pdf$/i, '').replace(/[-_]/g, ' '));
        }
    }, [title]);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        setDragging(false);
        acceptFile(e.dataTransfer.files[0]);
    }, [acceptFile]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        if (!file)          return setError('Please select a PDF file.');
        if (!title.trim())  return setError('Title is required.');

        setUploading(true);
        setProgress(0);
        try {
            await materialsService.upload(
                { file, title: title.trim(), description: description.trim(), subject },
                setProgress,
            );
            setSuccess(true);
        } catch (err) {
            setError(
                err?.response?.data?.detail ||
                err?.response?.data?.file?.[0] ||
                'Upload failed. Please try again.'
            );
        } finally {
            setUploading(false);
        }
    };

    // ── Success screen ────────────────────────────────────────────
    if (success) {
        return (
            <AppShell>
                <div className="mup-page-wrapper">
                    <div className="mup-success">
                        <div className="mup-success-icon">
                            <FontAwesomeIcon icon={faCheckCircle} />
                        </div>
                        <h2>Material Uploaded!</h2>
                        <p>Your PDF is now public — anyone can download or use it for quizzes.</p>
                        <div className="mup-success-actions">
                            <button className="mup-submit-btn" style={{ flex: 'none', padding: '14px 28px' }}
                                onClick={() => navigate('/materials/community')}
                            >
                                Browse Materials
                            </button>
                            <button
                                className="mup-cancel-btn"
                                style={{ flex: 'none', padding: '14px 28px' }}
                                onClick={() => {
                                    setFile(null); setTitle(''); setDescription('');
                                    setSubject('other'); setSuccess(false); setProgress(0);
                                }}
                            >
                                Upload Another
                            </button>
                        </div>
                    </div>
                </div>
            </AppShell>
        );
    }

    return (
        <AppShell>
            <div className="mup-page-wrapper">
                <div className="mup-card">

                    <button className="mup-back" onClick={() => navigate('/materials/community')}>
                        <FontAwesomeIcon icon={faArrowLeft} /> Back to Materials
                    </button>

                    <h1>Upload Material</h1>
                    <p className="mup-subtitle">
                        Share a PDF with the Lamla AI community. Anyone can download the raw file
                        or push it directly into Quiz Mode.
                    </p>

                    <form onSubmit={handleSubmit} noValidate>

                        {/* Drop zone — same pattern as CreateQuiz upload-zone */}
                        <div
                            className={`mup-dropzone${dragging ? ' dragging' : ''}${file ? ' has-file' : ''}`}
                            onDrop={handleDrop}
                            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                            onDragLeave={() => setDragging(false)}
                            onClick={() => !file && fileInputRef.current?.click()}
                            role="button"
                            tabIndex={0}
                            onKeyDown={e => e.key === 'Enter' && !file && fileInputRef.current?.click()}
                        >
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="application/pdf"
                                style={{ display: 'none' }}
                                onChange={e => acceptFile(e.target.files[0])}
                            />

                            {file ? (
                                <div className="mup-file-preview">
                                    <FontAwesomeIcon icon={faFilePdf} className="mup-pdf-icon" />
                                    <div className="mup-file-info">
                                        <p className="mup-file-name">{file.name}</p>
                                        <p className="mup-file-size">{formatSize(file.size)}</p>
                                    </div>
                                    <button
                                        type="button"
                                        className="mup-file-change"
                                        onClick={e => { e.stopPropagation(); setFile(null); setProgress(0); }}
                                    >
                                        Change file
                                    </button>
                                </div>
                            ) : (
                                <>
                                    <div className="mup-drop-icon">
                                        <FontAwesomeIcon icon={faCloudUploadAlt} />
                                    </div>
                                    <p className="mup-drop-title">Drag & drop your PDF here</p>
                                    <p className="mup-drop-sub">or click to browse — PDF only, max 20 MB</p>
                                </>
                            )}
                        </div>

                        {/* Title — subject-section style */}
                        <div className="mup-section">
                            <label className="mup-label" htmlFor="mup-title">
                                Title <span style={{ color: 'var(--enactus-error-red, #bd2413)', marginLeft: 2 }}>*</span>
                            </label>
                            <input
                                id="mup-title"
                                type="text"
                                className="mup-input"
                                placeholder="e.g. Introduction to Calculus — Chapter 3 Notes"
                                value={title}
                                onChange={e => setTitle(e.target.value)}
                                maxLength={200}
                                disabled={uploading}
                                required
                            />
                        </div>

                        {/* Description */}
                        <div className="mup-section">
                            <label className="mup-label" htmlFor="mup-desc">
                                Description{' '}
                                <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.88rem' }}>
                                    (optional)
                                </span>
                            </label>
                            <textarea
                                id="mup-desc"
                                className="mup-textarea"
                                placeholder="Briefly describe what's in this file…"
                                value={description}
                                onChange={e => setDescription(e.target.value)}
                                maxLength={500}
                                rows={3}
                                disabled={uploading}
                            />
                            <p className="mup-char-count">{description.length} / 500</p>
                        </div>

                        {/* Subject — tab-style chips */}
                        <div className="mup-section">
                            <label className="mup-label">Subject</label>
                            <div className="mup-subject-grid">
                                {SUBJECTS.map(s => (
                                    <button
                                        key={s.value}
                                        type="button"
                                        className={`mup-subject-chip${subject === s.value ? ' active' : ''}`}
                                        onClick={() => setSubject(s.value)}
                                        disabled={uploading}
                                    >
                                        {s.icon} {s.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Error */}
                        {error && (
                            <div className="mup-error">
                                <FontAwesomeIcon icon={faExclamationCircle} />
                                <span>{error}</span>
                            </div>
                        )}

                        {/* Progress */}
                        {uploading && (
                            <div className="mup-progress-wrap">
                                <div className="mup-progress-bar">
                                    <div className="mup-progress-fill" style={{ width: `${progress}%` }} />
                                </div>
                                <span>{progress}%</span>
                            </div>
                        )}

                        {/* Actions — actions-row style */}
                        <div className="mup-actions">
                            <button
                                type="submit"
                                className="mup-submit-btn"
                                disabled={uploading || !file || !title.trim()}
                            >
                                {uploading
                                    ? <><FontAwesomeIcon icon={faSpinner} spin /> Uploading…</>
                                    : <><FontAwesomeIcon icon={faCloudUploadAlt} /> Upload Material</>}
                            </button>
                            <button
                                type="button"
                                className="mup-cancel-btn"
                                onClick={() => navigate('/materials/community')}
                            >
                                Cancel
                            </button>
                        </div>

                    </form>
                </div>
            </div>
        </AppShell>
    );
};

export default MaterialUpload;