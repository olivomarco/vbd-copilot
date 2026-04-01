/**
 * CSA Copilot — Electron preload script.
 *
 * Exposes safe IPC methods to the renderer via contextBridge.
 */

import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("csaStudio", {
  /** Open a file/folder in the native file manager */
  openPath: (path: string) => ipcRenderer.invoke("shell:openPath", path),

  /** Open a folder in VS Code */
  openInVSCode: (path: string) => ipcRenderer.invoke("shell:openInVSCode", path),

  /** Show a system notification */
  notify: (title: string, body: string) => ipcRenderer.invoke("notify", title, body),

  /** Get the backend server port */
  getServerPort: () => ipcRenderer.invoke("getServerPort"),

  /** Listen for navigation events from the menu */
  onNavigate: (callback: (path: string) => void) => {
    ipcRenderer.on("navigate", (_event, path) => callback(path));
  },
});
