/**
 * Notification utilities — audible sound + favicon badge + title flash
 * when agent input is required.
 */

const ORIGINAL_TITLE = document.title;
const ORIGINAL_FAVICON = getFaviconHref();

let titleInterval: ReturnType<typeof setInterval> | null = null;
let faviconActive = false;
let notificationsInitialized = false;
let windowHasFocus = document.hasFocus();
let documentVisible = document.visibilityState === "visible";
let activeSystemNotification: Notification | null = null;
let systemNotificationTimer: ReturnType<typeof setTimeout> | null = null;

/* ------------------------------------------------------------------ */
/* Sound — synthesised notification chime via Web Audio API             */
/* ------------------------------------------------------------------ */

let audioCtx: AudioContext | null = null;
/** Timestamp of the last notification sound — used for debouncing. */
let lastSoundTime = 0;
/** Minimum gap between notification sounds (ms). Prevents double-chime
 *  when multiple WebSocket hooks process the same event. */
const SOUND_DEBOUNCE_MS = 2000;

function getAudioContext(): AudioContext {
  if (!audioCtx) {
    audioCtx = new AudioContext();
  }
  return audioCtx;
}

/**
 * Play a short two-tone chime.  Uses the Web Audio API so no external
 * audio file is needed.  Debounced: ignores calls within 2 s of the
 * last chime to prevent double-notification from parallel WS hooks.
 */
export function playNotificationSound(): void {
  const now = Date.now();
  if (now - lastSoundTime < SOUND_DEBOUNCE_MS) return;
  lastSoundTime = now;

  try {
    const ctx = getAudioContext();

    // Resume if the context was suspended (autoplay policy)
    if (ctx.state === "suspended") {
      void ctx.resume();
    }

    const now = ctx.currentTime;

    // Tone 1 — 880 Hz for 120 ms
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.value = 880;
    gain1.gain.setValueAtTime(0.18, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
    osc1.connect(gain1).connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.12);

    // Tone 2 — 1174 Hz for 180 ms (starts after a 60 ms gap)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.value = 1174;
    gain2.gain.setValueAtTime(0.18, now + 0.18);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.36);
    osc2.connect(gain2).connect(ctx.destination);
    osc2.start(now + 0.18);
    osc2.stop(now + 0.36);
  } catch {
    // Audio not available — silently ignore.
  }
}

/* ------------------------------------------------------------------ */
/* Favicon badge — red dot overlay on the existing favicon              */
/* ------------------------------------------------------------------ */

function getFaviconHref(): string {
  const link = document.querySelector<HTMLLinkElement>("link[rel*='icon']");
  return link?.href ?? "/favicon.svg";
}

function setFavicon(href: string): void {
  let link = document.querySelector<HTMLLinkElement>("link[rel*='icon']");
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.href = href;
}

/** Build a data-URI favicon that composites the original SVG with a red badge circle. */
function buildBadgedFavicon(): Promise<string> {
  return new Promise((resolve) => {
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext("2d")!;

    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      ctx.drawImage(img, 0, 0, 64, 64);

      // Red notification dot (top-right)
      ctx.beginPath();
      ctx.arc(52, 12, 12, 0, 2 * Math.PI);
      ctx.fillStyle = "#E53935";
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 2;
      ctx.stroke();

      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => resolve(ORIGINAL_FAVICON); // fallback
    img.src = ORIGINAL_FAVICON;
  });
}

/* ------------------------------------------------------------------ */
/* Title flash                                                         */
/* ------------------------------------------------------------------ */

function startTitleFlash(): void {
  if (titleInterval) return;
  let toggle = false;
  titleInterval = setInterval(() => {
    toggle = !toggle;
    document.title = toggle ? "⚡ Input required — CSA Copilot" : ORIGINAL_TITLE;
  }, 1200);
}

function stopTitleFlash(): void {
  if (titleInterval) {
    clearInterval(titleInterval);
    titleInterval = null;
  }
  document.title = ORIGINAL_TITLE;
}

