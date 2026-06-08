import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from "react-router-dom";
import { useEffect } from "react";
import "./App.css";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { DJANGO_WARMUP_ENDPOINT, FASTAPI_HEALTH_ENDPOINT } from "./services/api";
import Home from "./pages/Home/Home";
import About from "./pages/About/About";
import Login from "./pages/Login/Login";
import Signup from "./pages/Signup/Signup";
import VerifyEmail from "./pages/Auth/VerifyEmail";
import ForgotPassword from "./pages/Auth/ForgotPassword";
import ResetPassword from "./pages/Auth/ResetPassword";
import Dashboard from "./pages/Dashboards/Dashboard";
import AdminOverview from "./pages/Dashboards/AdminOverview";
import AdminUsers from "./pages/Dashboards/AdminUsers";
import AdminContent from "./pages/Dashboards/AdminContent";
import AdminSettings from "./pages/Dashboards/AdminSettings";
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
import AdminAppShell from "./components/AppShell/AdminAppShell";
import Materials from "./pages/Materials/CommunityMaterials";
import MaterialsMine from "./pages/Materials/MyMaterials";
import MaterialUpload from "./pages/Materials/MaterialUpload";
import NotFound from "./pages/NotFound/NotFound";
import Donate from "./pages/Donate/Donate";
import DonateThankyou from "./pages/Donate/DonateThankyou";
import ClashCreate from "./pages/Clash/ClashCreate";
import ClashLobby from "./pages/Clash/ClashLobby";
import ClashPlay from "./pages/Clash/ClashPlay";
import ClashResults from "./pages/Clash/ClashResults";
import AdminClash from "./pages/Dashboards/AdminClash";
import AdminClashDetail from "./pages/Dashboards/AdminClashDetail";

const WAKE_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

/**
 * Blocks rendering until auth rehydration from localStorage completes.
 * Prevents the "isAuthenticated: false" flash that redirects hard-refreshed
 * users to the login page before the token is read.
 */
function ProtectedRoute({ children, requireAdmin = false }) {
  const { isAuthenticated, isLoading, getUserRole } = useAuth();
  if (isLoading) return null;
  if (!isAuthenticated) return <Navigate to="/auth/login" replace />;
  if (requireAdmin && getUserRole() !== "admin") return <Navigate to="/dashboard" replace />;
  return children;
}

function ClashShareRedirect() {
  const { code } = useParams();
  return <Navigate to={`/clash/lobby/${code}`} replace />;
}

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
            {/* <Route path="/about" element={<About />} /> */}

            <Route path="/auth/login" element={<Login />} />
            <Route path="/auth/signup" element={<Signup />} />
            <Route path="/auth/verify-email" element={<VerifyEmail />} />
            <Route path="/auth/forgot-password" element={<ForgotPassword />} />
            <Route path="/auth/reset-password" element={<ResetPassword />} />

            <Route path="/auth" element={<Navigate to="/auth/login" replace />} />
            <Route path="/login" element={<Navigate to="/auth/login" replace />} />
            <Route path="/signup" element={<Navigate to="/auth/signup" replace />} />
            <Route path="/verify-email" element={<Navigate to="/auth/verify-email" replace />} />

            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/admin-dashboard" element={<Navigate to="/admin-dashboard/overview" replace />} />
            <Route path="/admin-dashboard/overview" element={<ProtectedRoute requireAdmin><AdminOverview /></ProtectedRoute>} />
            <Route path="/admin-dashboard/users" element={<ProtectedRoute requireAdmin><AdminUsers /></ProtectedRoute>} />
            <Route path="/admin-dashboard/content" element={<ProtectedRoute requireAdmin><AdminContent /></ProtectedRoute>} />
            <Route path="/admin-dashboard/settings" element={<ProtectedRoute requireAdmin><AdminSettings /></ProtectedRoute>} />
            <Route path="/admin-dashboard/profile" element={<ProtectedRoute requireAdmin><Profile ShellComponent={AdminAppShell} /></ProtectedRoute>} />
            <Route path="/admin-dashboard/user/:id" element={<ProtectedRoute requireAdmin><AdminUserDetails /></ProtectedRoute>} />
            <Route path="/admin-dashboard/activity" element={<ProtectedRoute requireAdmin><AdminActivity /></ProtectedRoute>} />
            <Route path="/admin-dashboard/ratings" element={<ProtectedRoute requireAdmin><AdminRatings /></ProtectedRoute>} />
            <Route path="/admin-dashboard/clashes" element={<ProtectedRoute requireAdmin><AdminClash /></ProtectedRoute>} />
            <Route path="/admin-dashboard/clashes/:code" element={<ProtectedRoute requireAdmin><AdminClashDetail /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />

            <Route path="/quiz" element={<ProtectedRoute><QuizHistory /></ProtectedRoute>} />
            <Route path="/quiz/create" element={<ProtectedRoute><CreateQuiz /></ProtectedRoute>} />
            <Route path="/quiz/play" element={<ProtectedRoute><Quiz /></ProtectedRoute>} />
            <Route path="/quiz/results" element={<ProtectedRoute><QuizResults /></ProtectedRoute>} />

            <Route path="/flashcards" element={<ProtectedRoute><FlashcardDecks /></ProtectedRoute>} />
            <Route path="/flashcards/create" element={<ProtectedRoute><FlashcardCreate /></ProtectedRoute>} />
            <Route path="/flashcards/deck/:id" element={<ProtectedRoute><FlashcardDeck /></ProtectedRoute>} />
            <Route path="/flashcards/study/:id" element={<ProtectedRoute><FlashcardStudy /></ProtectedRoute>} />
            <Route path="/flashcard" element={<Navigate to="/flashcards" replace />} />

            <Route path="/donate" element={<Donate />} />
            <Route path="/donate/thank-you" element={<DonateThankyou />} />

            <Route path="/materials" element={<Navigate to="/materials/community" replace />} />
            <Route path="/materials/community" element={<Materials />} />
            <Route path="/materials/mine" element={<ProtectedRoute><MaterialsMine /></ProtectedRoute>} />
            <Route path="/materials/upload" element={<ProtectedRoute><MaterialUpload /></ProtectedRoute>} />

            <Route path="/ai-tutor" element={<ProtectedRoute><Chatbot /></ProtectedRoute>} />
            <Route path="/ai" element={<Navigate to="/ai-tutor" replace />} />
            <Route path="/chat" element={<Navigate to="/ai-tutor" replace />} />
            <Route path="/chatbot" element={<Navigate to="/ai-tutor" replace />} />

            <Route path="/clash" element={<ProtectedRoute><ClashCreate /></ProtectedRoute>} />
            <Route path="/clash/share/:code" element={<ProtectedRoute><ClashShareRedirect /></ProtectedRoute>} />
            <Route path="/clash/lobby/:code" element={<ProtectedRoute><ClashLobby /></ProtectedRoute>} />
            <Route path="/clash/play/:code" element={<ProtectedRoute><ClashPlay /></ProtectedRoute>} />
            <Route path="/clash/results/:code" element={<ProtectedRoute><ClashResults /></ProtectedRoute>} />

            <Route path="*" element={<NotFound />} />
          </Routes>
        </Router>
      </AuthProvider>
      </ThemeProvider>
    </GoogleOAuthProvider>
  );
}

export default App;