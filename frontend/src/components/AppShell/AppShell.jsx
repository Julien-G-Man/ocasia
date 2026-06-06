import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faHome, faRobot, faBook, faLayerGroup, faFolder,
  faRightFromBracket, faUser, faBolt,
} from '@fortawesome/free-solid-svg-icons';
import { useAuth } from '../../context/AuthContext';
import './AppShell.css';

const NAV_ITEMS = [
  { label: 'Dashboard',  icon: faHome,       path: '/dashboard'       },
  { label: 'Quiz',       icon: faBook,       path: '/quiz'            },
  { label: 'Flashcards', icon: faLayerGroup, path: '/flashcards'      },
  { label: 'Clash',      icon: faBolt,       path: '/clash'           },
  { label: 'Materials',  icon: faFolder,     path: '/materials/mine'  },
  { label: 'AI Tutor',   icon: faRobot,      path: '/ai-tutor'        },
  { label: 'Profile',    icon: faUser,       path: '/profile'         },
];

const MOBILE_NAV_ITEMS = NAV_ITEMS.filter(({ path }) => path !== '/materials/mine');

export default function AppShell({
  children,
  variant = 'user',
  showSidebar = true,
  showTopbarNav = true,
  showMobileNav = true,
  sidebarVariant = variant,
  topbarNavItems = NAV_ITEMS.filter(({ path }) => path !== '/profile'),
  sidebarNavItems = NAV_ITEMS,
  mobileNavItems = MOBILE_NAV_ITEMS,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const isActive = (path) => (
    path === '/'
      ? location.pathname === '/'
      : location.pathname === path || location.pathname.startsWith(`${path}/`)
  );

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const initials = user?.username?.[0]?.toUpperCase();

  return (
    <div className={`app-shell app-shell--${variant} app-shell--sidebar-${sidebarVariant}${showSidebar ? '' : ' app-shell--no-sidebar'}`}>

      {/* ── Top navbar ─────────────────────────────────────── */}
      <header className="app-shell__topbar">
        <Link to="/" className="app-shell__topbar-brand">
          <img src="/assets/logo-blue.png" alt="Ocasia" className="app-shell__topbar-logo-img" />
          <span className="app-shell__topbar-logo-name" style={{ color: "#2563eb" }}>Ocasia</span>
        </Link>

        {showTopbarNav && (
          <nav className="app-shell__topbar-nav" aria-label="App navigation">
            {topbarNavItems.map(({ label, path }) => (
              <Link
                key={path}
                to={path}
                className={`app-shell__topbar-link${isActive(path) ? ' active' : ''}`}
              >
                {label}
              </Link>
            ))}
          </nav>
        )}

        <div className="app-shell__topbar-right">
          <Link to="/profile" className="app-shell__topbar-avatar-link">
            <div className="app-shell__avatar">
              {user?.profile_image
                ? <img src={user.profile_image} alt="avatar" />
                : (initials ?? <FontAwesomeIcon icon={faUser} />)}
            </div>
          </Link>
          <button
            className="app-shell__topbar-btn"
            onClick={handleLogout}
            title="Logout"
          >
            <FontAwesomeIcon icon={faRightFromBracket} />
          </button>
        </div>
      </header>

      {/* ── Desktop sidebar ─────────────────────────────────── */}
      {showSidebar && (
        <aside className="app-shell__sidebar">
          <nav className="app-shell__nav" aria-label="Main navigation">
            {sidebarNavItems.map(({ label, icon, path }) => (
              <Link
                key={path}
                to={path}
                className={`app-shell__nav-item${isActive(path) ? ' active' : ''}`}
              >
                <FontAwesomeIcon icon={icon} className="app-shell__nav-icon" />
                <span>{label}</span>
              </Link>
            ))}
          </nav>

          <div className="app-shell__user">
            <Link to="/profile" className="app-shell__user-info">
              <div className="app-shell__avatar">
                {user?.profile_image
                  ? <img src={user.profile_image} alt="avatar" />
                  : (initials ?? <FontAwesomeIcon icon={faUser} />)}
              </div>
              <div className="app-shell__user-text">
                <span className="app-shell__username">{user?.username ?? 'Account'}</span>
                <span className="app-shell__email">{user?.email ?? ''}</span>
              </div>
            </Link>
            <div className="app-shell__user-actions">
              <button
                className="app-shell__icon-btn app-shell__icon-btn--logout"
                onClick={handleLogout}
                title="Logout"
              >
                <FontAwesomeIcon icon={faRightFromBracket} />
              </button>
            </div>
          </div>
        </aside>
      )}

      {/* ── Page content ────────────────────────────────────── */}
      <div className="app-shell__content">
        {children}
      </div>

      {/* ── Mobile bottom nav ───────────────────────────────── */}
      {showMobileNav && (
        <nav className="app-shell__mobile-nav" aria-label="Mobile navigation">
          {mobileNavItems.map(({ label, icon, path }) => (
            <Link
              key={path}
              to={path}
              className={`app-shell__mobile-item${isActive(path) ? ' active' : ''}`}
            >
              <FontAwesomeIcon icon={icon} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
      )}

    </div>
  );
}
