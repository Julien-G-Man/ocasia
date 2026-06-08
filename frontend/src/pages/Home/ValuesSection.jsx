import React from "react";

const VALUES = [
  {
    num: "01",
    title: "Growth",
    desc: "Not just passing — genuinely improving. Every session is a step forward.",
  },
  {
    num: "02",
    title: "Deep Roots",
    desc: "Strong knowledge foundations built through active recall, not surface-level cramming.",
  },
  {
    num: "03",
    title: "Community",
    desc: "Clash battles and a shared materials library make learning a team sport.",
  },
  {
    num: "04",
    title: "Resilience",
    desc: "Tools that help you push through the hard topics and come out stronger.",
  },
];

export default function ValuesSection({ visible }) {
  return (
    <section id="values" className="values-section">
      <div className="container">
        <div className="section-header section-header--center reveal reveal-up">
          <p className="section-label">WHAT WE STAND FOR</p>
          <h2>
            Built on <span className="brand-highlight-text">Purpose</span>
          </h2>
        </div>
        {visible && (
          <div className="values-grid">
            {VALUES.map(({ num, title, desc }, i) => (
              <div key={num} className={`value-card anim-up anim-d${i + 1}`}>
                <span className="value-num">{num}</span>
                <h4 className="value-title">{title}</h4>
                <p className="value-desc">{desc}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
