# Google OAuth 2.0 Integration

## Overview

Ocasia uses a **custom Google OAuth implementation** (no django-allauth dependency) that exchanges Google ID tokens for application auth tokens. This provides a seamless "Sign in with Google" experience on both login and signup pages.

## Architecture

### Flow Diagram

```
┌─────────┐         ┌──────────────┐         ┌─────────────┐         ┌──────────┐
│ Browser │         │   React App  │         │   Django    │         │  Google  │
│         │         │  (Frontend)  │         │  (Backend)  │         │  Servers │
└────┬────┘         └──────┬───────┘         └──────┬──────┘         └─────┬────┘
     │                     │                        │                       │
     │  1. Click "Sign in with Google"             │                       │
     ├─────────────────────>│                        │                       │
     │                     │                        │                       │
     │                     │  2. Request Google ID token                    │
     │                     ├────────────────────────────────────────────────>│
     │                     │                        │                       │
     │                     │  3. Return Google ID token                     │
     │                     │<────────────────────────────────────────────────┤
     │                     │                        │                       │
     │                     │  4. POST /api/auth/google/ {token: "..."}      │
     │                     ├───────────────────────>│                       │
     │                     │                        │                       │
     │                     │                        │  5. Verify ID token   │
     │                     │                        ├──────────────────────>│
     │                     │                        │                       │
     │                     │                        │  6. Token valid ✓     │
     │                     │                        │<──────────────────────┤
     │                     │                        │                       │
     │                     │                        │  7. Create/update user│
     │                     │                        │  8. Generate app token│
     │                     │                        │                       │
     │                     │  9. {token: "abc...", user: {...}}             │
     │                     │<───────────────────────┤                       │
     │                     │                        │                       │
     │  10. Navigate to /dashboard                  │                       │
     │<────────────────────┤                        │                       │
     │                     │                        │                       │
```

## Implementation Details

### Backend

**Location:** `backend/apps/accounts/google_auth.py`

**Key Components:**
- `GoogleAuthView(APIView)` - Handles `POST /api/auth/google/`
- Uses `google.oauth2.id_token.verify_oauth2_token()` for verification
- Creates user with `is_email_verified=True` (Google confirms email)
- Returns DRF Token (same format as password login)

**Dependencies:**
```txt
google-auth==2.36.0
google-auth-oauthlib==1.2.1
google-auth-httplib2==0.2.0
```

**User Creation Logic:**
```python
user, created = User.objects.get_or_create(
    email=email.lower(),
    defaults={
        'username': email.split('@')[0], 
        'is_email_verified': True, 
        'profile_image': picture,
    }
)
```

### Frontend

**Location:** `frontend/src/pages/Login/Login.jsx` and `Signup.jsx`

**Key Components:**
- `GoogleOAuthProvider` wrapper in `App.jsx`
- `GoogleLogin` component from `@react-oauth/google`
- `AuthContext.googleAuth()` method for state management

**Dependencies:**
```json
{
  "@react-oauth/google": "^0.12.1"
}
```

**Integration Example:**
```jsx
import { GoogleLogin } from '@react-oauth/google';

<GoogleLogin
  onSuccess={(credentialResponse) => {
    handleGoogleSuccess(credentialResponse);
  }}
  onError={() => {
    setError('Google sign-in failed. Please try again.');
  }}
  useOneTap={false}
  theme="outline"
  size="large"
  text="continue_with"
  shape="rectangular"
/>
```

## Setup Instructions

### 1. Google Cloud Console Configuration

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to **APIs & Services** > **Credentials**
4. Click **Create Credentials** > **OAuth 2.0 Client ID**
5. Configure OAuth consent screen (if first time)
6. Application type: **Web application**
7. Name: "Ocasia Web Client"

**Authorized JavaScript origins:**
```
http://localhost:3000
https://ocasia.live
https://ocasia.vercel.app
```

**Authorized redirect URIs** (optional for token exchange flow):
```
http://localhost:3000/auth/login
https://yourdomain.com/auth/login
```

