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
import '../Dashboards/Dashboard.css';

const SUBJECTS = [
    { value: 'mathematics', label: 'Mathematics' },
    { value: 'sciences',    label: 'Sciences'    },
    { value: 'engineering', label: 'Engineering' },
    { value: 'computing',   label: 'Computing'   },
    { value: 'humanities',  label: 'Humanities'  },
    { value: 'business',    label: 'Business'    },
    { value: 'languages',   label: 'Languages'   },
    { value: 'medicine',    label: 'Medicine'    },
    { value: 'law',         label: 'Law'         },
    { value: 'arts',        label: 'Arts'        },
    { value: 'other',       label: 'Other'       },
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
                <main className="db-main">
                    <div className="db-tab">
                        <div className="db-card" style={{ maxWidth: 480, margin: '40px auto', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
                            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: 'var(--primary-color)' }} />
                            <div style={{ fontSize: '2.8rem', color: 'var(--color-success)', marginBottom: 16 }}>
                                <FontAwesomeIcon icon={faCheckCircle} />
                            </div>
                            <h2 style={{ fontSize: '1.6rem', fontWeight: 900, color: 'var(--text-primary)', margin: '0 0 10px' }}>File Uploaded</h2>
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.97rem', margin: '0 0 28px', lineHeight: 1.6 }}>
                                Your PDF is now public — anyone can download or use it to generate a quiz.
                            </p>
                            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                                <button
                                    className="db-btn db-btn-primary"
                                    onClick={() => navigate('/materials/community')}
                                >
                                    Browse All Files
                                </button>
                                <button
                                    className="db-btn db-btn-ghost"
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
                </main>
            </AppShell>
        );
    }

    return (
        <AppShell>
            <main className="db-main">
                <div className="db-tab">

                    <div className="db-page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                        <div>
                            <h1>Upload a Study File</h1>
                            <p>Share a PDF with the community. Anyone can download it or generate a quiz from it.</p>
                        </div>
                        <button
                            className="db-btn db-btn-ghost"
                            onClick={() => navigate('/materials/mine')}
                        >
                            <FontAwesomeIcon icon={faArrowLeft} style={{ marginRight: 6 }} />
                            Back to Files
                        </button>
                    </div>

                    <form onSubmit={handleSubmit} noValidate>
                        <div className="db-card">

                            {/* Drop zone */}
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

                            {/* Title */}
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

                            {/* Subject chips */}
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
                                            {s.label}
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

                            {/* Actions */}
                            <div className="mup-actions">
                                <button
                                    type="submit"
                                    className="mup-submit-btn"
                                    disabled={uploading || !file || !title.trim()}
                                >
                                    {uploading
                                        ? <><FontAwesomeIcon icon={faSpinner} spin /> Uploading…</>
                                        : <><FontAwesomeIcon icon={faCloudUploadAlt} /> Upload File</>}
                                </button>
                                <button
                                    type="button"
                                    className="mup-cancel-btn"
                                    onClick={() => navigate('/materials/community')}
                                    disabled={uploading}
                                >
                                    Cancel
                                </button>
                            </div>

                        </div>
                    </form>

                </div>
            </main>
        </AppShell>
    );
};

export default MaterialUpload;
