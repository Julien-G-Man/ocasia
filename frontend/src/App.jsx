import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import "./App.css";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider } from "./context/AuthContext";
import { DJANGO_WARMUP_ENDPOINT, FASTAPI_HEALTH_ENDPOINT } from "./services/api";
import Home from "./pages/Home/Home";
import Login from "./pages/Login/Login";
import Signup from "./pages/Signup/Signup";
import VerifyEmail from "./pages/Auth/VerifyEmail";
import ForgotPassword from "./pages/Auth/ForgotPassword";
import ResetPassword from "./pages/Auth/ResetPassword";
import Dashboard from "./pages/Dashboards/Dashboard";
import AdminDashboard from "./pages/Dashboards/AdminDashboard";
import AdminUserDetails from "./pages/Dashboards/AdminUserDetails";
import AdminActivity from "./pages/Dashboards/AdminActivity";
import AdminRatings from "./pages/Dashboards/AdminRatings";
import CreateQuiz from "./pages/Quiz/CreateQuiz";
import Quiz from "./pages/Quiz/Quiz";
import QuizResults from "./pages/Quiz/QuizResults";
import QuizHistory from "./pages/Quiz/QuizHistory";
import FlashcardDecks from "./pages/Flashcards/FlashcardDecks";
import FlashcardCreate from "./pages/Flashcards/FlashcardCreate";
import FlashcardDeck from "./pages/Flashcards/FlashcardDeck";
import FlashcardStudy from "./pages/Flashcards/FlashcardStudy";
import Chatbot from "./pages/Chatbot/Chatbot";
import Profile from "./pages/UserProfile/Profile";
import Materials from "./pages/Materials/CommunityMaterials";
import MaterialsMine from "./pages/Materials/MyMaterials";
import MaterialUpload from "./pages/Materials/MaterialUpload";
import NotFound from "./pages/NotFound/NotFound";
import Donate from "./pages/Donate/Donate";
import DonateThankyou from "./pages/Donate/DonateThankyou";

const WAKE_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

function App() {
  useEffect(() => {
    const wakeServices = async () => {
      await Promise.allSettled([
        fetch(DJANGO_WARMUP_ENDPOINT, { method: "GET", credentials: "omit" }),
        fetch(FASTAPI_HEALTH_ENDPOINT, { method: "GET", credentials: "omit" }),
      ]);
    };

    wakeServices();
    const intervalId = setInterval(wakeServices, WAKE_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <ThemeProvider>
      <AuthProvider>
        <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/" element={<Home />} />

            <Route path="/auth/login" element={<Login />} />
            <Route path="/auth/signup" element={<Signup />} />
            <Route path="/auth/verify-email" element={<VerifyEmail />} />
            <Route path="/auth/forgot-password" element={<ForgotPassword />} />
            <Route path="/auth/reset-password" element={<ResetPassword />} />

            <Route path="/auth" element={<Navigate to="/auth/login" replace />} />
            <Route path="/login" element={<Navigate to="/auth/login" replace />} />
            <Route path="/signup" element={<Navigate to="/auth/signup" replace />} />
            <Route path="/verify-email" element={<Navigate to="/auth/verify-email" replace />} />

            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/admin-dashboard" element={<AdminDashboard />} />
            <Route path="/admin-dashboard/user/:id" element={<AdminUserDetails />} />
            <Route path="/admin-dashboard/activity" element={<AdminActivity />} />
            <Route path="/admin-dashboard/ratings" element={<AdminRatings />} />
            <Route path="/profile" element={<Profile />} />

            <Route path="/quiz" element={<QuizHistory />} />
            <Route path="/quiz/create" element={<CreateQuiz />} />
            <Route path="/quiz/play" element={<Quiz />} />
            <Route path="/quiz/results" element={<QuizResults />} />

            <Route path="/flashcards" element={<FlashcardDecks />} />
            <Route path="/flashcards/create" element={<FlashcardCreate />} />
            <Route path="/flashcards/deck/:id" element={<FlashcardDeck />} />
            <Route path="/flashcards/study/:id" element={<FlashcardStudy />} />
            <Route path="/flashcard" element={<Navigate to="/flashcards" replace />} />

            <Route path="/donate" element={<Donate />} />
            <Route path="/donate/thank-you" element={<DonateThankyou />} />

            <Route path="/materials" element={<Navigate to="/materials/community" replace />} />
            <Route path="/materials/community" element={<Materials />} />
            <Route path="/materials/mine" element={<MaterialsMine />} />
            <Route path="/materials/upload" element={<MaterialUpload />} />

            <Route path="/ai-tutor" element={<Chatbot />} />
            <Route path="/ai" element={<Navigate to="/ai-tutor" replace />} />
            <Route path="/chat" element={<Navigate to="/ai-tutor" replace />} />
            <Route path="/chatbot" element={<Navigate to="/ai-tutor" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Router>
      </AuthProvider>
      </ThemeProvider>
    </GoogleOAuthProvider>
  );
}

export default App;