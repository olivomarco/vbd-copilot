import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { spawn, type ChildProcess } from "child_process";

/**
 * Vite plugin that starts the Python backend (`python app.py --server --port 18080`)
 * alongside the dev server and tears it down on exit.
 */
function backendPlugin() {
  let proc: ChildProcess | null = null;
  return {
    name: "start-backend",
    configureServer() {
      const root = path.resolve(__dirname, "..");
      proc = spawn("python", ["app.py", "--server", "--port", "18080"], {
        cwd: root,
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env },
      });
      proc.stdout?.on("data", (d: Buffer) => {
        const line = d.toString().trim();
        if (line) console.log(`[backend] ${line}`);
      });
      proc.stderr?.on("data", (d: Buffer) => {
        const line = d.toString().trim();
        if (line) console.error(`[backend] ${line}`);
      });
      proc.on("exit", (code) => {
        if (code !== null && code !== 0) {
          console.error(`[backend] exited with code ${code}`);
        }
        proc = null;
      });

      const cleanup = () => {
        if (proc && !proc.killed) {
          proc.kill("SIGTERM");
          proc = null;
        }
      };
      process.on("exit", cleanup);
      process.on("SIGINT", () => { cleanup(); process.exit(); });
      process.on("SIGTERM", () => { cleanup(); process.exit(); });
    },
  };
}

export default defineConfig({
  plugins: [react(), backendPlugin()],
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
