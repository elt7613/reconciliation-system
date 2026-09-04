import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

// Attach the access token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401: try refreshing the token once, then retry; otherwise log out
let refreshing: Promise<string | null> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retried) {
      original._retried = true;
      refreshing ??= (async () => {
        const refresh = localStorage.getItem("refresh");
        if (!refresh) return null;
        try {
          const { data } = await axios.post("/api/auth/refresh/", { refresh });
          localStorage.setItem("access", data.access);
          return data.access as string;
        } catch {
          return null;
        } finally {
          refreshing = null;
        }
      })();
      const newToken = await refreshing;
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export function setAuth(access: string, refresh: string) {
  localStorage.setItem("access", access);
  localStorage.setItem("refresh", refresh);
}

export function clearAuth() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
}

export function isLoggedIn(): boolean {
  return Boolean(localStorage.getItem("access"));
}

export default api;
