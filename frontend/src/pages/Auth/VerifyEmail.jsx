import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { authService } from '../../services/auth';
import './VerifyEmail.css';

/**
 * VerifyEmail page
 *
 * Mounted at: /verify-email?uid=...&token=...
 *
 * Flow:
 *  1. Extract uid + token from URL search params
 *  2. POST to /api/auth/verify-email/
 *  3. On success — update AuthContext + show success state
 *  4. On failure — show error state with a resend option (if authenticated)
 */
const VerifyEmail = () => {
  const [searchParams]  = useSearchParams();
  const { markEmailVerified, isAuthenticated, resendVerificationEmail } = useAuth();

  const [status, setStatus]       = useState('verifying'); // 'verifying' | 'success' | 'error' | 'already_verified'
  const [errorMsg, setErrorMsg]   = useState('');
  const [resendSent, setResendSent] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);

  useEffect(() => {
    const uid   = searchParams.get('uid');
    const token = searchParams.get('token');

    if (!uid || !token) {
      setErrorMsg('Invalid verification link. Please check your email and try again.');
      setStatus('error');
      return;
    }

    authService
      .verifyEmail(uid, token)
      .then((data) => {
        if (data.user) {
          markEmailVerified(data.user);
        }
        setStatus('success');
      })
      .catch((err) => {
        const detail = typeof err === 'string' ? err : (err?.detail || 'Verification failed. The link may have expired.');
        if (detail.toLowerCase().includes('already')) {
          setStatus('already_verified');
        } else {
          setErrorMsg(detail);
          setStatus('error');
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleResend = async () => {
    setResendLoading(true);
    try {
      await resendVerificationEmail();
      setResendSent(true);
    } catch {
      // Silently fail — user sees the button again
    } finally {
      setResendLoading(false);
    }
  };

  return (
    <div className="verify-container">
      <div className="verify-wrapper">
        <img src="/assets/logo-blue.png" alt="Ocasia" className="verify-logo" />

        {status === 'verifying' && (
          <>
            <div className="verify-spinner" />
            <h1>Verifying your email…</h1>
            <p>This will only take a moment.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="verify-icon verify-icon--success">✓</div>
            <h1>Email verified!</h1>
            <p>Your account is now fully activated. You're all set.</p>
            <Link to="/dashboard" className="verify-btn">Go to Dashboard</Link>
          </>
        )}

        {status === 'already_verified' && (
          <>
            <div className="verify-icon verify-icon--success">✓</div>
            <h1>Already verified</h1>
            <p>Your email address has already been verified.</p>
            <Link to="/dashboard" className="verify-btn">Go to Dashboard</Link>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="verify-icon verify-icon--error">✕</div>
            <h1>Verification failed</h1>
            <p>{errorMsg}</p>

            {isAuthenticated && (
              resendSent ? (
                <p className="verify-resent">
                  A new verification email has been sent. Check your inbox.
                </p>
              ) : (
                <button
                  className="verify-btn verify-btn--secondary"
                  onClick={handleResend}
                  disabled={resendLoading}
                >
                  {resendLoading ? 'Sending…' : 'Resend verification email'}
                </button>
              )
            )}

            <Link to="/" className="verify-back">← Back to Home</Link>
          </>
        )}
      </div>
    </div>
  );
};

export default VerifyEmail;