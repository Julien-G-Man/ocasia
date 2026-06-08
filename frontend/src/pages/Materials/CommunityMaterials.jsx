import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../../components/Navbar';
import AppShell from '../../components/AppShell/AppShell';
import { useAuth } from '../../context/AuthContext';
import { materialsService } from '../../services/materials';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faDownload, faSearch, faUpload,
    faUser, faCalendar, faSpinner, faTrash,
    faGraduationCap, faFilePdf,
} from '@fortawesome/free-solid-svg-icons';
import './Materials.css';

// ── Subject metadata — keys match SUBJECTS in MaterialUpload.jsx ──
const SUBJECT_META = {
    mathematics: {
        emoji: '📐',
        gradient: 'linear-gradient(135deg, #7c3aed, #a855f7)',
        image: 'https://images.unsplash.com/photo-1636466497217-26a8cbeaf0aa?q=80&w=1074&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D',
    },
    sciences: {
        emoji: '🔬',
        gradient: 'linear-gradient(135deg, #0369a1, #38bdf8)',
        image: 'https://plus.unsplash.com/premium_photo-1681426676206-0f2c02b48aff?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MTd8fHBoeXNpY3N8ZW58MHx8MHx8fDA%3D',
    },
    engineering: {
        emoji: '⚙️',
        gradient: 'linear-gradient(135deg, #374151, #9ca3af)',
        image: 'https://images.unsplash.com/photo-1769147339214-076740872485?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MTV8fG1lY2hhbmljYSUyMGVuZ2luZWVyaW5nfGVufDB8fDB8fHww',
    },
    computing: {
        emoji: '💻',
        gradient: 'linear-gradient(135deg, #1d4ed8, #60a5fa)',
        image: 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MTB8fGNvbXB1dGVyJTIwZW5naW5lZXJpbmd8ZW58MHx8MHx8fDA%3D',
    },
    humanities: {
        emoji: '📜',
        gradient: 'linear-gradient(135deg, #92400e, #fb923c)',
        image: 'https://images.unsplash.com/photo-1604549944235-3e5579b15cc2?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8aHVtYW5pdGllc3xlbnwwfHwwfHx8MA%3D%3D',
    },
    business: {
        emoji: '📊',
        gradient: 'linear-gradient(135deg, #b45309, #fbbf24)',
        image: 'https://images.unsplash.com/photo-1444653614773-995cb1ef9efa?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MjB8fGJ1c2luZXNzfGVufDB8fDB8fHww',
    },
    languages: {
        emoji: '🗣️',
        gradient: 'linear-gradient(135deg, #be185d, #fb7185)',
        image: 'https://images.unsplash.com/photo-1706403615881-d83dc2067c5d?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NHx8bGFuZ3VhZ2VzfGVufDB8fDB8fHww',
    },
    medicine: {
        emoji: '🩺',
        gradient: 'linear-gradient(135deg, #dc2626, #f87171)',
        image: 'https://images.unsplash.com/photo-1628595351029-c2bf17511435?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8c2NpZW5jZXxlbnwwfHwwfHx8MA%3D%3D',
    },
    law: {
        emoji: '⚖️',
        gradient: 'linear-gradient(135deg, #1e3a5f, #3b82f6)',
        image: 'https://plus.unsplash.com/premium_photo-1661769577787-9811af17f98d?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8OXx8bGF3fGVufDB8fDB8fHww',
    },
    arts: {
        emoji: '🎨',
        gradient: 'linear-gradient(135deg, #be185d, #f472b6)',
        image: 'https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8OHx8YXJ0c3xlbnwwfHwwfHx8MA%3D%3D',
    },
    other: {
        emoji: '📄',
        gradient: 'linear-gradient(135deg, #2563eb, #60a5fa)',
        image: 'https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MTB8fGxpYnJhcnl8ZW58MHx8MHx8fDA%3D',
    },
};

const DEFAULT_META = {
    emoji: '📄',
    gradient: 'linear-gradient(135deg, #2563eb, #60a5fa)',
    image: 'https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MTB8fGxpYnJhcnl8ZW58MHx8MHx8fDA%3D',
};

