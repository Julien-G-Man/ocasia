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
  faCalendar,
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
    try {
      const url = await materialsService.download(material.id);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('Download failed', error);
    }
  };

  const handleDelete = async (materialId) => {
    if (!window.confirm('Delete this material? This cannot be undone.')) return;
    setDeleting(materialId);
    try {
      await materialsService.delete(materialId);
      setMaterials((prev) => prev.filter((material) => material.id !== materialId));
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
              <h1>My Materials</h1>
              <p>Your uploaded files, ready for quizzes and downloads.</p>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="db-btn db-btn-ghost" onClick={() => navigate('/materials/community')}>
                View Community Uploads
              </button>
              <button className="db-btn db-btn-primary" onClick={() => navigate('/materials/upload')}>
                <FontAwesomeIcon icon={faCloudUploadAlt} style={{ marginRight: 6 }} />
                Upload Material
              </button>
            </div>
          </div>

          <div className="db-card">
            {loading ? (
              <div className="db-empty"><p>Loading your materials…</p></div>
            ) : materials.length === 0 ? (
              <div className="db-empty">
                <div className="db-empty-icon">📁</div>
                <p>You have not uploaded anything yet.</p>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                  <button className="db-btn db-btn-ghost" onClick={() => navigate('/materials/community')}>
                    View All Materials
                  </button>
                  <button className="db-btn db-btn-primary" onClick={() => navigate('/materials/upload')}>
                    Upload Material
                  </button>
                </div>
              </div>
            ) : (
              <div className="db-materials-list">
                {materials.map((material) => (
                  <div className="db-material-row" key={material.id}>
                    <div className="db-material-info">
                      <h3>{material.title || material.original_filename || 'Untitled material'}</h3>
                      <p>
                        {material.subject_label || material.subject || 'General'}
                        {material.file_size_display ? ` · ${material.file_size_display}` : ''}
                      </p>
                    </div>
                    <div className="db-material-meta">
                      <span>
                        <FontAwesomeIcon icon={faCalendar} /> {new Date(material.created_at).toLocaleDateString()}
                      </span>
                      <span>{material.download_count || 0} downloads</span>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      <button className="db-btn db-btn-ghost db-btn-sm" onClick={() => handleDownload(material)}>
                        <FontAwesomeIcon icon={faDownload} /> Download
                      </button>
                      <button
                        className="db-btn db-btn-danger db-btn-sm"
                        onClick={() => handleDelete(material.id)}
                        disabled={deleting === material.id}
                      >
                        {deleting === material.id ? <FontAwesomeIcon icon={faSpinner} spin /> : <FontAwesomeIcon icon={faTrash} />} {' '}
                        Delete
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
