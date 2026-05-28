import React from "react";

export default function AboutSection({ visible }) {
  return (
    <section id="about" className="principles-section">
      <div className="container">
        {visible && (
          <div className="principles-grid">
            <div className="principle-card">
              <img
                src="/assets/highfive-with-teacher.jpg"
                alt="About Lamla AI"
              />
              <div className="principle-icon">AI-powered learning, built for students</div>
            </div>

            <div className="principle-card principle-text">
              <p className="about-label">ABOUT LAMLA AI</p>
              <h3>
                Your Study Partner,{" "}
                <span className="brand-highlight-text">Powered by AI</span>
              </h3>
              <p>
                Lamla AI was built for students who want to study with
                purpose. Upload your course materials and get quizzes,
                flashcards, and clear explanations generated in seconds —
                tailored to what you're actually studying.
              </p>
              <p>
                Stuck on a concept? Ask your AI tutor anytime. Want to make
                it competitive? Challenge friends to a live Clash quiz battle
                with a shared room code.
              </p>
              <p>
                Built by students at KNUST, for students everywhere. We know
                what it takes to study well — and we built the tools we
                wished we had.
              </p>
              <div className="hero-btns about-btns">
                <a href="/quiz/create" className="hero-btn primary">
                  Start Studying →
                </a>
                <a href="#features" className="hero-btn secondary">
                  Our Features
                </a>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}