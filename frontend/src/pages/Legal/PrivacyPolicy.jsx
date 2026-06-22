import { Link } from 'react-router-dom';
import Navbar from '../../components/Navbar';
import Footer from '../../components/Footer';
import './Legal.css';

const LAST_UPDATED = 'June 22, 2026';
const CONTACT_EMAIL = 'lamlaaiteam@gmail.com';
const SITE_URL = 'https://ocasia.live';

const PrivacyPolicy = () => (
  <div className="site-wrapper">
    <Navbar />
    <main className="legal-page">
      <div className="legal-hero">
        <span className="legal-hero-plus" style={{top:'22px',left:'44px'}}>+</span>
        <span className="legal-hero-plus" style={{top:'22px',right:'64px'}}>+</span>
        <span className="legal-hero-plus" style={{bottom:'28px',left:'108px'}}>+</span>
        <span className="legal-hero-plus" style={{bottom:'28px',right:'108px'}}>+</span>
        <div className="legal-hero-inner">
          <span className="legal-hero-label">Legal</span>
          <h1>Privacy Policy</h1>
          <p className="legal-hero-meta">Last updated: {LAST_UPDATED}</p>
        </div>
      </div>

      <div className="legal-content">
        <div className="legal-switch">
          <p>Looking for our Terms of Service?</p>
          <Link to="/terms-of-service">Read Terms of Service &rarr;</Link>
        </div>

        <div className="legal-toc">
          <h2>Contents</h2>
          <ol>
            <li><a href="#information-we-collect">Information We Collect</a></li>
            <li><a href="#how-we-use-your-information">How We Use Your Information</a></li>
            <li><a href="#third-party-services">Third-Party Services</a></li>
            <li><a href="#data-storage-and-security">Data Storage &amp; Security</a></li>
            <li><a href="#your-rights">Your Rights</a></li>
            <li><a href="#cookies">Cookies &amp; Local Storage</a></li>
            <li><a href="#children">Children's Privacy</a></li>
            <li><a href="#ghana-law">Ghana Data Protection Law</a></li>
            <li><a href="#changes">Changes to This Policy</a></li>
            <li><a href="#contact">Contact Us</a></li>
          </ol>
        </div>

        <section className="legal-section" id="information-we-collect">
          <h2>1. Information We Collect</h2>
          <p>We collect information you provide directly and information generated as you use Ocasia.</p>
          <p><strong>Account information:</strong> When you register, we collect your name, email address, and a hashed password. If you sign in with Google, we receive your name and email from Google — we do not receive or store your Google password.</p>
          <p><strong>Study data:</strong> Quiz attempts, scores, subject selections, flashcard decks, and study material uploads are stored to power your dashboard, performance insights, and AI recommendations.</p>
          <p><strong>Uploaded content:</strong> Files you upload (PDFs, images) for quiz generation or materials are stored on Cloudinary. We do not use your uploaded content for any purpose beyond providing the service to you.</p>
          <p><strong>Communications:</strong> If you contact us by email or through our contact form, we retain your messages to respond to you.</p>
          <p><strong>Donation information:</strong> If you donate, payment is processed by Paystack. We receive confirmation of your donation (amount, reference) but not your full card details.</p>
        </section>

        <section className="legal-section" id="how-we-use-your-information">
          <h2>2. How We Use Your Information</h2>
          <ul>
            <li>To provide, maintain, and improve the Ocasia platform</li>
            <li>To generate personalised quizzes, flashcards, and study recommendations</li>
            <li>To show you your performance history, weak areas, and study trends</li>
            <li>To send transactional emails (account verification, password reset)</li>
            <li>To send product update newsletters, if you subscribed</li>
            <li>To detect and prevent fraud, abuse, or violations of our Terms</li>
            <li>To respond to support requests and feedback</li>
          </ul>
          <p>We do not sell your personal data to third parties.</p>
        </section>

        <section className="legal-section" id="third-party-services">
          <h2>3. Third-Party Services</h2>
          <p>Ocasia integrates the following third-party services to operate. Each has its own privacy policy.</p>
          <ul>
            <li><strong>Google OAuth</strong> — Used for "Sign in with Google". Governed by <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google's Privacy Policy</a>.</li>
            <li><strong>Cloudinary</strong> — Cloud storage and CDN for uploaded files and images. Governed by <a href="https://cloudinary.com/privacy" target="_blank" rel="noopener noreferrer">Cloudinary's Privacy Policy</a>.</li>
            <li><strong>Render</strong> — Hosts our backend API. Data is processed on Render's infrastructure.</li>
            <li><strong>Vercel</strong> — Hosts our frontend. Traffic data may be processed by Vercel.</li>
            <li><strong>OpenAI</strong> — Powers quiz generation, flashcards, and AI tutor responses. Your study content may be sent to OpenAI's API to generate responses. Governed by <a href="https://openai.com/policies/privacy-policy" target="_blank" rel="noopener noreferrer">OpenAI's Privacy Policy</a>.</li>
            <li><strong>Anthropic (Claude)</strong> — Used alongside OpenAI for AI-powered features. Governed by <a href="https://www.anthropic.com/privacy" target="_blank" rel="noopener noreferrer">Anthropic's Privacy Policy</a>.</li>
            <li><strong>Paystack</strong> — Processes donations. We do not store card information. Governed by <a href="https://paystack.com/privacy" target="_blank" rel="noopener noreferrer">Paystack's Privacy Policy</a>.</li>
            <li><strong>EmailJS </strong> — Used to send transactional and contact-form emails.</li>
            <li><strong>Redis (Upstash)</strong> — Used for short-lived response caching. No personal data is permanently stored in Redis.</li>
          </ul>
        </section>

        <section className="legal-section" id="data-storage-and-security">
          <h2>4. Data Storage &amp; Security</h2>
          <p>Your account data is stored in a PostgreSQL database hosted on <a href="https://neon.tech" target="_blank" rel="noopener noreferrer">Neon DB</a>. Passwords are hashed using Django's PBKDF2 algorithm and are never stored in plain text.</p>
          <p>We use HTTPS (TLS) for all data in transit. Sensitive environment variables (API keys, secrets) are never exposed to the frontend.</p>
          <p>While we take reasonable precautions, no system is completely secure. We encourage you to use a strong, unique password for your account.</p>
        </section>

        <section className="legal-section" id="your-rights">
          <h2>5. Your Rights</h2>
          <p>You have the right to:</p>
          <ul>
            <li><strong>Access</strong> the personal data we hold about you</li>
            <li><strong>Correct</strong> inaccurate data via your profile settings</li>
            <li><strong>Delete</strong> your account and associated data by emailing us</li>
            <li><strong>Unsubscribe</strong> from newsletter emails at any time</li>
            <li><strong>Export</strong> your study data — contact us and we will assist</li>
          </ul>
          <p>You also have the right to lodge a complaint with Ghana's <strong>Data Protection Commission (DPC)</strong> if you believe your rights under the Data Protection Act, 2012 (Act 843) have been violated.</p>
          <p>To exercise any of these rights, email us at <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. In line with Act 843, we will respond within <strong>21 days</strong>.</p>
        </section>

        <section className="legal-section" id="cookies">
          <h2>6. Cookies &amp; Local Storage</h2>
          <p>Ocasia uses browser <strong>localStorage</strong> (not cookies) to persist your session token and a small number of user preferences. No tracking cookies or advertising cookies are used.</p>
          <p>Third-party services (Google, Cloudinary) may set their own cookies as part of their normal operation. Refer to their respective privacy policies for details.</p>
        </section>

        <section className="legal-section" id="children">
          <h2>7. Children's Privacy</h2>
          <p>Ocasia is intended for students aged 13 and older. We do not knowingly collect personal data from children under 13. If you believe a child under 13 has provided us with personal data, please contact us and we will delete it promptly.</p>
        </section>

        <section className="legal-section" id="ghana-law">
          <h2>8. Ghana Data Protection Law</h2>
          <p>Ocasia operates in compliance with Ghana's <strong>Data Protection Act, 2012 (Act 843)</strong>, which governs the collection, use, and protection of personal data. Under Act 843, we act as a data controller and are obligated to:</p>
          <ul>
            <li>Process personal data lawfully, fairly, and transparently</li>
            <li>Collect data only for specified, explicit, and legitimate purposes</li>
            <li>Retain data only for as long as necessary for those purposes</li>
            <li>Implement appropriate security safeguards to protect your data</li>
            <li>Respond to data subject requests within 21 days</li>
          </ul>
          <p>If you believe your data protection rights under Act 843 have been violated, you may file a complaint with the <strong>Data Protection Commission of Ghana</strong>.</p>
        </section>

        <section className="legal-section" id="changes">
          <h2>9. Changes to This Policy</h2>
          <p>We may update this Privacy Policy from time to time. We will notify registered users of material changes via email or an in-app notice. The "Last updated" date at the top of this page will always reflect the most recent revision.</p>
          <p>Continued use of Ocasia after changes take effect constitutes acceptance of the revised policy.</p>
        </section>

        <section className="legal-section" id="contact">
          <h2>10. Contact Us</h2>
          <p>If you have questions, concerns, or requests regarding this Privacy Policy or your data, please reach out:</p>
          <div className="legal-contact-box">
            <p><strong>Ocasia (formerly Lamla AI)</strong></p>
            <p>Email: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
            <p>Website: <a href={SITE_URL} target="_blank" rel="noopener noreferrer">{SITE_URL}</a></p>
          </div>
        </section>
      </div>
    </main>
    <Footer />
  </div>
);

export default PrivacyPolicy;
