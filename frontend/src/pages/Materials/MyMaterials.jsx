import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../../components/AppShell/AppShell';
import { useAuth } from '../../context/AuthContext';
import { materialsService } from '../../services/materials';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faCloudUploadAlt,
  faDownload,
  faSpinner,
  faTrash,
  faFilePdf,
} from '@fortawesome/free-solid-svg-icons';
import './Materials.css';
import '../Dashboards/Dashboard.css';

const MyMaterials = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);
  const [downloading, setDownloading] = useState(null);

  const fetchMine = useCallback(async () => {
    setLoading(true);
    try {
      const result = await materialsService.getMine();
      setMaterials(Array.isArray(result) ? result : []);
    } catch (error) {
      console.error('Failed to load my materials', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/auth/login');
      return;
    }
    fetchMine();
  }, [isAuthenticated, navigate, fetchMine]);

  const handleDownload = async (material) => {
    setDownloading(material.id);
    try {
      const url = await materialsService.download(material.id);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('Download failed', error);
    } finally {
      setDownloading(null);
    }
  };

  const handleDelete = async (materialId) => {
    if (!window.confirm('Delete this material? This cannot be undone.')) return;
    setDeleting(materialId);
    try {
      await materialsService.delete(materialId);
      setMaterials((prev) => prev.filter((m) => m.id !== materialId));
    } catch (error) {
      console.error('Delete failed', error);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <AppShell>
      <main className="db-main">
        <div className="db-tab">

          <div className="db-page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h1>My Uploads</h1>
              <p>Files you've shared with the community.</p>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="db-btn db-btn-ghost" onClick={() => navigate('/materials/community')}>
                Browse All Files
              </button>
              <button className="db-btn db-btn-primary" onClick={() => navigate('/materials/upload')}>
                <FontAwesomeIcon icon={faCloudUploadAlt} style={{ marginRight: 6 }} />
                Upload File
              </button>
            </div>
          </div>

          <div className="db-card">
            <div className="db-card-header">
              <h2>Uploaded files</h2>
              {!loading && materials.length > 0 && (
                <span style={{ fontSize: 13, color: 'var(--text-muted, #888)' }}>
                  {materials.length} file{materials.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>

            {loading ? (
              <div className="db-empty">
                <p>Loading your files…</p>
              </div>
            ) : materials.length === 0 ? (
              <div className="db-empty">
                <div className="db-empty-icon">
                  <FontAwesomeIcon icon={faFilePdf} />
                </div>
                <p>You haven't uploaded anything yet.</p>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                  <button className="db-btn db-btn-ghost" onClick={() => navigate('/materials/community')}>
                    Browse All Files
                  </button>
                  <button className="db-btn db-btn-primary" onClick={() => navigate('/materials/upload')}>
                    Upload File
                  </button>
                </div>
              </div>
            ) : (
              <div className="db-activity-list">
                {materials.map((material) => (
                  <div className="db-activity-item" key={material.id}>
                    <div className="db-activity-dot">
                      <FontAwesomeIcon icon={faFilePdf} />
                    </div>
                    <div className="db-activity-body">
                      <p>{material.title || material.original_filename || 'Untitled'}</p>
                      <span>
                        {material.subject_label || material.subject || 'General'}
                        {material.file_size_display ? ` · ${material.file_size_display}` : ''}
                        {` · ${material.download_count ?? 0} downloads`}
                        {` · ${new Date(material.created_at).toLocaleDateString()}`}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                      <button
                        className="db-btn db-btn-ghost db-btn-sm"
                        onClick={() => handleDownload(material)}
                        disabled={downloading === material.id}
                      >
                        {downloading === material.id
                          ? <FontAwesomeIcon icon={faSpinner} spin />
                          : <FontAwesomeIcon icon={faDownload} />}
                      </button>
                      <button
                        className="db-btn db-btn-danger db-btn-sm"
                        onClick={() => handleDelete(material.id)}
                        disabled={deleting === material.id}
                      >
                        {deleting === material.id
                          ? <FontAwesomeIcon icon={faSpinner} spin />
                          : <FontAwesomeIcon icon={faTrash} />}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      </main>
    </AppShell>
  );
};

export default MyMaterials;