8. Click **Create** and copy:
   - Client ID: `123456789012-xxxxxxxxxxxxx.apps.googleusercontent.com`
   - Client Secret: `GOCSPX-xxxxxxxxxxxxxx` (not used in current flow, keep secure)

### 2. Backend Environment Variables

Add to `backend/.env`:

```bash
# Google OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID=your-client-id-here
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret-here

# Note: Client secret not currently used in token-exchange flow
# but required for future redirect-based OAuth implementations
```

**Security:**
- ✅ Never commit `.env` file to version control
- ✅ Add `.env` to `.gitignore`
- ✅ Use different credentials for production vs development

### 3. Frontend Environment Variables

Add to `frontend/.env`:

```bash
# Must match backend GOOGLE_OAUTH_CLIENT_ID
REACT_APP_GOOGLE_CLIENT_ID=react-client-id-here

# EmailJS — welcome email sent to new Google signup users
REACT_APP_EMAILJS_PUBLIC_KEY=
REACT_APP_EMAILJS_SERVICE_ID=
REACT_APP_EMAILJS_TEMPLATE_WELCOME=
```

Template variables for `welcome_email`: `{{to_email}}`, `{{user_name}}`

**App.jsx configuration:**
```jsx
import { GoogleOAuthProvider } from '@react-oauth/google';

<GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID || "your-client-id"}>
  <AuthProvider>
    <App />
  </AuthProvider>
</GoogleOAuthProvider>
```

### 4. Install Dependencies

**Backend:**
```bash
cd backend
pip install google-auth google-auth-oauthlib google-auth-httplib2
```

**Frontend:**
```bash
cd frontend
npm install @react-oauth/google
```

### 5. URL Configuration

Ensure Google auth route is registered in `backend/apps/accounts/urls.py`:

```python
from .google_auth import GoogleAuthView

urlpatterns = [
    path("auth/google/", GoogleAuthView.as_view(), name="auth-google"),
    # ... other routes
]
```

## Testing

### Local Development

1. Start backend: `cd backend && python run.py`
2. Start frontend: `cd frontend && npm start`
3. Navigate to `http://localhost:3000/auth/login`
4. Click "Continue with Google" button
5. Select Google account
6. Should redirect to dashboard with user logged in

### Backend Logs

All Google auth events are logged:

```
Google auth signup for user: user@example.com
Google auth login for user: user@example.com
```

Check terminal output for these messages to confirm successful authentication.

### Common Issues

#### Issue: "Google OAuth is not configured on the server"

**Cause:** `GOOGLE_OAUTH_CLIENT_ID` not set in backend environment

**Solution:**
```bash
# Check backend/.env file
grep GOOGLE_OAUTH_CLIENT_ID backend/.env

# If missing, add it:
echo "GOOGLE_OAUTH_CLIENT_ID=your-client-id" >> backend/.env
```

#### Issue: "Invalid token" or "Token verification failed"

**Cause:** Client ID mismatch between frontend and backend, or expired token

**Solutions:**
- Verify `REACT_APP_GOOGLE_CLIENT_ID` matches `GOOGLE_OAUTH_CLIENT_ID`
- Check authorized origins in Google Cloud Console
- Ensure time is synced on server (Google tokens expire quickly)

#### Issue: "Redirect URI mismatch"

**Cause:** Authorized redirect URIs not configured in Google Cloud Console

**Solution:**
- Add all frontend URLs to authorized redirect URIs
- Wait 5 minutes for Google to propagate changes

#### Issue: "Pop-up blocked"

**Cause:** Browser blocking Google sign-in popup

**Solution:**
- User must allow popups for your domain
- Consider using `useOneTap={true}` for smoother UX

## User Experience

### First-Time Users (Signup)

1. Click "Continue with Google" on signup page
2. Select Google account
3. **New user created automatically** with:
   - Email from Google
   - Username = email prefix
   - `is_email_verified=True` (no verification needed)
   - Profile image from Google (if available)
4. **Welcome email sent via EmailJS** (`REACT_APP_EMAILJS_TEMPLATE_WELCOME`) — replaces the verification email that email/password users receive
5. Redirected to dashboard immediately

### Returning Users (Login)

