import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/AppShell/AppShell";
import { useAuth } from "../../context/AuthContext";
import djangoApi, { getApiErrorMessage } from "../../services/api";
import RichTextRenderer from "../../utils/richTextRenderer";
import "./Flashcards.css";

export default function FlashcardDeck() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [title, setTitle] = useState("");
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [explainingId, setExplainingId] = useState(null);
  const [explanations, setExplanations] = useState({});
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editQuestion, setEditQuestion] = useState("");
  const [editAnswer, setEditAnswer] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth/login");
      return;
    }

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await djangoApi.get(`/flashcards/deck/${id}/`);
        setCards(res.data?.cards || []);
        setTitle(res.data?.title || res.data?.subject || "");
      } catch (err) {
        console.error("Load flashcard deck failed", err);
        setError(getApiErrorMessage(err, "Failed to load deck."));
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [id, isAuthenticated, navigate]);

  const deleteDeck = async () => {
    if (!window.confirm("Delete this deck?")) return;
    setError("");
    try {
      await djangoApi.delete(`/flashcards/deck/${id}/`);
      navigate("/flashcards");
    } catch (err) {
      console.error("Delete flashcard deck failed", err);
      setError(getApiErrorMessage(err, "Failed to delete deck."));
    }
  };

  const explainCard = async (card) => {
    if (!card?.id) return;
    if (explainingId === card.id) return;
    if (explanations[card.id]) return;

    setError("");
    setExplainingId(card.id);
    try {
      const res = await djangoApi.post("/flashcards/explain/", {
        card_id: card.id,
      });
      const text = res.data?.explanation || "No explanation available.";
      setExplanations((prev) => ({ ...prev, [card.id]: text }));
    } catch (err) {
      console.error("Explain flashcard failed", err);
      setError(getApiErrorMessage(err, "Failed to explain flashcard."));
    } finally {
      setExplainingId(null);
    }
  };

  const startEdit = (card) => {
    setEditingId(card.id);
    setEditQuestion(card.question);
    setEditAnswer(card.answer);
    setError("");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditQuestion("");
    setEditAnswer("");
  };

  const saveEdit = async (cardId) => {
    if (!editQuestion.trim() || !editAnswer.trim()) {
      setError("Question and answer cannot be empty.");
      return;
    }

    setError("");
    try {
      const res = await djangoApi.post("/flashcards/cards/update/", {
        card_id: cardId,
        question: editQuestion.trim(),
        answer: editAnswer.trim(),
      });
      
      setCards(prev => prev.map(c => 
        c.id === cardId ? { ...c, question: res.data.card.question, answer: res.data.card.answer } : c
      ));
      
      // Clear cached explanation since card changed
      setExplanations(prev => {
        const updated = { ...prev };
        delete updated[cardId];
        return updated;
      });
      
      cancelEdit();
    } catch (err) {
      console.error("Update flashcard failed", err);
      setError(getApiErrorMessage(err, "Failed to update card."));
    }
  };

  const deleteCard = async (cardId) => {
    if (!window.confirm("Delete this card?")) return;
    if (deletingId) return;

    setError("");
    setDeletingId(cardId);
    try {
      await djangoApi.delete(`/flashcards/cards/${cardId}/delete/`);
      setCards(prev => prev.filter(c => c.id !== cardId));
      setExplanations(prev => {
        const updated = { ...prev };
        delete updated[cardId];
        return updated;
      });
    } catch (err) {
      console.error("Delete flashcard failed", err);
      setError(getApiErrorMessage(err, "Failed to delete card."));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <AppShell>
      <main className="fc-page">
        <section className="fc-hero fc-hero--flat compact">
          <div>
            <h1>Deck Details: {title}</h1>
            <p>{cards.length} cards in this deck</p>
          </div>
          <div className="fc-actions">
            <button className="fc-primary" onClick={() => navigate(`/flashcards/study/${id}`)}>Study Deck</button>
            <button className="fc-danger" onClick={deleteDeck}>Delete Deck</button>
          </div>
        </section>

        {loading && <p className="fc-muted">Loading cards...</p>}
        {!loading && error && <p className="fc-error">{error}</p>}
        {!loading && !cards.length && <p className="fc-empty">No cards in this deck.</p>}

        <section className="fc-grid deck-detail-grid">
          {cards.map((card) => (
            <article key={card.id} className="fc-panel fc-qa">
              {editingId === card.id ? (
                <>
                  <div className="fc-edit-form">
                    <label>
                      <strong>Question:</strong>
                      <textarea
                        value={editQuestion}
                        onChange={(e) => setEditQuestion(e.target.value)}
                        rows={3}
                      />
                    </label>
                    <label>
                      <strong>Answer:</strong>
                      <textarea
                        value={editAnswer}
                        onChange={(e) => setEditAnswer(e.target.value)}
                        rows={4}
                      />
                    </label>
                  </div>
                  <div className="fc-actions">
                    <button className="fc-primary" onClick={() => saveEdit(card.id)}>Save</button>
                    <button className="fc-secondary" onClick={cancelEdit}>Cancel</button>
                  </div>
                </>
              ) : (
                <>
                  <div className="fc-rich-card-block">
                    <div className="fc-rich-card-label">Question</div>
                    <RichTextRenderer text={card.question} className="fc-rich-text" />
                  </div>
                  <div className="fc-rich-card-block">
                    <div className="fc-rich-card-label">Answer</div>
                    <RichTextRenderer text={card.answer} className="fc-rich-text" />
                  </div>
                  <div className="fc-actions">
                    <button
                      className="fc-secondary"
                      onClick={() => explainCard(card)}
                      disabled={explainingId === card.id}
                    >
                      {explainingId === card.id ? "Explaining..." : "Explain"}
                    </button>
                    <button
                      className="fc-secondary"
                      onClick={() => startEdit(card)}
                    >
                      Edit
                    </button>
                    <button
                      className="fc-danger"
                      onClick={() => deleteCard(card.id)}
                      disabled={deletingId === card.id}
                    >
                      {deletingId === card.id ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                  {explanations[card.id] && (
                    <div className="fc-explain-box">
                      <strong>Explanation</strong>
                      <div className="fc-rich-card-block">
                        <RichTextRenderer text={explanations[card.id]} className="fc-rich-text" />
                      </div>
                    </div>
                  )}
                </>
              )}
            </article>
          ))}
        </section>
      </main>
    </AppShell>
  );
}
