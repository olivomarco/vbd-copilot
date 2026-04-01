import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy all backend API routes to the Python server
      "/health": { target: "http://127.0.0.1:18080", changeOrigin: true },
      "/agents": { target: "http://127.0.0.1:18080", changeOrigin: true },
      "/sessions": { target: "http://127.0.0.1:18080", changeOrigin: true },
      "/usage": { target: "http://127.0.0.1:18080", changeOrigin: true },
      "/outputs": { target: "http://127.0.0.1:18080", changeOrigin: true },
      "/file": { target: "http://127.0.0.1:18080", changeOrigin: true },
      "/preview": { target: "http://127.0.0.1:18080", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:18080", ws: true },
    },
  },
});