1. Click "Continue with Google" on login page
2. Select Google account
3. **Existing user logged in** with:
   - Token refreshed
   - Last login timestamp updated
   - Profile image updated if changed in Google
4. Redirected to dashboard immediately

### Token Management

- Google OAuth users use same token system as password users
- Token stored in localStorage: `auth_token`
- User info stored in localStorage: `user` (JSON)
- Logout invalidates token server-side
- Page refresh rehydrates auth from localStorage

## Security Considerations

### Token Verification

- ✅ Tokens verified server-side using Google's public keys
- ✅ Signature validation ensures token authenticity
- ✅ Audience (`aud`) claim checked against client ID
- ✅ Expiration (`exp`) claim enforced by Google library

### Rate Limiting

Google auth endpoint shares rate limits with traditional auth:
- **5 requests per hour per IP**
- Prevents OAuth token enumeration attacks
- HTTP 429 returned on limit exceeded

### User Matching

- Users matched by **email address** (case-insensitive)
- Prevents duplicate accounts for same email
- Email verified automatically (trusted from Google)

### Data Privacy

Only the following data extracted from Google token:
- `email` (required)
- `given_name`, `family_name` (optional)
- `picture` (optional)
- `sub` (Google user ID, not stored)

**NOT collected:**
- Google access tokens (only ID token used)
- Google refresh tokens
- User's Google contacts/calendar/etc.

### Production Checklist

- [ ] Different OAuth credentials for production
- [ ] HTTPS enforced on production domain
- [ ] Authorized origins updated in Google Console
- [ ] Environment variables set in production environment
- [ ] Rate limiting monitored (check logs for 429 responses)
- [ ] Token verification errors monitored (check logs for warnings)

## API Reference

### Endpoint: POST /api/auth/google/

**URL:** `POST /api/auth/google/`

**Authentication:** None (public endpoint)

**Rate Limit:** 5 requests/hour per IP

**Request Body:**
```json
{
  "token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjU5M..."
}
```

**Success Response (200 OK):**
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": {
    "id": 123,
    "email": "user@example.com",
    "username": "user",
    "is_email_verified": true,
    "is_admin": false,
    "profile_image": "https://lh3.googleusercontent.com/a/...",
    "date_joined": "2026-03-07T12:00:00Z"
  },
  "created": true
}
```

**Error Responses:**

```json
// 400 Bad Request - Missing token
{
  "detail": "Google token is required."
}

// 400 Bad Request - Invalid token
{
  "detail": "Invalid Google token."
}

// 500 Internal Server Error - Server misconfiguration
{
  "detail": "Google OAuth is not configured on the server."
}
```

## Monitoring & Debugging

### Backend Logs

Enable debug logging in `backend/lamla/settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'apps.accounts': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

**Log messages to monitor:**
- `"Google auth signup for user: {email}"` - New user created via Google
- `"Google auth login for user: {email}"` - Existing user logged in
- `"Invalid Google token: {error}"` - Token verification failed
- `"GOOGLE_OAUTH_CLIENT_ID is not configured"` - Environment variable missing

### Frontend Debugging

Enable React DevTools and check:
- `AuthContext` state: `user`, `isAuthenticated`
- localStorage: `auth_token`, `user`
- Network tab: `/api/auth/google/` request/response

## Future Enhancements

Potential improvements to consider:

1. **Refresh token support** for long-lived sessions
2. **One Tap sign-in** (`useOneTap={true}`) for returning users
3. **Automatic sign-in** on subsequent visits
4. **Link Google account** to existing email/password account
5. **Multiple OAuth providers** (Facebook, GitHub, etc.)
6. **PKCE flow** for enhanced security
7. **Redirect-based OAuth** as alternative to token exchange

## References

- [Google Identity Documentation](https://developers.google.com/identity)
- [Google OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
- [@react-oauth/google NPM](https://www.npmjs.com/package/@react-oauth/google)
- [google-auth Python Library](https://googleapis.dev/python/google-auth/latest/)
- [Django REST Framework Authentication](https://www.django-rest-framework.org/api-guide/authentication/)
