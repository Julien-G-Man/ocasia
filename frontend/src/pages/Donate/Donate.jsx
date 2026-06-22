import { useState } from "react";
import Navbar from "../../components/Navbar";
import Footer from "../../components/Footer";
import { useAuth } from "../../context/AuthContext";
import { initiateDonation } from "../../services/payments";
import { getApiErrorMessage } from "../../services/api";
import "./Donate.css";

const AMOUNT_TILES = [
  { value: 5,  label: "Buy us a coffee"  },
  { value: 10, label: "Keep the lights on" },
  { value: 20, label: "Fund a feature"   },
  { value: 50, label: "Sponsor a student" },
];

const Donate = () => {
  const { user, isAuthenticated } = useAuth();

  const [amount, setAmount]   = useState("");
  const [email, setEmail]     = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const handleTile = (val) => setAmount(String(val));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const parsed = parseFloat(amount);
    if (!parsed || parsed < 5) {
      setError("Please enter an amount of at least 5 GHS.");
      return;
    }
    if (!isAuthenticated && !email.trim()) {
      setError("Please enter your email address.");
      return;
    }

    setLoading(true);
    try {
      const { data } = await initiateDonation({
        amount: parsed,
        email: isAuthenticated ? undefined : email.trim(),
      });
      window.location.href = data.authorization_url;
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not start payment. Please try again."));
      setLoading(false);
    }
  };

  return (
    <div className="site-wrapper">
      <Navbar user={user} />
      <main className="donate-page">

        <div className="donate-split">

          {/* ── Left — image panel ── */}
          <div className="donate-left">
            <img
              src="/assets/highfive-with-teacher.jpg"
              alt="Student high-fiving a teacher"
              className="donate-left-img"
            />
            <div className="donate-left-overlay">
              <div className="donate-left-body">
                <p className="donate-eyebrow">YOUR IMPACT</p>
                <h2 className="donate-left-heading">
                  Every contribution keeps this free for every student.
                </h2>
                <ul className="donate-impact-list">
                  <li>Keeps the platform free for students</li>
                  <li>Funds new AI features that actually help</li>
                  <li>Supports ongoing development & hosting</li>
                </ul>
              </div>
            </div>
          </div>

          {/* ── Right — form panel ── */}
          <div className="donate-right">
            <div className="donate-right-inner">
              <p className="donate-eyebrow">SUPPORT OCASIA</p>
              <h1 className="donate-title">
                Every <span className="brand-highlight-text">GHS</span> counts.
              </h1>
              <p className="donate-subtitle">
                One-time. Any amount. No account required.
              </p>

              <form onSubmit={handleSubmit} className="donate-form">

                <div className="donate-tile-grid">
                  {AMOUNT_TILES.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      className={`donate-tile ${parseFloat(amount) === value ? "active" : ""}`}
                      onClick={() => handleTile(value)}
                    >
                      <span className="tile-amount">GHS {value}</span>
                      <span className="tile-label">{label}</span>
                    </button>
                  ))}
                </div>

                <div className="donate-divider">
                  <span>or enter a custom amount</span>
                </div>

                <div className="donate-input-wrap">
                  <span className="donate-currency">GHS</span>
                  <input
                    type="number"
                    min="5"
                    step="1"
                    placeholder="0.00"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    required
                  />
                </div>

                {!isAuthenticated && (
                  <input
                    className="donate-email-input"
                    type="email"
                    placeholder="Your email address"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                )}

                {error && <p className="donate-error">{error}</p>}

                <button
                  type="submit"
                  className="donate-btn"
                  disabled={loading}
                >
                  {loading ? "Redirecting to payment…" : "Donate Now →"}
                </button>

              </form>

              <p className="donate-secure">
                🔒 Secured by Paystack · We never store card details
              </p>
            </div>
          </div>

        </div>

      </main>
      <Footer />
    </div>
  );
};

export default Donate;
