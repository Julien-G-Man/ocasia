import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { GoogleLogin } from '@react-oauth/google';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faUser,
  faEnvelope,
  faLock,
  faEye,
  faEyeSlash,
  faCheckCircle,
  faTriangleExclamation,
} from '@fortawesome/free-solid-svg-icons';
import '../Login/Login.css';
import '../Login/GoogleAuth.css';

// ── Brand-panel feature list ──────────────────────────────────────────────────
const FEATURES = [
  { icon: '⚡', label: 'AI-powered quiz generation from any document' },
  { icon: '🃏', label: 'Smart flashcards with spaced repetition' },
  { icon: '📊', label: 'Progress analytics & performance insights' },
  { icon: '🤖', label: 'Personal AI tutor, available 24/7' },
];

// ── Component ─────────────────────────────────────────────────────────────────
const Signup = () => {
  const location = useLocation();
  const fromGuest = location.state?.fromGuest === true;
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword]               = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading]                     = useState(false);
  const [error, setError]                             = useState('');
  const [validations, setValidations]                 = useState({
    passwordLength:   false,
    passwordMatch:    false,
    emailValid:       false,
    usernameProvided: false,
  });

  const navigate = useNavigate();
  const { signup, googleAuth } = useAuth();

  const handleGoogleSuccess = async (credentialResponse) => {
    setIsLoading(true);
    setError('');
    try {
      const { user } = await googleAuth(credentialResponse.credential);
      const isAdmin = user?.is_admin;
      navigate(isAdmin ? '/admin-dashboard' : '/dashboard', { replace: true });
    } catch (err) {
      setError(err?.message || 'Google signup failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleError = () => {
    setError('Google signup was canceled or failed.');
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    validateField(name, value, { ...formData, [name]: value });
  };

  const validateField = (name, value, currentForm) => {
    switch (name) {
      case 'password':
        setValidations(prev => ({
          ...prev,
          passwordLength: value.length >= 8,
          passwordMatch:  value === currentForm.confirmPassword || currentForm.confirmPassword === '',
        }));
        break;
      case 'confirmPassword':
        setValidations(prev => ({ ...prev, passwordMatch: value === currentForm.password }));
        break;
      case 'email': {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        setValidations(prev => ({ ...prev, emailValid: emailRegex.test(value) }));
        break;
      }
      case 'username':
        setValidations(prev => ({ ...prev, usernameProvided: value.trim().length > 0 }));
        break;
      default:
        break;
    }
  };

  const isFormValid = () =>
    validations.passwordLength &&
    validations.passwordMatch &&
    validations.emailValid &&
    validations.usernameProvided;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!isFormValid()) {
      setError('Please fill in all fields correctly.');
      return;
    }

    setIsLoading(true);
    try {
      await signup(formData.email, formData.password, formData.username);
      navigate('/dashboard');
    } catch (err) {
      setError(typeof err === 'string' ? err : err?.message || 'Signup failed. Please try again.');
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
            Start learning<br />
            <em>smarter today</em>.
          </h2>
          <p>
            Join hundreds of students who use Ocasia to ace their exams
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
            <h1>Create your account</h1>
            <p>Join thousands of students studying smarter with Ocasia.</p>
          </div>

          {/* Guest upsell banner */}
          {fromGuest && !error && (
            <div className="auth-error-banner" role="status" style={{ background: 'rgba(37,99,235,0.08)', borderColor: '#2563eb', color: 'inherit' }}>
              <span>🎓</span>
              <span>You've used your free quiz — create an account to keep going!</span>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="auth-error-banner" role="alert">
              <FontAwesomeIcon icon={faTriangleExclamation} />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="auth-form" noValidate>

            {/* Username */}
            <div className="auth-field">
              <label htmlFor="signup-username">Username</label>
              <div className="auth-input-wrap">
                <FontAwesomeIcon icon={faUser} className="auth-input-icon" />
                <input
                  id="signup-username"
                  name="username"
                  type="text"
                  placeholder="coolstudent42"
                  value={formData.username}
                  onChange={handleChange}
                  autoComplete="username"
                  disabled={isLoading}
                  required
                />
                {validations.usernameProvided && (
                  <FontAwesomeIcon icon={faCheckCircle} className="auth-input-check" />
                )}
              </div>
            </div>

            {/* Email */}
            <div className="auth-field">
              <label htmlFor="signup-email">Email address</label>
              <div className="auth-input-wrap">
                <FontAwesomeIcon icon={faEnvelope} className="auth-input-icon" />
                <input
                  id="signup-email"
                  name="email"
                  type="email"
                  placeholder="you@example.com"
                  value={formData.email}
                  onChange={handleChange}
                  autoComplete="email"
                  disabled={isLoading}
                  required
                />
                {validations.emailValid && (
                  <FontAwesomeIcon icon={faCheckCircle} className="auth-input-check" />
                )}
              </div>
            </div>

            {/* Password */}
            <div className="auth-field">
              <label htmlFor="signup-password">Password</label>
              <div className="auth-input-wrap">
                <FontAwesomeIcon icon={faLock} className="auth-input-icon" />
                <input
                  id="signup-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Min. 8 characters"
                  value={formData.password}
                  onChange={handleChange}
                  autoComplete="new-password"
                  disabled={isLoading}
                  required
                />
                <button
                  type="button"
                  className="auth-pw-toggle"
                  onClick={() => setShowPassword(v => !v)}
                  disabled={isLoading}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  <FontAwesomeIcon icon={showPassword ? faEyeSlash : faEye} />
                </button>
              </div>
              <p className={`auth-hint ${validations.passwordLength ? 'auth-hint--valid' : ''}`}>
                <span className="auth-hint-dot">•</span> At least 8 characters
              </p>
            </div>

            {/* Confirm Password */}
            <div className="auth-field">
              <label htmlFor="signup-confirm-password">Confirm password</label>
              <div className="auth-input-wrap">
                <FontAwesomeIcon icon={faLock} className="auth-input-icon" />
                <input
                  id="signup-confirm-password"
                  name="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="Repeat your password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  autoComplete="new-password"
                  disabled={isLoading}
                  required
                />
                <button
                  type="button"
                  className="auth-pw-toggle"
                  onClick={() => setShowConfirmPassword(v => !v)}
                  disabled={isLoading}
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  <FontAwesomeIcon icon={showConfirmPassword ? faEyeSlash : faEye} />
                </button>
              </div>
              <p className={`auth-hint ${validations.passwordMatch ? 'auth-hint--valid' : ''}`}>
                <span className="auth-hint-dot">•</span> Passwords match
              </p>
            </div>

            {/* Submit */}
            <button
              type="submit"
              className="auth-submit-btn"
              disabled={!isFormValid() || isLoading}
            >
              {isLoading ? (
                <>
                  <span className="auth-spinner" aria-hidden="true" />
                  Creating account…
                </>
              ) : (
                'Create Account'
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="auth-divider">
            <span>or</span>
          </div>

          {/* Google Sign-Up */}
          <div className="google-auth-wrapper">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              size="large"
              width="100%"
              theme="outline"
              text="signup_with"
            />
          </div>

          {/* Footer */}
          <footer className="auth-form-footer">
            <p>
              Already have an account?{' '}
              <Link to="/auth/login" className="auth-link">Sign in</Link>
            </p>
            <Link to="/" className="auth-link-muted">← Back to home</Link>
          </footer>
        </div>
      </main>
    </div>
  );
};

export default Signup;