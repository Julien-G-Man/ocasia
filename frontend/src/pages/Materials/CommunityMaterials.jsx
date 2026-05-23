import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../../components/Navbar';
import { useAuth } from '../../context/AuthContext';
import { materialsService } from '../../services/materials';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faFilePdf, faDownload, faSearch, faUpload,
    faFilter, faUser, faCalendar, faSpinner, faTrash,
    faMagicWandSparkles,
} from '@fortawesome/free-solid-svg-icons';
import './Materials.css';

const SUBJECT_ICONS = {
    mathematics: '📐', sciences: '🔬', engineering: '⚙️', computing: '💻',
    humanities: '📖', business: '💼', languages: '🌍', medicine: '🩺',
    law: '⚖️', arts: '🎨', other: '📄',
};

const Materials = () => {
    const navigate = useNavigate();
    const { user, isAuthenticated } = useAuth();

    const [data, setData]               = useState({ materials: [], count: 0, total_pages: 1, subjects: [] });
    const [loading, setLoading]         = useState(true);
    const [page, setPage]               = useState(1);
    const [subject, setSubject]         = useState('');
    const [search, setSearch]           = useState('');
    const [searchInput, setSearchInput] = useState('');
    const [downloading, setDownloading] = useState(null);
    const [deleting, setDeleting]       = useState(null);
    const [extracting, setExtracting]   = useState(null);
    const [error, setError]             = useState('');
    const [extractError, setExtractError] = useState('');

    const fetchMaterials = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const result = await materialsService.getAll({ subject, q: search, page });
            setData(result);
        } catch {
            setError('Failed to load materials. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [subject, search, page]);

    useEffect(() => { fetchMaterials(); }, [fetchMaterials]);

    const handleSearch = (e) => {
        e.preventDefault();
        setPage(1);
        setSearch(searchInput.trim());
    };

    const handleSubject = (val) => {
        setPage(1);
        setSubject(val === subject ? '' : val);
    };

    const handleDownload = async (material) => {
        setDownloading(material.id);
        try {
            const url = await materialsService.download(material.id);
            window.open(url, '_blank', 'noopener,noreferrer');
            setData(prev => ({
                ...prev,
                materials: prev.materials.map(m =>
                    m.id === material.id ? { ...m, download_count: m.download_count + 1 } : m
                ),
            }));
        } catch {
            alert('Download failed. Please try again.');
        } finally {
            setDownloading(null);
        }
    };

    // Extract PDF text and pass directly into CreateQuiz
    const handleUseForQuiz = async (material) => {
        setExtractError('');
        setExtracting(material.id);
        try {
            const { text, subject: subjectLabel, title } = await materialsService.extractForQuiz(material.id);
            navigate('/quiz/create', {
                state: {
                    studyText: text,
                    subject: subjectLabel,
                    sourceTitle: title,
                },
            });
        } catch (err) {
            setExtractError(
                err?.response?.data?.detail ||
                'Could not extract text from this file. It may be image-based.'
            );
        } finally {
            setExtracting(null);
        }
    };

    const handleDelete = async (materialId) => {
        if (!window.confirm('Delete this material? This cannot be undone.')) return;
        setDeleting(materialId);
        try {
            await materialsService.delete(materialId);
            setData(prev => ({
                ...prev,
                count: prev.count - 1,
                materials: prev.materials.filter(m => m.id !== materialId),
            }));
        } catch {
            alert('Delete failed. Please try again.');
        } finally {
            setDeleting(null);
        }
    };

    const canDelete = (material) =>
        isAuthenticated && (user?.id === material.uploader_id || user?.is_admin);

    return (
        <>
            <Navbar />
            <div className="mat-page-wrapper">
                <div className="mat-container">

                    {/* ── Hero ── */}
                    <div className="mat-hero">
                        <div className="mat-hero-text">
                            <h1>📚 Community Materials</h1>
                            <p>
                                Community-shared PDFs — download raw files or push any PDF
                                straight into Quiz Mode with one click.
                            </p>
                        </div>
                        {isAuthenticated && (
                            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                <button
                                    className="mat-upload-hero-btn"
                                    onClick={() => navigate('/materials/upload')}
                                >
                                    <FontAwesomeIcon icon={faUpload} /> Upload Material
                                </button>
                                <button
                                    className="mat-upload-hero-btn"
                                    onClick={() => navigate('/materials/mine')}
                                    style={{ background: 'var(--surface)', color: 'var(--primary-color)', border: '1px solid var(--border)' }}
                                >
                                    My Uploads
                                </button>
                            </div>
                        )}
                    </div>

                    <div className="mat-body">

                        {/* ── Sidebar ── */}
                        <aside className="mat-sidebar">
                            <p className="mat-sidebar-title">
                                <FontAwesomeIcon icon={faFilter} /> Subject
                            </p>
                            <div className="mat-subject-list">
                                <button
                                    className={`mat-subject-chip${subject === '' ? ' active' : ''}`}
                                    onClick={() => handleSubject('')}
                                >
                                    📚 All Subjects
                                </button>
                                {data.subjects.map(s => (
                                    <button
                                        key={s.value}
                                        className={`mat-subject-chip${subject === s.value ? ' active' : ''}`}
                                        onClick={() => handleSubject(s.value)}
                                    >
                                        {SUBJECT_ICONS[s.value] || '📄'} {s.label}
                                    </button>
                                ))}
                            </div>
                        </aside>

                        {/* ── Main ── */}
                        <main className="mat-main">

                            <div className="mat-controls-card">
                                {/* Search */}
                                <form className="mat-search-section" onSubmit={handleSearch}>
                                    <div className="mat-search-input-wrap">
                                        <FontAwesomeIcon icon={faSearch} />
                                        <input
                                            type="text"
                                            placeholder="Search by title or description…"
                                            value={searchInput}
                                            onChange={e => setSearchInput(e.target.value)}
                                        />
                                    </div>
                                    <button type="submit" className="mat-search-btn">Search</button>
                                </form>

                                {/* Count */}
                                <div className="mat-meta-row">
                                    <span>
                                        {loading
                                            ? 'Loading…'
                                            : `${data.count} material${data.count !== 1 ? 's' : ''} found`}
                                        {subject && ` · ${data.subjects.find(s => s.value === subject)?.label || subject}`}
                                        {search && ` · "${search}"`}
                                    </span>
                                    {search && (
                                        <button
                                            className="mat-clear-btn"
                                            onClick={() => { setSearch(''); setSearchInput(''); setPage(1); }}
                                        >
                                            Clear search ×
                                        </button>
                                    )}
                                </div>
                            </div>

                            {error && <div className="mat-error">{error}</div>}
                            {extractError && <div className="mat-error">{extractError}</div>}

                            {/* Grid */}
                            {loading ? (
                                <div className="mat-loading">
                                    <FontAwesomeIcon icon={faSpinner} spin />
                                    Loading materials…
                                </div>
                            ) : data.materials.length === 0 ? (
                                <div className="mat-empty">
                                    <div className="mat-empty-icon">📭</div>
                                    <p>
                                        {search || subject
                                            ? 'No materials match this filter.'
                                            : 'No materials yet — be the first to upload!'}
                                    </p>
                                    {isAuthenticated && (
                                        <button
                                            className="mat-btn-primary"
                                            onClick={() => navigate('/materials/upload')}
                                        >
                                            <FontAwesomeIcon icon={faUpload} /> Upload Material
                                        </button>
                                    )}
                                </div>
                            ) : (
                                <div className="mat-grid">
                                    {data.materials.map(m => (
                                        <div className="mat-card" key={m.id}>

                                            {/* Top row */}
                                            <div className="mat-card-top">
                                                <div className="mat-card-icon-wrap">
                                                    <span className="mat-card-emoji">
                                                        {SUBJECT_ICONS[m.subject] || '📄'}
                                                    </span>
                                                    <FontAwesomeIcon icon={faFilePdf} className="mat-pdf-icon" />
                                                </div>
                                                {m.subject && (
                                                    <span className="mat-subject-badge">
                                                        {data.subjects.find(s => s.value === m.subject)?.label || m.subject}
                                                    </span>
                                                )}
                                            </div>

                                            {/* Body */}
                                            <div className="mat-card-body">
                                                <h3 className="mat-card-title" title={m.title}>{m.title}</h3>
                                                {m.description && (
                                                    <p className="mat-card-desc">{m.description}</p>
                                                )}
                                                <div className="mat-card-meta">
                                                    <span><FontAwesomeIcon icon={faUser} /> {m.uploader_username}</span>
                                                    <span>
                                                        <FontAwesomeIcon icon={faCalendar} />
                                                        {new Date(m.created_at).toLocaleDateString()}
                                                    </span>
                                                    <span>{m.file_size_display}</span>
                                                </div>
                                                <p className="mat-card-file" title={m.original_filename}>{m.original_filename}</p>
                                            </div>

                                            {/* Footer */}
                                            <div className="mat-card-footer">
                                                <div className="mat-card-footer-top">
                                                    <span className="mat-download-count">
                                                        <FontAwesomeIcon icon={faDownload} /> {m.download_count} download{m.download_count === 1 ? '' : 's'}
                                                    </span>
                                                </div>

                                                <div className="mat-card-actions">
                                                    {canDelete(m) && (
                                                        <button
                                                            className="mat-btn-danger"
                                                            onClick={() => handleDelete(m.id)}
                                                            disabled={deleting === m.id}
                                                            title="Delete this material"
                                                        >
                                                            {deleting === m.id
                                                                ? <FontAwesomeIcon icon={faSpinner} spin />
                                                                : <FontAwesomeIcon icon={faTrash} />}
                                                        </button>
                                                    )}
                                                    <button
                                                        className="mat-btn-secondary mat-btn-compact"
                                                        onClick={() => handleUseForQuiz(m)}
                                                        disabled={extracting === m.id}
                                                        title="Extract text and open in Quiz Mode"
                                                    >
                                                        {extracting === m.id
                                                            ? <><FontAwesomeIcon icon={faSpinner} spin /> Extracting…</>
                                                            : <><FontAwesomeIcon icon={faMagicWandSparkles} />Use for Quiz</>}
                                                    </button>
                                                    <button
                                                        className="mat-btn-primary mat-btn-compact"
                                                        onClick={() => handleDownload(m)}
                                                        disabled={downloading === m.id}
                                                    >
                                                        {downloading === m.id
                                                            ? <><FontAwesomeIcon icon={faSpinner} spin /> Opening…</>
                                                            : <><FontAwesomeIcon icon={faDownload} /> Download</>}
                                                    </button>
                                                </div>
                                            </div>

                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Pagination */}
                            {data.total_pages > 1 && (
                                <div className="mat-pagination">
                                    <button
                                        className="mat-page-btn"
                                        disabled={page === 1}
                                        onClick={() => setPage(p => p - 1)}
                                    >
                                        ← Previous
                                    </button>
                                    <span>Page {page} of {data.total_pages}</span>
                                    <button
                                        className="mat-page-btn"
                                        disabled={page === data.total_pages}
                                        onClick={() => setPage(p => p + 1)}
                                    >
                                        Next →
                                    </button>
                                </div>
                            )}

                        </main>
                    </div>
                </div>
            </div>
        </>
    );
};

export default Materials;