/* ------------------------------------------------------------------ */
/* Browser focus/visibility + system notifications                    */
/* ------------------------------------------------------------------ */

function shouldUseSystemNotification(): boolean {
  return !windowHasFocus || !documentVisible;
}

function closeActiveSystemNotification(): void {
  if (activeSystemNotification) {
    activeSystemNotification.close();
    activeSystemNotification = null;
  }
  if (systemNotificationTimer) {
    clearTimeout(systemNotificationTimer);
    systemNotificationTimer = null;
  }
}

function maybeRequestNotificationPermission(): void {
  if (!("Notification" in window)) return;
  if (Notification.permission !== "default") return;
  // Fire-and-forget: browsers may ignore this without user interaction.
  void Notification.requestPermission();
}

/**
 * Initialize notification state tracking once at app startup.
 * Can optionally pre-request Notification permission.
 */
export function initializeNotifications(requestPermission = false): void {
  if (notificationsInitialized) return;
  notificationsInitialized = true;

  windowHasFocus = document.hasFocus();
  documentVisible = document.visibilityState === "visible";

  window.addEventListener("focus", () => {
    windowHasFocus = true;
  });

  window.addEventListener("blur", () => {
    windowHasFocus = false;
  });

  document.addEventListener("visibilitychange", () => {
    documentVisible = document.visibilityState === "visible";
    if (documentVisible && windowHasFocus) {
      closeActiveSystemNotification();
    }
  });

  if (requestPermission) {
    maybeRequestNotificationPermission();
  }
}

function sendSystemNotification(title: string, body: string): void {
  if (!("Notification" in window)) return;
  if (Notification.permission !== "granted") return;

  closeActiveSystemNotification();

  try {
    const notification = new Notification(title, {
      body,
      icon: ORIGINAL_FAVICON,
      tag: "csa-copilot-input-required",
    });

    activeSystemNotification = notification;
    notification.onclose = () => {
      if (activeSystemNotification === notification) {
        activeSystemNotification = null;
      }
      if (systemNotificationTimer) {
        clearTimeout(systemNotificationTimer);
        systemNotificationTimer = null;
      }
    };

    // Some platforms keep notifications around; auto-close to avoid stale toasts.
    systemNotificationTimer = setTimeout(() => {
      if (activeSystemNotification === notification) {
        notification.close();
      }
    }, 20000);
  } catch {
    // Ignore Notification API failures and keep in-page signals only.
  }
}

/* ------------------------------------------------------------------ */
/* Public API                                                          */
/* ------------------------------------------------------------------ */

/**
 * Fire all attention signals: sound + favicon badge + title flash.
 * Safe to call multiple times — debounces sound and deduplicates
 * favicon/title internally.
 */
export async function notifyInputRequired(): Promise<void> {
  initializeNotifications();
  playNotificationSound();

  // Title flash
  startTitleFlash();

  // Favicon badge
  if (!faviconActive) {
    faviconActive = true;
    const badged = await buildBadgedFavicon();
    setFavicon(badged);
  }

  if (shouldUseSystemNotification()) {
    sendSystemNotification(
      "Input required — CSA Copilot",
      "The agent is waiting for your response.",
    );
  }
}

/**
 * Clear all attention signals and restore original state.
 */
export function clearInputNotification(): void {
  stopTitleFlash();

  if (faviconActive) {
    faviconActive = false;
    setFavicon(ORIGINAL_FAVICON);
  }

  closeActiveSystemNotification();
}

/**
 * Notify the user that a job has completed while the window was
 * backgrounded.  Only fires a system notification — no sound/favicon
 * since the job is done, not blocked.
 */
export function notifyJobCompleted(title: string): void {
  initializeNotifications();
  if (!shouldUseSystemNotification()) return;
  sendSystemNotification(
    "Job completed — CSA Copilot",
    title,
  );
}
