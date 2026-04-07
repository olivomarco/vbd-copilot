import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import http from "http";
import { spawn, type ChildProcess } from "child_process";

function waitForBackendReady(maxWaitMs = 30000, intervalMs = 500): Promise<void> {
  const deadline = Date.now() + maxWaitMs;

  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get("http://127.0.0.1:18080/health", { timeout: 2000 }, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve();
          return;
        }

        if (Date.now() >= deadline) {
          reject(new Error(`health endpoint returned ${res.statusCode}`));
          return;
        }

        setTimeout(attempt, intervalMs);
      });

      req.on("timeout", () => {
        req.destroy(new Error("health check timeout"));
      });

      req.on("error", (error) => {
        if (Date.now() >= deadline) {
          reject(error);
          return;
        }
        setTimeout(attempt, intervalMs);
      });
    };

    attempt();
  });
}

/**
 * Vite plugin that starts the Python backend (`python app.py --server --port 18080`)
 * alongside the dev server and tears it down on exit.
 */
function backendPlugin() {
  let proc: ChildProcess | null = null;
  let hasReportedReady = false;
  return {
    name: "start-backend",
    configureServer() {
      const root = path.resolve(__dirname, "..");
      console.log("[dev] starting backend on http://127.0.0.1:18080");
      proc = spawn("python", ["app.py", "--server", "--port", "18080"], {
        cwd: root,
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, CSA_BACKEND_DEV_LOG: "1" },
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

      void waitForBackendReady()
        .then(() => {
          if (!hasReportedReady) {
            hasReportedReady = true;
            console.log("[dev] backend ready at http://127.0.0.1:18080");
          }
        })
        .catch((error: Error) => {
          console.error(`[dev] backend did not become healthy: ${error.message}`);
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
