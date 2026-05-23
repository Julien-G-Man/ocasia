import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../../components/AppShell/AppShell";
import { useAuth } from "../../context/AuthContext";
import djangoApi from "../../services/api";
import "./Flashcards.css";
import "../Dashboards/Dashboard.css";

export default function FlashcardDecks() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [decks, setDecks] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadDecks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await djangoApi.get("/flashcards/decks/");
      setDecks(res.data?.decks || []);
    } catch (err) {
      console.error("Load flashcard decks failed", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth/login");
      return;
    }
    loadDecks();
  }, [isAuthenticated, navigate, loadDecks]);

  const handleDelete = async (deckId) => {
    if (!window.confirm("Delete this deck?")) return;
    try {
      await djangoApi.delete(`/flashcards/decks/${deckId}/`);
      setDecks((prev) => prev.filter((d) => d.id !== deckId));
    } catch (err) {
      console.error("Delete flashcard deck failed", err);
    }
  };

  const totalDue = decks.reduce((sum, d) => sum + (d.due_today || 0), 0);

  return (
    <AppShell>
      <main className="db-main">
          <section className="fc-hero fc-hero--flat">
            <div>
              <h1>Flashcard Decks</h1>
              <p>Build and review decks with a daily due-card loop.</p>
            </div>
            <div className="fc-hero-stats">
              <div>
                <strong>{decks.length}</strong>
                <span>Decks</span>
              </div>
              <div>
                <strong>{totalDue}</strong>
                <span>Due Today</span>
              </div>
            </div>
            <button className="fc-primary" onClick={() => navigate("/flashcards/create")}>Create Deck</button>
          </section>

          {loading && <p className="fc-muted">Loading decks...</p>}
          {!loading && !decks.length && <p className="fc-empty">No decks yet. Create your first deck.</p>}

          <section className="fc-grid decks-grid">
            {decks.map((deck) => (
              <article key={deck.id} className="fc-panel fc-deck-item">
                <h3>{deck.title}</h3>
                <div className="fc-meta-row">
                  <span>{deck.card_count || 0} cards</span>
                  <span className="fc-due-pill">{deck.due_today || 0} due today</span>
                </div>
                <div className="fc-actions">
                  <button className="fc-primary" onClick={() => navigate(`/flashcards/study/${deck.id}`)}>Study</button>
                  <button className="fc-secondary" onClick={() => navigate(`/flashcards/deck/${deck.id}`)}>View Deck</button>
                  <button className="fc-danger" onClick={() => handleDelete(deck.id)}>Delete</button>
                </div>
              </article>
            ))}
          </section>
      </main>
    </AppShell>
  );
}
