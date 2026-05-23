import React from "react";

export default function HeroSection({ user }) {
  return (
    <>
      <section className="hero-section">
        <div className="hero-content">
          <h1 className="hero-title">
            <span className="title-line">Turn Your Notes Into</span>
            <span className="title-line">
              Better Results with <span className="brand-highlight">Lamla AI</span>
            </span>
          </h1>

          <p className="hero-desc">
            Upload your study materials to generate quizzes, flashcards, and
            clear explanations in seconds.
            <br />
            <strong className="highlight-text">Study smarter. Perform better.</strong>
          </p>

          <div className="hero-btns">
            {!user ? (
              <a href="/auth/signup" className="hero-btn primary">
                Get Started Free
              </a>
            ) : (
              <a href="/quiz/create" className="hero-btn primary">
                Start Practicing
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