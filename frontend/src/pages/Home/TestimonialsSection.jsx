import React, { useState, useEffect } from "react";

const TESTIMONIALS = [
  {
    quote:
      "Ocasia helped me turn my lecture slides into practice quizzes in seconds. It's an amazing tool!",
    name: "Christopher N",
    title: "Student @ KNUST",
    initials: "CN",
    image: null,
  },
  {
    quote:
      "We did a Clash before our midterms and it got so competitive — people were trash talking in the group chat over quiz scores. Best study session we've ever had.",
    name: "Kwame A",
    title: "Computer Science Student @ KNUST",
    initials: "KA",
    image: null,
  },
  {
    quote:
      "A platform that encourages competitive learning while supporting continuous improvement. I really enjoyed Clash with my friends.",
    name: "Jude Fiadzawoo",
    title: "Computer Science @ KNUST",
    initials: "JF",
    image: null,
  },
];

export default function TestimonialsSection({ visible }) {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (!visible) return;
    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % TESTIMONIALS.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [visible]);

  const t = TESTIMONIALS[currentIndex];

  return (
    <section id="testimonials" className="testimonials-section">
      <div className="container">
        <div className="section-header section-header--left">
          <p className="section-label">TESTIMONIALS</p>
          <h2>
            What Our Users{" "}
            <span className="brand-highlight-text">Have To Say</span>
          </h2>
        </div>
        {visible && (
          <div className="testimonials-carousel">
            <div className="testimonial-wrapper">
              <div className="testimonial-card">
                <div className="avatar-decor" aria-hidden="true"></div>
                <div className="author-avatar author-avatar--overlap">
                  {t.image ? (
                    <img src={t.image} alt={t.name} />
                  ) : (
                    <span>{t.initials}</span>
                  )}
                </div>

                <blockquote className="testimonial-quote">
                  &ldquo;{t.quote}&rdquo;
                </blockquote>

                <div className="testimonial-author no-avatar-inline">
                  <div className="author-info">
                    <p className="author-name">{t.name}</p>
                    <p className="author-title">{t.title}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="testimonials-dots">
              {TESTIMONIALS.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  className={`testimonials-dot${i === currentIndex ? " active" : ""}`}
                  onClick={() => setCurrentIndex(i)}
                  aria-label={`Show testimonial ${i + 1}`}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
