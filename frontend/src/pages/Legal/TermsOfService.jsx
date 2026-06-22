import { Link } from 'react-router-dom';
import Navbar from '../../components/Navbar';
import Footer from '../../components/Footer';
import './Legal.css';

const LAST_UPDATED = 'June 22, 2026';
const CONTACT_EMAIL = 'lamlaaiteam@gmail.com';
const SITE_URL = 'https://ocasia.live';

const TermsOfService = () => (
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
          <h1>Terms of Service</h1>
          <p className="legal-hero-meta">Last updated: {LAST_UPDATED}</p>
        </div>
      </div>

      <div className="legal-content">
        <div className="legal-switch">
          <p>Looking for our Privacy Policy?</p>
          <Link to="/privacy-policy">Read Privacy Policy &rarr;</Link>
        </div>

        <div className="legal-toc">
          <h2>Contents</h2>
          <ol>
            <li><a href="#acceptance">Acceptance of Terms</a></li>
            <li><a href="#eligibility">Eligibility</a></li>
            <li><a href="#account">Your Account</a></li>
            <li><a href="#acceptable-use">Acceptable Use</a></li>
            <li><a href="#content">User-Uploaded Content</a></li>
            <li><a href="#intellectual-property">Intellectual Property</a></li>
            <li><a href="#ai-disclaimer">AI-Generated Content Disclaimer</a></li>
            <li><a href="#donations">Donations</a></li>
            <li><a href="#termination">Termination</a></li>
            <li><a href="#disclaimers">Disclaimers</a></li>
            <li><a href="#liability">Limitation of Liability</a></li>
            <li><a href="#governing-law">Governing Law</a></li>
            <li><a href="#changes">Changes to These Terms</a></li>
            <li><a href="#contact">Contact Us</a></li>
          </ol>
        </div>

        <section className="legal-section" id="acceptance">
          <h2>1. Acceptance of Terms</h2>
          <p>By accessing or using Ocasia at <a href={SITE_URL} target="_blank" rel="noopener noreferrer">{SITE_URL}</a> ("the Platform"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree, do not use the Platform.</p>
          <p>These Terms apply to all users, including registered accounts and unauthenticated visitors.</p>
        </section>

        <section className="legal-section" id="eligibility">
          <h2>2. Eligibility</h2>
          <p>You must be at least 13 years old to use Ocasia. By using the Platform, you represent that you meet this requirement. If you are under 18, you should review these Terms with a parent or guardian.</p>
        </section>

        <section className="legal-section" id="account">
          <h2>3. Your Account</h2>
          <p>You are responsible for maintaining the confidentiality of your account credentials and for all activity that occurs under your account. You agree to:</p>
          <ul>
            <li>Provide accurate and current information when registering</li>
            <li>Keep your password secure and not share it with others</li>
            <li>Notify us immediately if you suspect unauthorised access to your account</li>
          </ul>
          <p>We reserve the right to suspend or terminate accounts that violate these Terms.</p>
        </section>

        <section className="legal-section" id="acceptable-use">
          <h2>4. Acceptable Use</h2>
          <p>Ocasia is an educational tool. You agree not to use the Platform to:</p>
          <ul>
            <li>Cheat on exams or assessments in violation of your institution's academic integrity policy</li>
            <li>Upload content you do not own or have the right to use</li>
            <li>Attempt to gain unauthorised access to any part of the Platform or its infrastructure</li>
            <li>Scrape, crawl, or bulk-download content without prior written permission</li>
            <li>Distribute malware, spam, or engage in phishing</li>
            <li>Harass, impersonate, or harm other users</li>
            <li>Use the Platform for any illegal purpose under Ghanaian law or applicable international law</li>
          </ul>
        </section>

        <section className="legal-section" id="content">
          <h2>5. User-Uploaded Content</h2>
          <p>You retain ownership of content you upload (study materials, PDFs, etc.). By uploading content, you grant Ocasia a non-exclusive, royalty-free licence to store, process, and display that content solely for the purpose of providing the service to you.</p>
          <p>You must not upload:</p>
          <ul>
            <li>Content that infringes any third party's intellectual property rights</li>
            <li>Illegal, defamatory, or harmful content</li>
            <li>Personal data of others without their consent</li>
          </ul>
          <p>We reserve the right to remove content that violates these Terms without notice.</p>
        </section>

        <section className="legal-section" id="intellectual-property">
          <h2>6. Intellectual Property</h2>
          <p>All content on the Platform that is not user-generated — including the software, design, text, graphics, and AI-generated quiz content — is owned by or licensed to Ocasia. You may not reproduce, distribute, or create derivative works from it without our prior written consent.</p>
        </section>

        <section className="legal-section" id="ai-disclaimer">
          <h2>7. AI-Generated Content Disclaimer</h2>
          <p>Ocasia uses the <strong>OpenAI API</strong> and <strong>Anthropic (Claude) API</strong> to generate quizzes, flashcards, explanations, and AI tutor responses. When you use these features, your study content (materials, questions, chat messages) is sent to these providers to generate a response.</p>
          <p>While we strive for accuracy, <strong>AI-generated content may contain errors or inaccuracies</strong>. You should not rely solely on AI-generated content for critical academic decisions. Always verify important information with authoritative sources such as textbooks, official syllabi, or your instructors.</p>
        </section>

        <section className="legal-section" id="donations">
          <h2>8. Donations</h2>
          <p>Ocasia accepts voluntary donations to support platform development. Donations are processed by Paystack and are <strong>non-refundable</strong> unless required by applicable law. Donations do not constitute a purchase of any product, service, or equity in Ocasia.</p>
        </section>

        <section className="legal-section" id="termination">
          <h2>9. Termination</h2>
          <p>We may suspend or terminate your access to the Platform at our discretion, with or without notice, if we believe you have violated these Terms or if continuing to provide access would be unlawful.</p>
          <p>You may delete your account at any time by contacting us at <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. Upon deletion, your personal data will be removed in accordance with our Privacy Policy.</p>
        </section>

        <section className="legal-section" id="disclaimers">
          <h2>10. Disclaimers</h2>
          <p>Ocasia is provided <strong>"as is"</strong> and <strong>"as available"</strong> without warranties of any kind, express or implied, including but not limited to warranties of merchantability, fitness for a particular purpose, or non-infringement.</p>
          <p>We do not guarantee that the Platform will be uninterrupted, error-free, or free from harmful components. We may modify, suspend, or discontinue features at any time.</p>
        </section>

        <section className="legal-section" id="liability">
          <h2>11. Limitation of Liability</h2>
          <p>To the maximum extent permitted by applicable law, Ocasia and its creators shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising from your use of — or inability to use — the Platform, even if we have been advised of the possibility of such damages.</p>
          <p>Our total liability to you for any claim arising out of these Terms shall not exceed the greater of (a) the amount you paid us in the 12 months before the claim arose, or (b) GHS 50.</p>
        </section>

        <section className="legal-section" id="governing-law">
          <h2>12. Governing Law</h2>
          <p>These Terms are governed by and construed in accordance with the laws of the Republic of Ghana, including the <strong>Electronic Transactions Act, 2008 (Act 772)</strong>, which gives legal recognition to electronic agreements and records.</p>
          <p>Your personal data is processed in accordance with the <strong>Data Protection Act, 2012 (Act 843)</strong>. See our <Link to="/privacy-policy">Privacy Policy</Link> for details.</p>
          <p>Any disputes arising from these Terms shall be subject to the exclusive jurisdiction of the courts of Ghana.</p>
        </section>

        <section className="legal-section" id="changes">
          <h2>13. Changes to These Terms</h2>
          <p>We may update these Terms from time to time. We will notify registered users of material changes via email or an in-app notice. The "Last updated" date at the top of this page reflects the most recent revision.</p>
          <p>Continued use of Ocasia after the revised Terms take effect constitutes your acceptance of those changes.</p>
        </section>

        <section className="legal-section" id="contact">
          <h2>14. Contact Us</h2>
          <p>If you have questions about these Terms, please contact us:</p>
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

export default TermsOfService;
