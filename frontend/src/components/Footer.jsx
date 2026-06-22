import React from "react";
import { useState } from "react";
import { Link } from "react-router-dom";
import djangoApi from "../services/api";
import "../App.css";

const Footer = () => {
  const [newsletterStatus, setNewsletterStatus] = useState("");
  const [isSubscribing, setIsSubscribing] = useState(false);

  const handleNewsletterSubmit = async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const formData = new FormData(form);

    try {
      setIsSubscribing(true);
      await djangoApi.post("/dashboard/newsletter/", {
        email: formData.get("newsletter_email"),
      });
      setNewsletterStatus("Subscribed. You will receive updates soon.");
      form.reset();
    } catch (err) {
      console.error("Newsletter subscribe error:", err);
      setNewsletterStatus("Subscription failed. Please try again.");
    } finally {
      setIsSubscribing(false);
      setTimeout(() => setNewsletterStatus(""), 3500);
    }
  };

  return (
    <footer className="main-footer">
      <div className="container footer-grid">
        <div className="footer-col footer-about">
          <h3>Contact Us</h3>
          <ul>
            <li>
              <a href="mailto:lamlaaiteam@gmail.com"><i className="fas fa-envelope"></i> lamlaaiteam@gmail.com</a>
            </li>
            <li>
              <a href="tel:+233509341251"><i className="fas fa-phone"></i> +233 50 934 1251</a>
            </li>
          </ul>
        </div>
        <div className="footer-col">
          <h3>Quick Links</h3>
          <ul>
            <li><Link to="/">Home</Link></li>
            <li><Link to="/ai-tutor">AI Tutor</Link></li>
            <li><Link to="/quiz/create">Quiz</Link></li>
            <li><Link to="/flashcards">Flashcards</Link></li>
            <li><Link to="/clash">Clash</Link></li>
            <li><Link to="/#exam-analyzer">Exam Analyzer</Link></li>
          </ul>
        </div>
        <div className="footer-col footer-form-col">
          <h3>Newsletter</h3>
          <p className="footer-newsletter-text">Get product updates, study tips, and feature announcements.</p>
          <form className="footer-newsletter-bar" onSubmit={handleNewsletterSubmit}>
            <input type="email" name="newsletter_email" placeholder="Enter your email address" required />
            <button type="submit" disabled={isSubscribing}>
              {isSubscribing ? "Subscribing..." : "Subscribe"}
            </button>
          </form>
          {newsletterStatus && <p className="footer-form-status">{newsletterStatus}</p>}
        </div>

        <div className="footer-col">
          <h3>Connect With Us</h3>
          <div className="social-icons">
            <a href="https://www.instagram.com/ocasia.app" className="social-icon" aria-label="Instagram">
              <img src="https://staticassets.netlify.app/public/icons/social/instagram.png" alt="Instagram" />
            </a>
            <a href="https://www.linkedin.com/company/ocasia-app" className="social-icon" aria-label="LinkedIn">
              <img src="https://staticassets.netlify.app/public/icons/social/linkedin.png" alt="LinkedIn" />
            </a>
            <a href="https://www.facebook.com/people/LamlaAI/61578006032583/" className="social-icon" aria-label="Facebook">
              <img src="https://staticassets.netlify.app/public/icons/social/facebook.png" alt="Facebook" />
            </a>
            <a href="https://x.com/lamla.ai" className="social-icon" aria-label="X/Twitter">
              <img src="https://staticassets.netlify.app/public/icons/social/twitter.png" alt="X/Twitter" />
            </a>
          </div>
        </div>
      </div>
      <div className="footer-bottom">
        <p>&copy; 2026 Ocasia. All rights reserved.</p>
        <div className="legal-links">
          <Link to="/privacy-policy">Privacy Policy</Link>
          <Link to="/terms-of-service">Terms of Service</Link>
          <Link to="/privacy-policy#cookies">Cookie Policy</Link>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
