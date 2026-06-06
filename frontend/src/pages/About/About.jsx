import React, { useEffect, useState } from 'react';
import Navbar from '../../components/Navbar';
import Footer from '../../components/Footer';
import './About.css';

const About = ({ user }) => {
    const [isVisible, setIsVisible] = useState({
        principles: false,
        cta: false
    });

    useEffect(() => {
        // Lazy load principles section
        const principlesObserver = new IntersectionObserver(([entry]) => {
            if (entry.isIntersecting) {
                setIsVisible(prev => ({ ...prev, principles: true }));
                principlesObserver.unobserve(entry.target);
            }
        }, { threshold: 0.1 });

        const principlesEl = document.getElementById("principles-section");
        if (principlesEl) {
            principlesObserver.observe(principlesEl);
        }

        // Lazy load CTA section
        const ctaObserver = new IntersectionObserver(([entry]) => {
            if (entry.isIntersecting) {
                setIsVisible(prev => ({ ...prev, cta: true }));
                ctaObserver.unobserve(entry.target);
            }
        }, { threshold: 0.1 });

        const ctaEl = document.getElementById("cta-section");
        if (ctaEl) {
            ctaObserver.observe(ctaEl);
        }

        return () => {
            principlesObserver.disconnect();
            ctaObserver.disconnect();
        };
    }, []);

    return (
        <div className="site-wrapper">
            <Navbar user={user} />
            <main className="about-page">
                <section className="about-hero" data-aos="fade-up">
                    <div className="hero-bg-overlay"></div>
                    <div className="about-hero-content container">
                        <h1 className="about-hero-title">
                            About <span className="highlight">Ocasia</span>
                        </h1>
                        <p className="about-hero-desc">
                            <strong>Ocasia</strong> (formerly <strong>Lamla AI</strong>) is a smart exam preparation platform designed to help you study with intention, not panic.<br></br>
                            Ocasia replaces guesswork with guided, personalized study by combining AI-generated quizzes, real-time feedback, and performance insights.<br></br>
                            <b>Study Smarter. Perform Better.</b>
                        </p>
                    </div>                    
                </section>

                <div className="about-content-wrapper">
                    <div className="section-header">
                        <div className="section-badge">
                            <span>✨ Principles</span>
                        </div>
                        <h2>Our Core<span className="highlight"> Principles</span></h2>
                        <p>Learn about the mission, vision, and values that drive us.</p>
                    </div>

                    <div className="about-container" id="principles-section">
                        {isVisible.principles && (
                            <section className="about-page-section about-tabs-container" data-aos="fade-up" data-aos-delay="200">
                                <div className="about-tabs" id="aboutTabs">
                                    <button className="about-tab active" data-tab="mission">Mission</button>
                                    <button className="about-tab" data-tab="vision">Vision</button>
                                    <button className="about-tab" data-tab="values">Values</button>
                                    <button className="about-tab" data-tab="offers">What We Offer</button>
                                </div>

                                <div className="about-tab-content active" id="mission-tab-content">
                                    <div className="content-list-group">
                                        <h3><span className="emoji">🎯</span> Our Mission</h3>
                                        <p>To empower students to learn deeply, track their understanding, and focus on what matters most—across their academic journey, from early prep to final revision.</p>
                                        <ul>
                                            <li><i className="fas fa-check-circle"></i> Replace guesswork with guided, personalized study</li>
                                            <li><i className="fas fa-check-circle"></i> Assess knowledge and strengthen weak areas</li>
                                            <li><i className="fas fa-check-circle"></i> Build mastery through active recall, not cramming</li>
                                            <li><i className="fas fa-check-circle"></i> Prepare with intention, not panic</li>
                                        </ul>
                                    </div>
                                </div>

                                <div className="about-tab-content" id="vision-tab-content">
                                    <div className="content-list-group">
                                        <h3><span className="emoji">🚀</span> Our Vision</h3>
                                        <p>To redefine academic readiness—starting from Africa, for the world—by making purposeful, AI-powered study accessible to every student.</p>
                                        <ul>
                                            <li><i className="fas fa-check-circle"></i> Enable students to prepare smarter, not just harder</li>
                                            <li><i className="fas fa-check-circle"></i> Support mastery, not just survival</li>
                                            <li><i className="fas fa-check-circle"></i> Scale globally, starting with high-syllabus, paper-based exam systems</li>
                                        </ul>
                                    </div>
                                </div>

                                <div className="about-tab-content" id="values-tab-content">
                                    <div className="content-list-group">
                                        <h3><span className="emoji">🧭</span> Our Values</h3>
                                        <ul>
                                            <li><i className="fas fa-check-circle"></i> Clarity over confusion: Guided, purposeful study</li>
                                            <li><i className="fas fa-check-circle"></i> Growth over shortcuts: Mastery through active recall</li>
                                            <li><i className="fas fa-check-circle"></i> Focus over panic: Tools to support real learning</li>
                                            <li><i className="fas fa-check-circle"></i> Integrity: Ocasia is not a cramming or cheat tool</li>
                                        </ul>
                                    </div>
                                </div>

                                <div className="about-tab-content" id="offers-tab-content">
                                    <div className="content-list-group">
                                        <h3><span className="emoji">💡</span> What Ocasia Offers</h3>
                                        <ul>
                                            <li><i className="fas fa-check-circle"></i> Upload study materials (PDF/text) for quiz generation</li>
                                            <li><i className="fas fa-check-circle"></i> AI-generated quizzes with instant feedback</li>
                                            <li><i className="fas fa-check-circle"></i> Performance tracking with color-coded insights</li>
                                            <li><i className="fas fa-check-circle"></i> Subject and topic selection for focused study</li>
                                            <li><i className="fas fa-check-circle"></i> A multilingual assistant copilot to support you on your journey to success</li>
                                        </ul>
                                        <p>Ocasia is not a shortcut or a cheat—it's a smart compass for students who want to prepare better, not later.</p>
                                    </div>
                                </div>
                            </section>
                        )}

                        <section id="cta-section" className="section-header" data-aos="fade-up" data-aos-delay="300">
                            <h2>🤝 <span className="highlight"> Join the </span>Journey</h2>
                            <p>If you want to prepare with purpose, not panic—Ocasia was built for you.</p>
                            <p>This is more than a platform. It's a toolset. A mindset. A movement.</p>
                            <p><strong className="highlight-text">Study Smarter. Perform Better.</strong></p>
                            {isVisible.cta && (
                                <div className="hero-btns">
                                    {!user ? (
                                        <a href="/account/signup" className="hero-btn primary">Get Started</a>
                                    ) : (
                                        <a href="/quiz/create" className="hero-btn primary">Start Practicing</a>
                                    )}
                                </div>
                            )}
                        </section>

                    </div>
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default About;