function getSubjectMeta(value) {
    if (!value) return DEFAULT_META;
    const key = value.toLowerCase().replace(/[\s-]+/g, '_');
    return SUBJECT_META[key] || SUBJECT_META[value.toLowerCase()] || DEFAULT_META;
}

function buildCardHeaderStyle(meta) {
    if (meta.image) {
        return {
            backgroundImage: `linear-gradient(160deg, rgba(0,0,0,0.12) 0%, rgba(0,0,0,0.52) 100%), url('${meta.image}?w=600&h=200&q=75&fit=crop&auto=format')`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
        };
    }
    return { background: meta.gradient };
}

const Materials = () => {
    const navigate = useNavigate();
    const { user, isAuthenticated, isLoading } = useAuth();

    // Pre-check token so AppShell shows immediately for returning users, no layout flash
    const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('auth_token');
    const useShell = isAuthenticated || (isLoading && hasToken);

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

    const handleUseForQuiz = async (material) => {
        setExtractError('');
        setExtracting(material.id);
        try {
            const { text, subject: subjectLabel, title } = await materialsService.extractForQuiz(material.id);
            navigate('/quiz/create', {
                state: { studyText: text, subject: subjectLabel, sourceTitle: title },
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

    // ── Page content (shared between AppShell and standalone) ────
    const pageContent = (
        <div className={`mat-page-wrapper${useShell ? ' mat-page-wrapper--in-shell' : ''}`}>
            <div className="mat-container">

                {/* ── Hero ── */}
                <div className="mat-hero">
                    <div className="mat-hero-inner">
                        <div className="mat-hero-text">
                            <span className="mat-hero-kicker">Community Library</span>
                            <h1>Learning Materials</h1>
                            <p>Notes, slides and past papers — shared by students, for students.</p>
                        </div>
                        {isAuthenticated && (
                            <div className="mat-hero-btns">
                                <button
                                    className="mat-upload-hero-btn"
                                    onClick={() => navigate('/materials/upload')}
                                >
                                    <FontAwesomeIcon icon={faUpload} /> Upload
                                </button>
                                <button
                                    className="mat-upload-hero-btn mat-hero-btn-ghost"
                                    onClick={() => navigate('/materials/mine')}
                                >
                                    My Uploads
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Embedded search */}
                    <form className="mat-hero-search" onSubmit={handleSearch}>
                        <div className="mat-hero-search-input">
                            <FontAwesomeIcon icon={faSearch} />
                            <input
                                type="text"
                                placeholder="Search by title or description…"
                                value={searchInput}
                                onChange={e => setSearchInput(e.target.value)}
                            />
                        </div>
                        <button type="submit" className="mat-hero-search-btn">Search</button>
                    </form>

                    {/* Stats */}
                    <div className="mat-hero-stats">
                        <div className="mat-hero-stat">
                            <span className="mat-hero-stat-num">{loading ? '—' : data.count}</span>
                            <span className="mat-hero-stat-label">Materials</span>
                        </div>
                        <div className="mat-hero-stat">
                            <span className="mat-hero-stat-num">{data.subjects.length || '—'}</span>
                            <span className="mat-hero-stat-label">Subjects</span>
                        </div>
                    </div>
                </div>

                {/* ── Category pills ── */}
                <div className="mat-category-strip">
                    <button
                        className={`mat-category-pill${subject === '' ? ' active' : ''}`}
                        onClick={() => handleSubject('')}
                    >
                        <span className="mat-cat-emoji">🏛️</span>
                        All Subjects
                    </button>
                    {data.subjects.map(s => {
                        const meta = getSubjectMeta(s.value);
                        return (
                            <button
                                key={s.value}
                                className={`mat-category-pill${subject === s.value ? ' active' : ''}`}
                                onClick={() => handleSubject(s.value)}
                            >
                                <span className="mat-cat-emoji">{meta.emoji}</span>
                                {s.label}
                            </button>
                        );
                    })}
                </div>

                {/* ── Content ── */}
                <main className="mat-main">

                    <div className="mat-meta-row">
                        <span>
                            {loading
                                ? 'Loading…'
                                : `${data.count} material${data.count !== 1 ? 's' : ''} found`}
                            {subject && ` in ${data.subjects.find(s => s.value === subject)?.label || subject}`}
                            {search && ` · "${search}"`}
                        </span>
                        {search && (
                            <button
                                className="mat-clear-btn"
                                onClick={() => { setSearch(''); setSearchInput(''); setPage(1); }}
                            >
                                Clear ×
                            </button>
                        )}
                    </div>

                    {error && <div className="mat-error">{error}</div>}
                    {extractError && <div className="mat-error">{extractError}</div>}

                    {loading ? (
                        <div className="mat-loading">
                            <FontAwesomeIcon icon={faSpinner} spin />
                            Loading materials…
                        </div>
                    ) : data.materials.length === 0 ? (
                        <div className="mat-empty">
                            <div className="mat-empty-icon">
                                <FontAwesomeIcon icon={faFilePdf} />
                            </div>
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
                            {data.materials.map(m => {
                                const meta = getSubjectMeta(m.subject);
                                const subjectLabel = data.subjects.find(s => s.value === m.subject)?.label || m.subject;
                                return (
                                    <div className="mat-card" key={m.id}>

                                        {/* Photo header */}
                                        <div
                                            className="mat-card-header"
                                            style={buildCardHeaderStyle(meta)}
                                        >
                                            <span className="mat-card-emoji">{meta.emoji}</span>
                                            {m.subject && (
                                                <span className="mat-card-subject-tag">{subjectLabel}</span>
                                            )}
                                        </div>

                                        {/* Body */}
                                        <div className="mat-card-body">
                                            <h3 className="mat-card-title" title={m.title}>{m.title}</h3>
                                            {m.description && (
                                                <p className="mat-card-desc">{m.description}</p>
                                            )}
                                            <div className="mat-card-meta">
                                                <span>
                                                    <FontAwesomeIcon icon={faUser} />
                                                    {m.uploader_username}
                                                </span>
                                                <span>{m.file_size_display}</span>
                                                <span>
                                                    <FontAwesomeIcon icon={faCalendar} />
                                                    {new Date(m.created_at).toLocaleDateString()}
                                                </span>
                                            </div>
                                        </div>

                                        {/* Footer */}
                                        <div className="mat-card-footer">
                                            <span className="mat-download-count">
                                                <FontAwesomeIcon icon={faDownload} />
                                                {m.download_count}
                                            </span>
                                            <div className="mat-card-actions">
                                                {canDelete(m) && (
                                                    <button
                                                        className="mat-btn-danger"
                                                        onClick={() => handleDelete(m.id)}
                                                        disabled={deleting === m.id}
                                                        title="Delete"
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
                                                    title="Generate quiz from this file"
                                                >
                                                    {extracting === m.id
                                                        ? <FontAwesomeIcon icon={faSpinner} spin />
                                                        : <><FontAwesomeIcon icon={faGraduationCap} /> Quiz</>}
                                                </button>
                                                <button
                                                    className="mat-btn-primary mat-btn-compact"
                                                    onClick={() => handleDownload(m)}
                                                    disabled={downloading === m.id}
                                                >
                                                    {downloading === m.id
                                                        ? <FontAwesomeIcon icon={faSpinner} spin />
                                                        : <><FontAwesomeIcon icon={faDownload} /> Download</>}
                                                </button>
                                            </div>
                                        </div>

                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {data.total_pages > 1 && (
                        <div className="mat-pagination">
                            <button
                                className="mat-page-btn"
                                disabled={page === 1}
                                onClick={() => setPage(p => p - 1)}
                            >
                                ← Prev
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
    );

    // ── Render with AppShell (auth) or Navbar (guest) ────────────
    return useShell ? (
        <AppShell>{pageContent}</AppShell>
    ) : (
        <>
            <Navbar />
            {pageContent}
        </>
    );
};

export default Materials;
