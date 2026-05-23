import React from "react";

export default function GetInTouchSection({ onSubmit, contactStatus, contactIsError, isSendingContact }) {
  return (
    <section className="home-engagement-section">
      <div className="container">
        <div className="home-engagement-grid">
          <aside className="home-contact-aside">
            <div>
              <p className="section-label">GET IN TOUCH</p>
              <h3>Need help with your studies?</h3>
              <p>
                Tell us what you need and the Lamla team will respond as
                soon as possible.
              </p>
            </div>
            <div className="home-contact-meta">
              <div className="home-contact-meta-item">
                <span className="home-contact-meta-icon">1</span>
                <div className="home-contact-meta-text">
                  <h4>Quick response</h4>
                  <p>We usually reply within one business day.</p>
                </div>
              </div>
              <div className="home-contact-meta-item">
                <span className="home-contact-meta-icon">2</span>
                <div className="home-contact-meta-text">
                  <h4>Study support</h4>
                  <p>Ask about quizzes, flashcards, and materials.</p>
                </div>
              </div>
              <div className="home-contact-meta-item">
                <span className="home-contact-meta-icon">3</span>
                <div className="home-contact-meta-text">
                  <h4>Simple process</h4>
                  <p>Use the form and we will take it from there.</p>
                </div>
              </div>
            </div>
          </aside>

          <form className="home-contact-shell" onSubmit={onSubmit}>
            <div className="home-contact-form">
              <div className="home-contact-field-grid">
                <label className="home-contact-field">
                  <span className="home-contact-label">Full Name *</span>
                  <input type="text" name="name" placeholder="John Doe" required />
                </label>
                <label className="home-contact-field">
                  <span className="home-contact-label">Email Address *</span>
                  <input type="email" name="email" placeholder="john@example.com" required />
                </label>
              </div>
              <label className="home-contact-field">
                <span className="home-contact-label">Subject *</span>
                <input type="text" name="title" placeholder="Prayer Request, Inquiry..." required />
              </label>
              <label className="home-contact-field">
                <span className="home-contact-label">Message *</span>
                <textarea name="message" rows="6" placeholder="How can we help you?" required />
              </label>
              <button type="submit" disabled={isSendingContact}>
                {isSendingContact ? "Sending..." : "Send Message"}
              </button>
              {contactStatus && (
                <p className={`home-contact-status${contactIsError ? " home-contact-status--error" : ""}`}>
                  {contactStatus}
                </p>
              )}
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}