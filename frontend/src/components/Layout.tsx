import { type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout({
  title,
  children,
  actions,
}: {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const navLink = (to: string, label: string) => (
    <Link
      to={to}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
        location.pathname === to
          ? "bg-indigo-600 text-white"
          : "text-slate-600 hover:bg-slate-100"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="font-semibold text-slate-900">Recon</span>
            <nav className="flex items-center gap-1">
              {navLink("/", "Dashboard")}
              {navLink("/import", "Import")}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {actions}
            <span className="text-sm text-slate-500">{user?.email}</span>
            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="text-sm text-slate-500 hover:text-slate-800"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
          {actions}
        </div>
        {children}
      </main>
    </div>
  );
}
