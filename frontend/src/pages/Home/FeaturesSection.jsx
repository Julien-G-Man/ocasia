import React, { useRef, useEffect, useState } from "react";

const FEATURES = [
  {
    href: "/quiz/create",
    image: "/assets/quizzes.jpg",
    alt: "Quiz Mode",
    title: "Quiz Mode",
    description: "Automatically generates multiple-choice questions from your materials.",
  },
  {
    href: "/ai-tutor",
    image: "/assets/ai-tutor.jpg",
    alt: "AI Tutor",
    title: "AI Tutor",
    description: "Get instant answers to your questions and deeper explanations.",
  },
  {
    href: "/flashcards",
    image: "/assets/flashcards.jpeg",
    alt: "Flashcards",
    title: "Flashcards",
    description: "Create and study with AI-generated flashcards for quick review.",
  },
  {
    href: "/#exam-analyzer",
    image: "/assets/uni_exams.jpg",
    alt: "Exam Analyzer",
    title: "Exam Analysis",
    description: "Analyze uploaded exams or slides for instant feedback and topic breakdowns.",
  },
  {
    href: "/dashboard",
    image: "/assets/improve-performance.jpg",
    alt: "Performance Analytics",
    title: "Performance Analytics",
    description: "Track your progress and identify weak points to focus your efforts.",
  },
  {
    href: "/materials/community",
    image: "/assets/steam.jpg",
    alt: "Uploaded Materials",
    title: "Materials",
    description: "Don't have slides? Select from a wide range of material uploaded by our students community.",
  },
];

export default function FeaturesSection({ visible }) {
  const railRef = useRef(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const scrollRail = (direction) => {
    const rail = railRef.current;
    if (!rail) return;

    const firstCard = rail.querySelector(".feature-card");
    const cardWidth = firstCard ? firstCard.getBoundingClientRect().width : rail.clientWidth * 0.7;
    const gap = 20;
    const distance = Math.max(cardWidth + gap, rail.clientWidth * 0.82);

    rail.scrollBy({
      left: direction === "next" ? distance : -distance,
      behavior: "smooth",
    });
  };

  const scrollToCard = (index) => {
    const rail = railRef.current;
    if (!rail) return;
    const cards = rail.querySelectorAll(".feature-card");
    if (cards[index]) {
      rail.scrollTo({ left: cards[index].offsetLeft, behavior: "smooth" });
    }
  };

  // Track active dot via scroll position
  useEffect(() => {
    if (!visible) return;
    const rail = railRef.current;
    if (!rail) return;

    const handleScroll = () => {
      const cards = rail.querySelectorAll(".feature-card");
      let closest = 0;
      let minDist = Infinity;
      cards.forEach((card, i) => {
        const dist = Math.abs(card.offsetLeft - rail.scrollLeft);
        if (dist < minDist) {
          minDist = dist;
          closest = i;
        }
      });
      setActiveIndex(closest);
    };

    rail.addEventListener("scroll", handleScroll, { passive: true });
    return () => rail.removeEventListener("scroll", handleScroll);
  }, [visible]);

  // Auto-advance every 5 seconds
  useEffect(() => {
    if (!visible) return;
    const timer = setInterval(() => {
      const rail = railRef.current;
      if (!rail) return;
      const atEnd = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 4;
      if (atEnd) {
        rail.scrollTo({ left: 0, behavior: "smooth" });
      } else {
        scrollRail("next");
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section id="features" className="features-section">
      <div className="container">
        <div className="section-header section-header--center">
          <p className="section-label">FEATURES</p>
          <h2>
            Smart Features for{" "}
            <span className="brand-highlight-text">Smart Students</span>
          </h2>
        </div>

        {visible && (
          <div className="features-rail-shell">
            <div className="features-rail-controls" aria-label="Scroll feature cards">
              <button
                type="button"
                className="features-scroll-button"
                onClick={() => scrollRail("prev")}
                aria-label="Scroll to previous feature card"
              >
                ←
              </button>
              <button
                type="button"
                className="features-scroll-button"
                onClick={() => scrollRail("next")}
                aria-label="Scroll to next feature card"
              >
                →
              </button>
            </div>

            <div className="features-grid" ref={railRef}>
              {FEATURES.map((feature, index) => {
                const isFirst = index === 0;
                const isLast = index === FEATURES.length - 1;

                return (
                  <a
                    key={feature.title}
                    href={feature.href}
                    className={`feature-card${isFirst ? " feature-card--start" : ""}${isLast ? " feature-card--end" : ""}`}
                  >
                    <div className="feature-image">
                      <img src={feature.image} alt={feature.alt} />
                    </div>
                    <div className="feature-card-content">
                      <h3 className="feature-title">{feature.title}</h3>
                      <p className="feature-desc">{feature.description}</p>
                      <div className="feature-actions">
                        <span className="feature-button feature-button--primary">Try now</span>
                        <span className="feature-button feature-button--secondary">Learn More</span>
                      </div>
                    </div>
                  </a>
                );
              })}
            </div>

            <div className="features-dots">
              {FEATURES.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  className={`features-dot${i === activeIndex ? " active" : ""}`}
                  onClick={() => scrollToCard(i)}
                  aria-label={`Go to feature ${i + 1}`}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
