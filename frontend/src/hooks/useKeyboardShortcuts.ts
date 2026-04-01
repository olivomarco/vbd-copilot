import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

/**
 * Global keyboard shortcuts:
 *   Ctrl+N  → Launchpad (new job)
 *   Ctrl+L  → Output Library
 *   Ctrl+M  → Mission Control
 *   Escape  → close any open panel / go back
 */
export function useKeyboardShortcuts() {
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't capture if user is typing in an input/textarea
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.ctrlKey || e.metaKey) {
        switch (e.key.toLowerCase()) {
          case "n":
            e.preventDefault();
            navigate("/");
            break;
          case "l":
            e.preventDefault();
            navigate("/library");
            break;
          case "m":
            e.preventDefault();
            navigate("/mission");
            break;
        }
      }

      if (e.key === "Escape") {
        // Close any open brief form panels by dispatching a custom event
        window.dispatchEvent(new CustomEvent("csa-escape"));
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate]);
}
