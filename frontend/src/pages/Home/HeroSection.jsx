import React from "react";

export default function HeroSection({ user }) {
  return (
    <>
      <section className="hero-section">
        <div className="hero-content">
          <h1 className="hero-title">
            <span className="title-line">The AI That</span>
            <span className="title-line">
              Studies With <span className="brand-highlight">You</span>
            </span>
          </h1>

          <p className="hero-desc">
            Generate quizzes and flashcards from your notes, get instant
            explanations from your AI tutor, and challenge friends in live quiz
            battles.
            <br />
            <strong className="highlight-text">One platform. Every way to study.</strong>
          </p>

          <div className="hero-btns">
            {!user ? (
              <a href="/auth/signup" className="hero-btn primary">
                Get Started Free
              </a>
            ) : (
              <a href="/dashboard" className="hero-btn primary">
                Go to Dashboard
              </a>
            )}
            <a href="#features" className="hero-btn secondary">
              Explore Features
            </a>
          </div>
        </div>
      </section>

      <div className="stats-band-wrapper">
        <div className="stats-band">
          <div className="stat-item">
            <span className="stat-number">50+</span>
            <span className="stat-label">STUDENTS</span>
          </div>
          <div className="stat-divider" />
          <div className="stat-item">
            <span className="stat-number">250+</span>
            <span className="stat-label">QUIZZES GENERATED</span>
          </div>
          <div className="stat-divider" />
          <div className="stat-item">
            <span className="stat-number">92%</span>
            <span className="stat-label">SUCCESS RATE</span>
          </div>
          <div className="stat-divider" />
          <div className="stat-item">
            <span className="stat-number">3+</span>
            <span className="stat-label">AI FEATURES</span>
          </div>
        </div>
      </div>
    </>
  );
}