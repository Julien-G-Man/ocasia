import React, { useState, useEffect } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { authService } from '../../services/auth';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faLock,
  faEye,
  faEyeSlash,
  faTriangleExclamation,
  faCircleCheck,
  faArrowLeft,
} from '@fortawesome/free-solid-svg-icons';
import '../Login/Login.css';

const MIN_LENGTH = 8;

const ResetPassword = () => {
  const [searchParams]              = useSearchParams();
  const navigate                    = useNavigate();

  const uid   = searchParams.get('uid');
  const token = searchParams.get('token');

  const [password, setPassword]             = useState('');
  const [confirm, setConfirm]               = useState('');
  const [showPassword, setShowPassword]     = useState(false);
  const [showConfirm, setShowConfirm]       = useState(false);
  const [isLoading, setIsLoading]           = useState(false);
  const [error, setError]                   = useState('');
  const [status, setStatus]                 = useState('form'); // 'form' | 'success' | 'invalid_link'

  useEffect(() => {
    if (!uid || !token) {
      setStatus('invalid_link');
    }
  }, [uid, token]);

  const passwordValid = password.length >= MIN_LENGTH;
  const passwordsMatch = password === confirm && confirm.length > 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!passwordValid) {
      setError(`Password must be at least ${MIN_LENGTH} characters.`);
      return;
    }

    if (!passwordsMatch) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      await authService.confirmPasswordReset(uid, token, password);
      setStatus('success');
    } catch (err) {
      setError(typeof err === 'string' ? err : 'Reset failed. This link may have expired or already been used.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page">
      {/* ── Left: Brand panel ── */}
      <aside className="auth-brand-panel">
        <div className="brand-glow" aria-hidden="true" />

        <div className="auth-brand-logo">
          <img src="/assets/logo.png" alt="Ocasia logo" />
          <span>Ocasia</span>
        </div>

        <div className="auth-brand-headline">
          <h2>
            Almost there.<br />
            Create a new <em>secure</em> password.
          </h2>
          <p>
            Choose a strong password you haven't used before.
            Your account security is our priority.
          </p>
        </div>

        <div className="auth-features">
          {[
            { icon: '🔐', label: 'Minimum 8 characters required' },
            { icon: '♻️', label: 'Old password immediately invalidated' },
            { icon: '🚪', label: 'All other sessions will be signed out' },
          ].map(({ icon, label }) => (
            <div className="auth-feature-item" key={label}>
              <div className="auth-feature-icon" aria-hidden="true">{icon}</div>
              <span className="auth-feature-text">{label}</span>
            </div>
          ))}
        </div>
      </aside>

      {/* ── Right: Form / state panel ── */}
      <main className="auth-form-panel">
        <div className="auth-form-inner">

          {/* ── Invalid link ── */}
          {status === 'invalid_link' && (
            <div style={{ textAlign: 'center', paddingTop: 24 }}>
              <div
                style={{
                  width: 64, height: 64, borderRadius: '50%',
                  background: 'rgba(239,68,68,0.1)',
                  border: '2px solid rgba(239,68,68,0.25)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 28px', fontSize: '1.6rem', color: '#ef4444',
                }}
                aria-hidden="true"
              >
                ✕
              </div>
              <h1 style={{ fontSize: '1.9rem', fontWeight: 800, color: '#f0f4f8', marginBottom: 12, letterSpacing: '-0.5px' }}>
                Invalid reset link
              </h1>
              <p style={{ color: '#718096', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: 32 }}>
                This reset link is missing required parameters.
                Please request a new one.
              </p>
              <Link to="/auth/forgot-password" className="auth-submit-btn" style={{ display: 'inline-block', textDecoration: 'none', marginBottom: 16 }}>
                Request a new link
              </Link>
              <br />
              <Link to="/auth/login" className="auth-link-muted">
                <FontAwesomeIcon icon={faArrowLeft} style={{ marginRight: 6 }} />
                Back to sign in
              </Link>
            </div>
          )}

          {/* ── Success ── */}
          {status === 'success' && (
            <div style={{ textAlign: 'center', paddingTop: 24 }}>
              <div
                style={{
                  width: 64, height: 64, borderRadius: '50%',
                  background: 'rgba(16,185,129,0.12)',
                  border: '2px solid rgba(16,185,129,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 28px', fontSize: '1.6rem', color: '#10b981',
                }}
                aria-hidden="true"
              >
                <FontAwesomeIcon icon={faCircleCheck} />
              </div>
              <h1 style={{ fontSize: '1.9rem', fontWeight: 800, color: '#f0f4f8', marginBottom: 12, letterSpacing: '-0.5px' }}>
                Password reset!
              </h1>
              <p style={{ color: '#718096', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: 32 }}>
                Your password has been updated. You can now sign in with your new password.
              </p>
              <button
                className="auth-submit-btn"
                style={{ width: '100%', marginBottom: 16, cursor: 'pointer' }}
                onClick={() => navigate('/auth/login', { replace: true })}
              >
                Sign in now
              </button>
            </div>
          )}

          {/* ── Form ── */}
          {status === 'form' && (
            <>
              <div className="auth-form-header">
                <h1>Set new password</h1>
                <p>Choose a strong password for your account.</p>
              </div>

              {error && (
                <div className="auth-error-banner" role="alert">
                  <FontAwesomeIcon icon={faTriangleExclamation} />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="auth-form" noValidate>
                {/* New password */}
                <div className="auth-field">
                  <label htmlFor="reset-password">New password</label>
                  <div className="auth-input-wrap">
                    <FontAwesomeIcon icon={faLock} className="auth-input-icon" />
                    <input
                      id="reset-password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="new-password"
                      autoFocus
                      disabled={isLoading}
                      required
                    />
                    <button
                      type="button"
                      className="auth-pw-toggle"
                      onClick={() => setShowPassword((v) => !v)}
                      disabled={isLoading}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      <FontAwesomeIcon icon={showPassword ? faEyeSlash : faEye} />
                    </button>
                  </div>
                  <p className={`auth-hint ${passwordValid ? 'auth-hint--valid' : ''}`}>
                    <span className="auth-hint-dot">{passwordValid ? '✓' : '·'}</span>
                    At least {MIN_LENGTH} characters
                  </p>
                </div>

                {/* Confirm password */}
                <div className="auth-field">
                  <label htmlFor="reset-confirm">Confirm new password</label>
                  <div className="auth-input-wrap">
                    <FontAwesomeIcon icon={faLock} className="auth-input-icon" />
                    <input
                      id="reset-confirm"
                      type={showConfirm ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      autoComplete="new-password"
                      disabled={isLoading}
                      required
                    />
                    <button
                      type="button"
                      className="auth-pw-toggle"
                      onClick={() => setShowConfirm((v) => !v)}
                      disabled={isLoading}
                      aria-label={showConfirm ? 'Hide password' : 'Show password'}
                    >
                      <FontAwesomeIcon icon={showConfirm ? faEyeSlash : faEye} />
                    </button>
                  </div>
                  {confirm.length > 0 && (
                    <p className={`auth-hint ${passwordsMatch ? 'auth-hint--valid' : ''}`}>
                      <span className="auth-hint-dot">{passwordsMatch ? '✓' : '·'}</span>
                      {passwordsMatch ? 'Passwords match' : 'Passwords do not match'}
                    </p>
                  )}
                </div>

                <button type="submit" className="auth-submit-btn" disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <span className="auth-spinner" aria-hidden="true" />
                      Resetting…
                    </>
                  ) : (
                    'Reset password'
                  )}
                </button>
              </form>

              <footer className="auth-form-footer">
                <Link to="/auth/login" className="auth-link-muted">
                  <FontAwesomeIcon icon={faArrowLeft} style={{ marginRight: 6 }} />
                  Back to sign in
                </Link>
              </footer>
            </>
          )}

        </div>
      </main>
    </div>
  );
};

export default ResetPassword;
