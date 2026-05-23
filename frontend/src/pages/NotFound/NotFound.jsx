import React from "react";
import { Link } from "react-router-dom";
import Navbar from "../../components/Navbar";

const NotFound = () => {
  return (
    <div className="not-found-page" style={{
      backgroundImage: "linear-gradient(rgba(248, 250, 252, 0.9), rgba(248, 250, 252, 0.9)), url('/assets/not-found.webp')", 
      backgroundSize: "cover",
      backgroundPosition: "center",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column"
    }}>
      <Navbar />
      
      <div style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "#0f172a",
        textAlign: "center",
        padding: "0 20px"
      }}>
        <h2 style={{ fontSize: "1.8rem", marginBottom: "15px" }}>Oops! You've strayed off the path.</h2>
        <p style={{ marginBottom: "30px", maxWidth: "600px", fontSize: "1.1rem", opacity: 0.9 }}>
          The page you are looking for might have been removed, or is temporarily unavailable.
        </p>
        <Link 
          to="/" 
          className="btn" 
          style={{ 
            padding: "14px 32px", 
            marginTop: "100px",
            marginBottom: "20px",
            backgroundColor: "#2563eb",
            color: "#fff",
            fontWeight: "bold",
            borderRadius: "8px",
            textDecoration: "none",
            fontSize: "1rem",
            transition: "all 0.3s ease",
            backdropFilter: "blur(5px)",
            boxShadow: "0 4px 15px rgba(37, 99, 235, 0.25)"
          }}
          onMouseOver={(e) => {
            e.target.style.backgroundColor = "#1d4ed8";
            e.target.style.color = "white";
          }}
          onMouseOut={(e) => {
            e.target.style.backgroundColor = "#2563eb";
            e.target.style.color = "white";
          }}
        >
          Return to Home
        </Link>
      </div>
    </div>
  );
};

export default NotFound;