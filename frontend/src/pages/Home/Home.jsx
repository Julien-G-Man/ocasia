import React, { useEffect, useState } from "react";
import Navbar from "../../components/Navbar";
import Footer from "../../components/Footer";
import djangoApi from "../../services/api";
import "./Home.css";
import "../../App.css";
import HeroSection from "./HeroSection";
import AboutSection from "./AboutSection";
import FeaturesSection from "./FeaturesSection";
import TestimonialsSection from "./TestimonialsSection";
import GetInTouchSection from "./GetInTouchSection";

const Home = ({ user }) => {
  const [contactStatus, setContactStatus] = useState("");
  const [contactIsError, setContactIsError] = useState(false);
  const [isSendingContact, setIsSendingContact] = useState(false);

  const [isVisible, setIsVisible] = useState({
    about: false,
    features: false,
    testimonials: false,
  });

  useEffect(() => {
    const createObserver = (id, key) => {
      const el = document.getElementById(id);
      if (!el) return null;
      const obs = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setIsVisible((prev) => ({ ...prev, [key]: true }));
            obs.unobserve(entry.target);
          }
        },
        { threshold: 0.1 },
      );
      obs.observe(el);
      return obs;
    };

    const o1 = createObserver("about", "about");
    const o2 = createObserver("features", "features");
    const o3 = createObserver("testimonials", "testimonials");

    return () => {
      if (o1) o1.disconnect();
      if (o2) o2.disconnect();
      if (o3) o3.disconnect();
    };
  }, []);

  const handleContactSubmit = async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const formData = new FormData(form);
    const payload = {
      name: formData.get("name"),
      email: formData.get("email"),
      title: formData.get("title"),
      message: formData.get("message"),
    };

    const gasUrl = (import.meta.env.VITE_GAS_CONTACT_URL || "")
      .replace(/^["']|["']$/g, "")
      .trim() || null;

    try {
      setIsSendingContact(true);

      if (gasUrl) {
        const res = await fetch(gasUrl, {
          method: "POST",
          body: JSON.stringify(payload),
          headers: { "Content-Type": "text/plain" },
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || "GAS error");
      } else {
        await djangoApi.post("/dashboard/contact/", payload);
      }

      setContactIsError(false);
      setContactStatus("Thanks for reaching out. We will get back to you soon.");
      form.reset();
    } catch (err) {
      console.error("Contact form error:", err);
      if (gasUrl) {
        try {
          await djangoApi.post("/dashboard/contact/", payload);
          setContactIsError(false);
          setContactStatus("Thanks for reaching out. We will get back to you soon.");
          form.reset();
          return;
        } catch (djangoErr) {
          console.error("Django fallback error:", djangoErr);
        }
      }
      setContactIsError(true);
      setContactStatus("We could not send your message right now. Please try again.");
    } finally {
      setIsSendingContact(false);
      setTimeout(() => setContactStatus(""), 3500);
    }
  };

  return (
    <div className="site-wrapper">
      <Navbar user={user} />

      <main className="main-content">
        <HeroSection user={user} />
        <AboutSection visible={isVisible.about} />
        <FeaturesSection visible={isVisible.features} />
        <TestimonialsSection visible={isVisible.testimonials} />
        <GetInTouchSection
          onSubmit={handleContactSubmit}
          contactStatus={contactStatus}
          contactIsError={contactIsError}
          isSendingContact={isSendingContact}
        />
      </main>

      <Footer />
    </div>
  );
};

export default Home;
