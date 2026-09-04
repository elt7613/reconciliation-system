import { Navigate, Route, Routes } from "react-router-dom";
import { type ReactElement } from "react";
import { useAuth } from "./auth/AuthContext";
import DashboardPage from "./pages/Dashboard";
import ImportPage from "./pages/Import";
import LoginPage from "./pages/Login";
import SignupPage from "./pages/Signup";

function Protected({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/import"
        element={
          <Protected>
            <ImportPage />
          </Protected>
        }
      />
      <Route
        path="/"
        element={
          <Protected>
            <DashboardPage />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
