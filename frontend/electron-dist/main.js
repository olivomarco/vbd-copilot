"use strict";
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
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const child_process_1 = require("child_process");
const path = __importStar(require("path"));
let mainWindow = null;
let serverProcess = null;
let serverPort = null;
// ── Server lifecycle ─────────────────────────────────────────────────────
function startServer() {
    return new Promise((resolve, reject) => {
        const pythonCmd = process.platform === "win32" ? "python" : "python3";
        const appDir = path.resolve(__dirname, "..", "..");
        const proc = (0, child_process_1.spawn)(pythonCmd, ["app.py", "--server", "--port", "0"], {
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
        proc.stdout?.on("data", (data) => {
            const line = data.toString().trim();
            const match = line.match(/^PORT:(\d+)$/m);
            if (match && !resolved) {
                resolved = true;
                clearTimeout(timeout);
                resolve(parseInt(match[1], 10));
            }
        });
        proc.stderr?.on("data", (data) => {
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
function createWindow(port) {
    mainWindow = new electron_1.BrowserWindow({
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
    }
    else {
        mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
    }
    mainWindow.on("closed", () => {
        mainWindow = null;
    });
    // Open external links in the system browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        electron_1.shell.openExternal(url);
        return { action: "deny" };
    });
}
// ── Application menu ─────────────────────────────────────────────────────
function buildMenu() {
    const template = [
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
    electron_1.Menu.setApplicationMenu(electron_1.Menu.buildFromTemplate(template));
}
// ── IPC handlers ─────────────────────────────────────────────────────────
function setupIpc() {
    // Open a file/folder in the system file manager
    electron_1.ipcMain.handle("shell:openPath", async (_event, filePath) => {
        return electron_1.shell.openPath(filePath);
    });
    // Open a folder in VS Code
    electron_1.ipcMain.handle("shell:openInVSCode", async (_event, folderPath) => {
        return electron_1.shell.openExternal(`vscode://file/${folderPath}`);
    });
    // Show a system notification
    electron_1.ipcMain.handle("notify", async (_event, title, body) => {
        new electron_1.Notification({ title, body }).show();
    });
    // Get the server port
    electron_1.ipcMain.handle("getServerPort", () => serverPort);
}
// ── App lifecycle ────────────────────────────────────────────────────────
electron_1.app.whenReady().then(async () => {
    setupIpc();
    buildMenu();
    try {
        serverPort = await startServer();
        console.log(`[electron] Server running on port ${serverPort}`);
        createWindow(serverPort);
    }
    catch (err) {
        console.error("[electron] Failed to start server:", err);
        electron_1.app.quit();
    }
});
electron_1.app.on("window-all-closed", () => {
    if (serverProcess) {
        serverProcess.kill();
        serverProcess = null;
    }
    electron_1.app.quit();
});
electron_1.app.on("before-quit", () => {
    if (serverProcess) {
        serverProcess.kill();
        serverProcess = null;
    }
});
