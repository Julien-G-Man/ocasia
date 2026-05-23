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
              <div className="principle-icon">Study tool for notes, quizzes, and flashcards</div>
            </div>

            <div className="principle-card principle-text">
              <p className="about-label">ABOUT LAMLA AI</p>
              <h3>
                Smarter Studying, {" "}
                <span className="brand-highlight-text">Better Results</span>
              </h3>
              <p>
                Lamla AI was built for students who want to study with
                purpose. We combine cutting-edge AI with your own course
                materials to create a personalised study experience that
                actually works.
              </p>
              <p>
                Whether you're preparing for finals or just reviewing before
                a test — Lamla AI turns your slides and notes into quizzes,
                flashcards, and clear study explanations.
              </p>
              <p>
                Built by students, for students. Our platform evolves with
                your feedback so you can walk into every exam with
                confidence.
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