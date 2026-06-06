import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import Navbar from "../../components/Navbar";
import Footer from "../../components/Footer";
import { useAuth } from "../../context/AuthContext";
import { verifyDonation } from "../../services/payments";
import "./DonateThankyou.css";

const DonateThankyou = () => {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const reference = searchParams.get("reference") || searchParams.get("trxref");

  const [state, setState]   = useState("loading");
  const [amount, setAmount] = useState(null);

  useEffect(() => {
    if (!reference) { setState("no_ref"); return; }

    verifyDonation(reference)
      .then(({ data }) => {
        if (data.status === "success") { setAmount(data.amount); setState("success"); }
        else setState("failed");
      })
      .catch(() => setState("failed"));
  }, [reference]);

  return (
    <div className="site-wrapper">
      <Navbar user={user} />
      <main className="ty-page">

        {state === "loading" && (
          <div className="ty-center">
            <div className="ty-spinner" />
            <p className="ty-hint">Confirming your payment…</p>
          </div>
        )}

        {state === "success" && (
          <div className="ty-split">
            <div className="ty-left">
              <p className="donate-eyebrow">DONATION CONFIRMED</p>
              <h1 className="ty-heading">
                Thank you for<br />
                <span className="brand-highlight-text">believing in us.</span>
              </h1>
              <p className="ty-body">
                Your donation{amount ? ` of GHS ${amount}` : ""} was received.
                You're helping keep Ocasia free for every student — that means
                everything to us.
              </p>
              <div className="ty-actions">
                <Link to="/dashboard" className="ty-btn-primary">
                  Back to Dashboard →
                </Link>
                <Link to="/quiz/create" className="ty-btn-secondary">
                  Start a Quiz
                </Link>
              </div>
            </div>
            <div className="ty-right">
              <div className="ty-badge">
                <span className="ty-check">✓</span>
                <p className="ty-badge-label">Payment received</p>
                {amount && <p className="ty-badge-amount">GHS {amount}</p>}
              </div>
              <ul className="ty-perks">
                <li>You're now an Ocasia supporter</li>
                <li>Donor status permanently on your profile</li>
                <li>Platform stays free because of you</li>
              </ul>
            </div>
          </div>
        )}

        {state === "failed" && (
          <div className="ty-center ty-failed">
            <div className="ty-status-icon failed">✕</div>
            <p className="donate-eyebrow">PAYMENT NOT CONFIRMED</p>
            <h1 className="ty-heading">Something went wrong.</h1>
            <p className="ty-body">
              We could not confirm your payment. If you were charged, please
              contact us with your reference:<br />
              <code className="ty-ref">{reference}</code>
            </p>
            <div className="ty-actions ty-actions--center">
              <Link to="/donate" className="ty-btn-primary">Try again →</Link>
            </div>
          </div>
        )}

        {state === "no_ref" && (
          <div className="ty-center">
            <div className="ty-status-icon neutral">?</div>
            <p className="donate-eyebrow">NOTHING TO CONFIRM</p>
            <h1 className="ty-heading">No payment reference.</h1>
            <p className="ty-body">
              This page is only accessible after completing a payment.
            </p>
            <div className="ty-actions ty-actions--center">
              <Link to="/donate" className="ty-btn-primary">Go to Donate →</Link>
            </div>
          </div>
        )}

      </main>
      <Footer />
    </div>
  );
};

export default DonateThankyou;
