"use strict";
/**
 * CSA Copilot — Electron preload script.
 *
 * Exposes safe IPC methods to the renderer via contextBridge.
 */
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld("csaStudio", {
    /** Open a file/folder in the native file manager */
    openPath: (path) => electron_1.ipcRenderer.invoke("shell:openPath", path),
    /** Open a folder in VS Code */
    openInVSCode: (path) => electron_1.ipcRenderer.invoke("shell:openInVSCode", path),
    /** Show a system notification */
    notify: (title, body) => electron_1.ipcRenderer.invoke("notify", title, body),
    /** Get the backend server port */
    getServerPort: () => electron_1.ipcRenderer.invoke("getServerPort"),
    /** Listen for navigation events from the menu */
    onNavigate: (callback) => {
        electron_1.ipcRenderer.on("navigate", (_event, path) => callback(path));
    },
});
