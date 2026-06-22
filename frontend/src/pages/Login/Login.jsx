import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { GoogleLogin} from '@react-oauth/google';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faEnvelope,
  faLock,
  faEye,
  faEyeSlash,
  faTriangleExclamation,
} from '@fortawesome/free-solid-svg-icons';
import './Login.css';
import './GoogleAuth.css';

// ── Brand-panel feature list ──────────────────────────────────────────────────
const FEATURES = [
  { icon: '⚡', label: 'AI-powered quiz generation from any document' },
  { icon: '🃏', label: 'Smart flashcards with spaced repetition' },
  { icon: '📊', label: 'Progress analytics & performance insights' },
  { icon: '🤖', label: 'Personal AI tutor, available 24/7' },
];

// ── Component ─────────────────────────────────────────────────────────────────
const Login = () => {
  const [identifier, setIdentifier]               = useState('');
  const [password, setPassword]         = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading]       = useState(false);
  const [error, setError]               = useState('');

  const navigate = useNavigate();
  const location = useLocation();
  const { login, googleAuth } = useAuth();

  const _redirectAfterAuth = (isAdmin) => {
    const from = location.state?.from?.pathname;
    navigate(from || (isAdmin ? '/admin-dashboard' : '/dashboard'), { replace: true });
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    setIsLoading(true);
    setError('');
    try {
      const { user } = await googleAuth(credentialResponse.credential);
      _redirectAfterAuth(user?.is_admin);
    } catch (err) {
      setError(err?.message || 'Google sign-in failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleError = () => {
    setError('Google sign-in was canceled or failed.');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!identifier.trim() || !password) {
      setError('Please enter your email and password.');
      return;
    }

    setIsLoading(true);
    try {
      const response = await login(identifier.trim().toLowerCase(), password);
      _redirectAfterAuth(response?.user?.is_admin);
    } catch (err) {
      // Normalise error message from various server response shapes
      const msg =
        err?.non_field_errors?.[0] ||
        err?.detail ||
        err?.message ||
        'Incorrect email or password. Please try again.';
      setError(msg);
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
            Study smarter,<br />
            not <em>harder</em>.
          </h2>
          <p>
            Join thousands of students who use Ocasia to ace their exams
            with personalised quizzes, flashcards, and an always-on AI tutor.
          </p>
        </div>

        <div className="auth-features">
          {FEATURES.map(({ icon, label }) => (
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
          <div className="auth-form-header">
            <h1>Welcome back</h1>
            <p>Sign in to continue your study journey.</p>
          </div>

          {/* Error banner */}
          {error && (
            <div className="auth-error-banner" role="alert">
              <FontAwesomeIcon icon={faTriangleExclamation} />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            {/* Email */}
            <div className="auth-field">
              <label htmlFor="login-email">Email / Username</label>
              <div className="auth-input-wrap">
                <FontAwesomeIcon icon={faEnvelope} className="auth-input-icon" />
                <input
                  id="login-email"
                  type="text"
                  placeholder="Email or Username"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  autoComplete="username"
                  disabled={isLoading}
                  required
                />
              </div>
            </div>

            {/* Password */}
            <div className="auth-field">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label htmlFor="login-password">Password</label>
                <Link
                  to="/auth/forgot-password"
                  className="auth-link-muted"
                  style={{ fontSize: '0.8rem', textTransform: 'none', letterSpacing: 0 }}
                  tabIndex={-1}
                >
                  Forgot password?
                </Link>
              </div>
              <div className="auth-input-wrap">
                <FontAwesomeIcon icon={faLock} className="auth-input-icon" />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
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
            </div>

            {/* Submit */}
            <button
              type="submit"
              className="auth-submit-btn"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <span className="auth-spinner" aria-hidden="true" />
                  Signing in…
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="auth-divider">
            <span>or</span>
          </div>

          {/* Google Sign-In */}
          <div className="google-auth-wrapper">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              size="large"
              width="100%"
              theme="outline"
              text="continue_with"
            />
          </div>

          {/* Footer */}
          <footer className="auth-form-footer">
            <p>
              Don't have an account?{' '}
              <Link to="/auth/signup" className="auth-link">
                Create one free
              </Link>
            </p>
            <Link to="/" className="auth-link-muted">
              ← Back to home
            </Link>
          </footer>
        </div>
      </main>
    </div>
  );
};

export default Login;