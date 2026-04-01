import { useEffect, type ReactNode } from "react";
import { FluentProvider } from "@fluentui/react-components";
import { lightTheme, darkTheme } from "./theme";
import { useSettingsStore } from "@/stores/settingsStore";

function useResolvedTheme() {
  const pref = useSettingsStore((s) => s.theme);

  if (pref === "light") return "light";
  if (pref === "dark") return "dark";

  // "system" — check media query
  if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function ThemeWrapper({ children }: { children: ReactNode }) {
  const resolved = useResolvedTheme();
  const isDark = resolved === "dark";

  // Apply data attribute + CSS variables to <html> so non-Fluent elements respond
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", resolved);

    if (isDark) {
      root.style.setProperty("--brand-light", "#1a1a2e");
      root.style.setProperty("--surface", "#1e1e2e");
      root.style.setProperty("--text-primary", "#e0e0e0");
      root.style.setProperty("--text-secondary", "#a0a0a0");
      root.style.setProperty("color-scheme", "dark");
    } else {
      root.style.setProperty("--brand-light", "#f5f5f5");
      root.style.setProperty("--surface", "#ffffff");
      root.style.setProperty("--text-primary", "#323130");
      root.style.setProperty("--text-secondary", "#605e5c");
      root.style.setProperty("color-scheme", "light");
    }
  }, [resolved, isDark]);

  return (
    <FluentProvider theme={isDark ? darkTheme : lightTheme} style={{ height: "100%", width: "100%" }}>
      {children}
    </FluentProvider>
  );
}
