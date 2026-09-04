import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { clearAuth, isLoggedIn, setAuth } from "../api/client";
import { login as apiLogin, me, signup as apiSignup, type SignupPayload } from "../api/auth";

interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(isLoggedIn());

  useEffect(() => {
    let cancelled = false;
    if (isLoggedIn()) {
      me()
        .then((u) => !cancelled && setUser(u))
        .catch(() => {
          clearAuth();
          if (!cancelled) setUser(null);
        })
        .finally(() => !cancelled && setLoading(false));
    } else {
      setLoading(false);
    }
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiLogin(email, password);
    setAuth(data.access, data.refresh);
    const u = await me();
    setUser(u);
  };

  const signup = async (payload: SignupPayload) => {
    const data = await apiSignup(payload);
    setAuth(data.tokens.access, data.tokens.refresh);
    const u = await me();
    setUser(u);
  };

  const logout = () => {
    clearAuth();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
