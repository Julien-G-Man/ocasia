import React from "react";

export default function AboutSection({ visible }) {
  return (
    <section id="about" className="principles-section">
      <div className="container">
        {visible && (
          <div className="principles-grid">
            <div className="principle-card anim-left">
              <img
                src="/assets/highfive-with-teacher.jpg"
                alt="About Ocasia"
              />
              <div className="principle-icon">Born at KNUST · Built for the world</div>
            </div>

            <div className="principle-card principle-text anim-right anim-d2">
              <p className="about-label">ABOUT OCASIA</p>
              <h3>
                Built for students who want to{" "}
                <span className="brand-highlight-text">actually learn</span>
              </h3>
              <p>
                Ocasia was built by students at KNUST who lived the pressure —
                guesswork, late nights, the fear of not being ready. We built
                the tools we wished we had.
              </p>
              <p>
                We believe studying should be intentional, not panicked.
                Not about cramming and hoping — about knowing your material
                and walking into every exam confident.
              </p>
              <p className="brand-tagline-line">
                Starting from Africa.{" "}
                <span className="brand-highlight-text">Built for every student, everywhere.</span>
              </p>
              <div className="hero-btns about-btns">
                <a href="/auth/signup" className="hero-btn primary">
                  Start for Free →
                </a>
                <a href="#features" className="hero-btn secondary">
                  See What We Offer
                </a>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
