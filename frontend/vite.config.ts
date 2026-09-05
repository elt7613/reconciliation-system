import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Default base ("/"): the SPA is served at its own domain root, so
  // routes are normal: /, /login, /assets/...
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
