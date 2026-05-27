import React, { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "../App.css";

const Navbar = ({ user, brandOnly = false }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const isHome = location.pathname === "/";

  const { isAuthenticated, logout, user: authUser } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  // Use user from prop or from auth context
  const currentUser = user || authUser;
  const profileImageUrl = currentUser?.profile_image || null;

  const [isScrolled, setIsScrolled] = useState(!isHome || window.scrollY > 50);

  useEffect(() => {
    if (!isHome) {
      setIsScrolled(true);
      return;
    }

    setIsScrolled(window.scrollY > 50);

    const handleScroll = () => setIsScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [isHome]);

  const closeMenu = () => setIsOpen(false);

  const handleHomeClick = (e) => {
    closeMenu();
    if (isHome) {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const handleLogout = async () => {
    closeMenu();
    await logout();
    navigate("/");
  };

  return (
    <>
      <header className={`main-header ${isScrolled ? "scrolled" : ""}`}>
        <div className="container header-container">
          <Link to="/" className="logo" onClick={handleHomeClick}>
            <img src="/assets/lamla_logo.png" alt="Lamla AI Logo" className="logo-img" />
            <span className="brand-highlight">Lamla.ai</span>
          </Link>

          {!brandOnly && (
            <>
              <div className="nav-right-group">
                <nav className="main-nav">
                  <ul className="nav-links nav-links--desktop">
                    {isAuthenticated || user ? (
                      <>
                        <li><Link to="/dashboard">Dashboard</Link></li>
                        <li><Link to="/quiz">Quiz</Link></li>
                        <li><Link to="/flashcards">Flashcards</Link></li>
                        <li><Link to="/clash">Clash</Link></li>
                        <li><Link to="/materials/community">Materials</Link></li>
                        <li><Link to="/ai-tutor">AI Tutor</Link></li>
                        <li className="nav-item-cta">
                          <button type="button" className="btn btn-nav-secondary" onClick={handleLogout}>Logout</button>
                        </li>
                      </>
                    ) : (
                      <>
                        <li><Link to="/" onClick={handleHomeClick}>Home</Link></li>
                        <li><Link to="/ai-tutor">AI Tutor</Link></li>
                        <li><Link to="/quiz/create">Quiz</Link></li>
                        <li><Link to="/flashcards">Flashcards</Link></li>
                        <li><Link to="/materials/community">Materials</Link></li>
                        <li className="nav-item-cta">
                          <Link to="/auth/login" className="btn btn-nav-secondary">Login</Link>
                        </li>
                      </>
                    )}
                  </ul>
                </nav>

                {(isAuthenticated || currentUser) && (
                  <Link to="/profile" className="navbar-profile-link">
                    <img 
                      src={profileImageUrl || "/assets/profile_default.png"} 
                      alt="Profile"
                      className="navbar-profile-image"
                    />
                  </Link>
                )}

                <button
                  className={`navbar-hamburger ${isOpen ? "open" : ""}`}
                  onClick={() => setIsOpen(!isOpen)}
                  aria-label="Toggle navigation"
                  aria-expanded={isOpen}
                >
                  <span></span>
                  <span></span>
                  <span></span>
                </button>
              </div>
            </>
          )}
        </div>
      </header>

      {!brandOnly && (
        <>
          <div className={`nav-overlay ${isOpen ? "open" : ""}`} onClick={closeMenu} aria-hidden="true" />

          <ul className={`nav-links nav-links--mobile ${isOpen ? "open" : ""}`}>
            {isAuthenticated || user ? (
              <>
                <li><Link to="/dashboard" onClick={closeMenu}>Dashboard</Link></li>
                <li><Link to="/quiz" onClick={closeMenu}>Quiz</Link></li>
                <li><Link to="/flashcards" onClick={closeMenu}>Flashcards</Link></li>
                <li><Link to="/clash" onClick={closeMenu}>Clash</Link></li>
                <li><Link to="/materials/community" onClick={closeMenu}>Materials</Link></li>
                <li><Link to="/ai-tutor" onClick={closeMenu}>AI Tutor</Link></li>
                <li className="nav-item-cta">
                  <button type="button" className="btn btn-nav-secondary" onClick={handleLogout}>Logout</button>
                </li>
              </>
            ) : (
              <>
                <li><Link to="/" onClick={handleHomeClick}>Home</Link></li>
                <li><Link to="/ai-tutor" onClick={closeMenu}>AI Tutor</Link></li>
                <li><Link to="/quiz/create" onClick={closeMenu}>Quiz</Link></li>
                <li><Link to="/flashcards" onClick={closeMenu}>Flashcards</Link></li>
                <li><Link to="/materials/community" onClick={closeMenu}>Materials</Link></li>
                <li><Link to="/auth/login" onClick={closeMenu}>Login</Link></li>
                <li className="nav-item-cta">
                  <Link to="/auth/signup" className="btn btn-nav-secondary" onClick={closeMenu}>Sign Up</Link>
                </li>
              </>
            )}
          </ul>
        </>
      )}
    </>
  );
};

export default Navbar;
