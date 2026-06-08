import React, { useEffect, useState } from "react";

const STAT_TARGETS = [
  { key: "students", value: 70,  suffix: "+", label: "STUDENTS" },
  { key: "quizzes",  value: 250, suffix: "+", label: "QUIZZES GENERATED" },
  { key: "success",  value: 92,  suffix: "%", label: "SUCCESS RATE" },
  { key: "features", value: 3,   suffix: "+", label: "AI FEATURES" },
];

export default function HeroSection({ user }) {
  const [counts, setCounts] = useState({ students: 0, quizzes: 0, success: 0, features: 0 });

  useEffect(() => {
    const duration = 3000;
    let raf;
    const timer = setTimeout(() => {
      const start = performance.now();
      const tick = (now) => {
        const p = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - p, 4);
        setCounts({
          students: Math.floor(eased * 70),
          quizzes:  Math.floor(eased * 250),
          success:  Math.floor(eased * 92),
          features: Math.floor(eased * 3),
        });
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, 800);

    return () => { clearTimeout(timer); cancelAnimationFrame(raf); };
  }, []);

  return (
    <>
      <section className="hero-section">
        <div className="hero-content">
          <h1 className="hero-title">
            <span className="title-line hero-line-1">Grow Deeper.</span>
            <span className="title-line hero-line-2">
              Perform <span className="brand-highlight">Better.</span>
            </span>
          </h1>

          <p className="hero-desc hero-desc-anim">
            The Acacia survives the harshest ground — not through luck, but
            because its roots go deeper than the drought. Ocasia is built on
            that same idea: AI quizzes, flashcards, a personal tutor, and live
            Clash battles for students who walk into every exam ready.
          </p>

          <div className="hero-btns hero-btns-anim">
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
              Explore
            </a>
          </div>
        </div>
      </section>

      <div className="stats-band-wrapper">
        <div className="stats-band anim-up anim-d5">
          <div className="stat-item">
            <span className="stat-number">{counts.students}+</span>
            <span className="stat-label">STUDENTS</span>
          </div>
          <div className="stat-divider" />
          <div className="stat-item">
            <span className="stat-number">{counts.quizzes}+</span>
            <span className="stat-label">QUIZZES GENERATED</span>
          </div>
          <div className="stat-divider" />
          <div className="stat-item">
            <span className="stat-number">{counts.success}%</span>
            <span className="stat-label">SUCCESS RATE</span>
          </div>
          <div className="stat-divider" />
          <div className="stat-item">
            <span className="stat-number">{counts.features}+</span>
            <span className="stat-label">AI FEATURES</span>
          </div>
        </div>
      </div>
    </>
  );
}
