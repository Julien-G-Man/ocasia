import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faEnvelope,
  faTriangleExclamation,
  faCircleCheck,
  faArrowLeft,
} from '@fortawesome/free-solid-svg-icons';
import '../Login/Login.css';

const ForgotPassword = () => {
  const [email, setEmail]         = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState('');
  const [submitted, setSubmitted] = useState(false);

  const { requestPasswordReset } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }

    setIsLoading(true);
    try {
      await requestPasswordReset(email.trim().toLowerCase());
      setSubmitted(true);
    } catch (err) {
      setError(typeof err === 'string' ? err : 'Something went wrong. Please try again.');
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
            Don't worry,<br />
            we've got you <em>covered</em>.
          </h2>
          <p>
            Enter the email address linked to your account and we'll send
            you a secure link to reset your password.
          </p>
        </div>

        <div className="auth-features">
          {[
            { icon: '🔒', label: 'Secure, time-limited reset link' },
            { icon: '⚡', label: 'Delivered instantly to your inbox' },
            { icon: '🔁', label: 'Link expires after use automatically' },
          ].map(({ icon, label }) => (
            <div className="auth-feature-item" key={label}>
              <div className="auth-feature-icon" aria-hidden="true">{icon}</div>
              <span className="auth-feature-text">{label}</span>
            </div>
          ))}
        </div>
      </aside>

      {/* ── Right: Form panel ── */}
      <main className="auth-form-panel">
        <div className="auth-form-inner">

          {!submitted ? (
            <>
              <div className="auth-form-header">
                <h1>Forgot password?</h1>
                <p>Enter your email and we'll send you a reset link.</p>
              </div>

              {error && (
                <div className="auth-error-banner" role="alert">
                  <FontAwesomeIcon icon={faTriangleExclamation} />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="auth-form" noValidate>
                <div className="auth-field">
                  <label htmlFor="forgot-email">Email address</label>
                  <div className="auth-input-wrap">
                    <FontAwesomeIcon icon={faEnvelope} className="auth-input-icon" />
                    <input
                      id="forgot-email"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                      autoFocus
                      disabled={isLoading}
                      required
                    />
                  </div>
                </div>

                <button type="submit" className="auth-submit-btn" disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <span className="auth-spinner" aria-hidden="true" />
                      Sending…
                    </>
                  ) : (
                    'Send reset link'
                  )}
                </button>
              </form>

              <footer className="auth-form-footer">
                <p>
                  Remember your password?{' '}
                  <Link to="/auth/login" className="auth-link">Sign in</Link>
                </p>
                <Link to="/" className="auth-link-muted">
                  <FontAwesomeIcon icon={faArrowLeft} style={{ marginRight: 6 }} />
                  Back to home
                </Link>
              </footer>
            </>
          ) : (
            /* ── Success state ── */
            <div style={{ textAlign: 'center', paddingTop: 24 }}>
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: '50%',
                  background: 'rgba(16,185,129,0.12)',
                  border: '2px solid rgba(16,185,129,0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 28px',
                  fontSize: '1.6rem',
                  color: '#10b981',
                }}
                aria-hidden="true"
              >
                <FontAwesomeIcon icon={faCircleCheck} />
              </div>

              <h1 style={{ fontSize: '1.9rem', fontWeight: 800, color: '#f0f4f8', marginBottom: 12, letterSpacing: '-0.5px' }}>
                Check your inbox
              </h1>
              <p style={{ color: '#718096', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: 32, maxWidth: 320, margin: '0 auto 32px' }}>
                If an account is linked to <strong style={{ color: '#a0aec0' }}>{email}</strong>, you'll
                receive a password reset link shortly.
              </p>

              <p style={{ color: '#4a5568', fontSize: '0.875rem', marginBottom: 28 }}>
                Didn't get it? Check your spam folder or{' '}
                <button
                  onClick={() => setSubmitted(false)}
                  style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', fontWeight: 600, fontSize: 'inherit', padding: 0 }}
                >
                  try again
                </button>
                .
              </p>

              <Link to="/auth/login" className="auth-link-muted">
                <FontAwesomeIcon icon={faArrowLeft} style={{ marginRight: 6 }} />
                Back to sign in
              </Link>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default ForgotPassword;
