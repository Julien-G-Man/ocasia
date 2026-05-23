import React, { useEffect, useState, useRef } from 'react';
import AppShell from '../../components/AppShell/AppShell';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faCheckCircle, faExclamationCircle,
} from '@fortawesome/free-solid-svg-icons';
import './Profile.css';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const Profile = () => {
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading, updateProfile, uploadProfileImage, changePassword } = useAuth();
  const { theme, toggleTheme } = useTheme();

  // ── Profile form ────────────────────────────────────────────
  const [form,     setForm]     = useState({ username: '', email: '' });
  const [errors,   setErrors]   = useState({ username: '', email: '' });
  const [dirty,    setDirty]    = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [profMsg,  setProfMsg]  = useState({ ok: '', err: '' });

  // ── Image upload ────────────────────────────────────────────
  const [imageFile,    setImageFile]    = useState(null);
  const [imgUploading, setImgUploading] = useState(false);
  const [imgMsg,       setImgMsg]       = useState({ ok: '', err: '' });
  const [previewUrl, setPreviewUrl] = useState(null);
  const prevPreview = useRef(null);

  // ── Password form ────────────────────────────────────────────
  const [pwForm,  setPwForm]  = useState({ old_password: '', new_password: '', confirm: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg,   setPwMsg]   = useState({ ok: '', err: '' });

  // ── Auth guard ───────────────────────────────────────────────
  useEffect(() => {
    if (!isLoading && !isAuthenticated) navigate('/auth/login');
  }, [isLoading, isAuthenticated, navigate]);

  // ── Seed form from user ──────────────────────────────────────
  useEffect(() => {
    if (user) {
      setForm({ username: user.username || '', email: user.email || '' });
      setErrors({ username: '', email: '' });
      setDirty(false);
    }
  }, [user]);

  // ── Track dirty state ────────────────────────────────────────
  useEffect(() => {
    setDirty(
      form.username.trim() !== (user?.username || '') ||
      form.email.trim()    !== (user?.email    || '')
    );
  }, [form, user]);

  // ── Validation ───────────────────────────────────────────────
  const validate = (name, value) => {
    if (name === 'username') {
      if (!value.trim())          return 'Username cannot be blank.';
      if (value.trim().length > 50) return 'Username is too long (max 50 chars).';
    }
    if (name === 'email') {
      if (!EMAIL_RE.test(value.trim())) return 'Enter a valid email address.';
    }
    return '';
  };

  const handleFormChange = (e) => {
    const { name, value } = e.target;
    setForm(s => ({ ...s, [name]: value }));
    setErrors(s => ({ ...s, [name]: validate(name, value) }));
  };

  const formValid = !validate('username', form.username) && !validate('email', form.email);

  // ── Submit handlers ──────────────────────────────────────────
  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    const usernameErr = validate('username', form.username);
    const emailErr    = validate('email',    form.email);
    setErrors({ username: usernameErr, email: emailErr });
    if (usernameErr || emailErr) return;

    setSaving(true);
    setProfMsg({ ok: '', err: '' });
    try {
      await updateProfile(form.username.trim(), form.email.trim());
      setProfMsg({ ok: 'Profile updated successfully.', err: '' });
      setDirty(false);
    } catch (err) {
      const msg = err?.email?.[0] || err?.detail || err?.message || 'Update failed.';
      setProfMsg({ ok: '', err: msg });
    } finally {
      setSaving(false);
    }
  };

  const handleImageUpload = async (e) => {
    e.preventDefault();
    if (!imageFile) { setImgMsg({ ok: '', err: 'No image selected.' }); return; }
    setImgUploading(true);
    setImgMsg({ ok: '', err: '' });
    try {
      await uploadProfileImage(imageFile);
      setImgMsg({ ok: 'Photo updated.', err: '' });
      setImageFile(null);
    } catch (err) {
      setImgMsg({ ok: '', err: err?.detail || err?.message || 'Upload failed.' });
    } finally {
      setImgUploading(false);
    }
  };

  // Create a local preview URL for selected imageFile
  useEffect(() => {
    if (imageFile) {
      const url = URL.createObjectURL(imageFile);
      setPreviewUrl(url);
      if (prevPreview.current) URL.revokeObjectURL(prevPreview.current);
      prevPreview.current = url;
    } else {
      if (prevPreview.current) URL.revokeObjectURL(prevPreview.current);
      prevPreview.current = null;
      setPreviewUrl(null);
    }
    return () => {
      if (prevPreview.current) URL.revokeObjectURL(prevPreview.current);
    };
  }, [imageFile]);

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setPwMsg({ ok: '', err: '' });
    if (pwForm.new_password.length < 8) {
      setPwMsg({ ok: '', err: 'New password must be at least 8 characters.' }); return;
    }
    if (pwForm.new_password !== pwForm.confirm) {
      setPwMsg({ ok: '', err: 'Passwords do not match.' }); return;
    }
    setPwSaving(true);
    try {
      const res = await changePassword(pwForm.old_password, pwForm.new_password);
      if (res?.token) localStorage.setItem('auth_token', res.token);
      setPwMsg({ ok: 'Password changed successfully.', err: '' });
      setPwForm({ old_password: '', new_password: '', confirm: '' });
    } catch (err) {
      setPwMsg({ ok: '', err: err?.detail || err?.message || 'Password change failed.' });
    } finally {
      setPwSaving(false);
    }
  };

  if (isLoading || !isAuthenticated) return null;

  return (
    <AppShell>
      <main className="db-main">
        <div className="db-tab">

          <div className="db-page-header">
            <h1>My Profile</h1>
            <p>Manage your account information and security.</p>
          </div>

          {/* toast / status area */}
          <div id="profile-toast" aria-live="polite" className="db-toast">
            {profMsg.ok && <div className="db-feedback db-feedback-ok"><FontAwesomeIcon icon={faCheckCircle} /> {profMsg.ok}</div>}
            {profMsg.err && <div className="db-feedback db-feedback-err"><FontAwesomeIcon icon={faExclamationCircle} /> {profMsg.err}</div>}
            {imgMsg.ok && <div className="db-feedback db-feedback-ok"><FontAwesomeIcon icon={faCheckCircle} /> {imgMsg.ok}</div>}
            {imgMsg.err && <div className="db-feedback db-feedback-err"><FontAwesomeIcon icon={faExclamationCircle} /> {imgMsg.err}</div>}
            {pwMsg.ok && <div className="db-feedback db-feedback-ok"><FontAwesomeIcon icon={faCheckCircle} /> {pwMsg.ok}</div>}
            {pwMsg.err && <div className="db-feedback db-feedback-err"><FontAwesomeIcon icon={faExclamationCircle} /> {pwMsg.err}</div>}
          </div>

          <div className="db-grid">
            <div className="profile-left">
              {/* Account info */}
              <div className="db-card">
                <p className="db-section-label">Account Information</p>
                <form className="db-form" onSubmit={handleProfileSubmit}>
                  <div className="db-form-row">
                    <div className="db-field">
                      <label htmlFor="username">Username</label>
                      <input
                        id="username"
                        name="username"
                        type="text"
                        value={form.username}
                        onChange={handleFormChange}
                      />
                      {errors.username
                        ? <span className="db-feedback db-feedback-err"><FontAwesomeIcon icon={faExclamationCircle} /> {errors.username}</span>
                        : form.username.trim() && <span className="db-feedback db-feedback-ok"><FontAwesomeIcon icon={faCheckCircle} /> Looks good</span>}
                    </div>
                    <div className="db-field">
                      <label htmlFor="email">Email Address</label>
                      <input
                        id="email"
                        name="email"
                        type="email"
                        value={form.email}
                        onChange={handleFormChange}
                      />
                      {errors.email
                        ? <span className="db-feedback db-feedback-err"><FontAwesomeIcon icon={faExclamationCircle} /> {errors.email}</span>
                        : form.email.trim() && <span className="db-feedback db-feedback-ok"><FontAwesomeIcon icon={faCheckCircle} /> Valid email</span>}
                    </div>
                  </div>

                  <div className="db-actions">
                    <button
                      type="submit"
                      className="db-btn db-btn-primary"
                      disabled={saving || !dirty || !formValid}
                    >
                      {saving ? 'Saving…' : 'Save Changes'}
                    </button>
                  </div>
                </form>
              </div>

              {/* Password */}
              <div className="db-card">
                <p className="db-section-label">Change Password</p>
                <form className="db-form" onSubmit={handlePasswordSubmit}>
                  <div className="db-field">
                    <label htmlFor="old_password">Current Password</label>
                    <input
                      id="old_password"
                      name="old_password"
                      type="password"
                      value={pwForm.old_password}
                      placeholder="••••••••"
                      onChange={(e) => setPwForm(s => ({ ...s, old_password: e.target.value }))}
                    />
                  </div>
                  <div className="db-form-row">
                    <div className="db-field">
                      <label htmlFor="new_password">New Password</label>
                      <input
                        id="new_password"
                        name="new_password"
                        type="password"
                        value={pwForm.new_password}
                        placeholder="Min 8 characters"
                        onChange={(e) => setPwForm(s => ({ ...s, new_password: e.target.value }))}
                      />
                    </div>
                    <div className="db-field">
                      <label htmlFor="confirm">Confirm New Password</label>
                      <input
                        id="confirm"
                        name="confirm"
                        type="password"
                        value={pwForm.confirm}
                        placeholder="••••••••"
                        onChange={(e) => setPwForm(s => ({ ...s, confirm: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="db-actions">
                    <button type="submit" className="db-btn db-btn-primary" disabled={pwSaving}>
                      {pwSaving ? 'Updating…' : 'Change Password'}
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <aside className="profile-right">
              {/* Hero / avatar */}
              <div className="db-profile-hero">
                <div className="db-profile-avatar-xl">
                  {user?.profile_image
                    ? <img src={user.profile_image} alt="avatar" />
                    : user?.username?.[0]?.toUpperCase()}
                </div>
                <div className="db-profile-hero-info">
                  <h2>{user?.username}</h2>
                  <p>{user?.email}</p>
                  <div className="db-profile-hero-meta">
                    <span className={`db-badge ${user?.is_admin ? 'db-badge-red' : 'db-badge-yellow'}`}>
                      {user?.is_admin ? 'Admin' : 'Student'}
                    </span>
                    {user?.is_email_verified
                      ? <span className="db-badge db-badge-green">✓ Verified</span>
                      : <span className="db-badge db-badge-gray">Unverified</span>}
                  </div>
                </div>
              </div>

              {/* Profile photo */}
              <div className="db-card">
                <p className="db-section-label">Profile Photo</p>
                <form onSubmit={handleImageUpload} className="db-form">
                  <div className="db-field">
                    <label htmlFor="profile_file">Upload new photo (JPEG, PNG, WebP, GIF — max 5 MB)</label>
                    <div className="db-file-input-wrap">
                      <input
                        id="profile_file"
                        type="file"
                        accept="image/*"
                        onChange={(e) => { const f = e.target.files?.[0] || null; setImageFile(f); setImgMsg({ ok: '', err: '' }); }}
                      />
                    </div>
                    {imageFile && (
                      <span className="db-file-meta">
                        {imageFile.name} · {(imageFile.size / 1024 / 1024).toFixed(2)} MB
                      </span>
                    )}
                    {previewUrl && (
                      <div className="db-avatar-preview">
                        <img src={previewUrl} alt="preview" />
                      </div>
                    )}
                  </div>

                  <div className="db-actions">
                    <button
                      type="submit"
                      className="db-btn db-btn-primary"
                      disabled={imgUploading || !imageFile}
                    >
                      {imgUploading ? 'Uploading…' : 'Upload Photo'}
                    </button>
                  </div>
                </form>
              </div>

              {/* Preferences */}
              <div className="db-card">
                <p className="db-section-label">Preferences</p>
                <div className="db-theme-row">
                  <span>Theme</span>
                  <div className="db-theme-controls">
                    <span className="db-badge db-badge-gray">{theme}</span>
                    <button
                      className="db-btn db-btn-ghost db-btn-sm"
                      onClick={toggleTheme}
                    >
                      Toggle
                    </button>
                  </div>
                </div>
              </div>
            </aside>
          </div>

        </div>
      </main>
    </AppShell>
  );
};

export default Profile;