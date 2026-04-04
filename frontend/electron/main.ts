/**
 * CSA Copilot — Electron main process.
 *
 * 1. Spawns the Python server (`python app.py --server --port 0`)
 * 2. Reads the port from stdout (`PORT:XXXX`)
 * 3. Loads the React frontend pointing at `http://127.0.0.1:XXXX`
 *
 * When running in dev mode (VITE_DEV_SERVER_URL set), it loads the
 * Vite dev server instead and proxies API calls.
 */

import { app, BrowserWindow, shell, ipcMain, Notification, Menu } from "electron";
import { spawn, type ChildProcess } from "child_process";
import * as path from "path";

let mainWindow: BrowserWindow | null = null;
let serverProcess: ChildProcess | null = null;
let serverPort: number | null = null;

// ── Server lifecycle ─────────────────────────────────────────────────────

function startServer(): Promise<number> {
  return new Promise((resolve, reject) => {
    const pythonCmd = process.platform === "win32" ? "python" : "python3";
    const appDir = path.resolve(__dirname, "..", "..");
    const proc = spawn(pythonCmd, ["app.py", "--server", "--port", "0"], {
      cwd: appDir,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env },
    });

    serverProcess = proc;

    let resolved = false;
    const timeout = setTimeout(() => {
      if (!resolved) {
        reject(new Error("Server did not start within 30 seconds"));
      }
    }, 30_000);

    proc.stdout?.on("data", (data: Buffer) => {
      const line = data.toString().trim();
      const match = line.match(/^PORT:(\d+)$/m);
      if (match && !resolved) {
        resolved = true;
        clearTimeout(timeout);
        resolve(parseInt(match[1], 10));
      }
    });

    proc.stderr?.on("data", (data: Buffer) => {
      // Log server stderr for debugging
      console.error("[server]", data.toString().trim());
    });

    proc.on("error", (err) => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timeout);
        reject(err);
      }
    });

    proc.on("exit", (code) => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timeout);
        reject(new Error(`Server exited with code ${code}`));
      }
      serverProcess = null;
    });
  });
}

// ── Window creation ──────────────────────────────────────────────────────

function createWindow(port: number) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: "CSA Copilot",
    icon: path.join(__dirname, "..", "public", "csa-copilot-logo.svg"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 12, y: 12 },
  });

  // Use Vite dev server in development, built files in production
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    mainWindow.loadURL(devUrl);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  // Open external links in the system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

// ── Application menu ─────────────────────────────────────────────────────

function buildMenu() {
  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: "CSA Copilot",
      submenu: [
        { role: "about" },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },
    {
      label: "Navigate",
      submenu: [
        {
          label: "Launchpad",
          accelerator: "CmdOrCtrl+N",
          click: () => mainWindow?.webContents.send("navigate", "/"),
        },
        {
          label: "Mission Control",
          accelerator: "CmdOrCtrl+M",
          click: () => mainWindow?.webContents.send("navigate", "/mission"),
        },
        {
          label: "Output Library",
          accelerator: "CmdOrCtrl+L",
          click: () => mainWindow?.webContents.send("navigate", "/library"),
        },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ── IPC handlers ─────────────────────────────────────────────────────────

function setupIpc() {
  const userHome = app.getPath("home");

  // Open a file/folder in the system file manager
  ipcMain.handle("shell:openPath", async (_event, filePath: string) => {
    const normalized = path.resolve(filePath);
    if (!normalized.startsWith(userHome)) {
      throw new Error("Access denied: path outside allowed directories");
    }
    return shell.openPath(normalized);
  });

  // Open a folder in VS Code
  ipcMain.handle("shell:openInVSCode", async (_event, folderPath: string) => {
    const normalized = path.resolve(folderPath);
    if (!normalized.startsWith(userHome)) {
      throw new Error("Access denied: path outside allowed directories");
    }
    return shell.openExternal(`vscode://file/${normalized}`);
  });

  // Show a system notification
  ipcMain.handle("notify", async (_event, title: string, body: string) => {
    new Notification({ title, body }).show();
  });

  // Get the server port
  ipcMain.handle("getServerPort", () => serverPort);
}

// ── App lifecycle ────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  setupIpc();
  buildMenu();

  try {
    serverPort = await startServer();
    console.log(`[electron] Server running on port ${serverPort}`);
    createWindow(serverPort);
  } catch (err) {
    console.error("[electron] Failed to start server:", err);
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (serverProcess) {
    serverProcess.kill();
    serverProcess = null;
  }
  app.quit();
});

app.on("before-quit", () => {
  if (serverProcess) {
    serverProcess.kill();
    serverProcess = null;
  }
});
