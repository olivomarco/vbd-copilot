/**
 * Type declarations for the Electron context bridge.
 * These APIs are available when running inside Electron.
 * In browser mode, window.csaStudio is undefined.
 */

interface CsaStudioBridge {
  openPath: (path: string) => Promise<string>;
  openInVSCode: (path: string) => Promise<void>;
  notify: (title: string, body: string) => Promise<void>;
  getServerPort: () => Promise<number>;
  onNavigate: (callback: (path: string) => void) => void;
}

interface Window {
  csaStudio?: CsaStudioBridge;
}
