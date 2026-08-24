"use client";

import { useEffect, useState } from "react";

const KEY = "finbot-theme";
type Theme = "light" | "dark";

/* Both the attribute and the class are set. Our own tokens key off
   `[data-theme="dark"]`, but CopilotKit's stylesheet keys off a `.dark` class -- with
   only the attribute set, its `dark:` variants never fire and the chat renders black
   text on a dark background. */
export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.classList.toggle("dark", theme === "dark");
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const saved = (localStorage.getItem(KEY) as Theme | null) ?? "light";
    setTheme(saved);
    applyTheme(saved);
  }, []);

  const flip = () => {
    const next: Theme = theme === "light" ? "dark" : "light";
    setTheme(next);
    applyTheme(next);
    localStorage.setItem(KEY, next);
  };

  return (
    <button
      onClick={flip}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
      className="pressable"
      style={{
        all: "unset",
        cursor: "pointer",
        width: 28,
        height: 28,
        display: "grid",
        placeItems: "center",
        borderRadius: "var(--r-sm)",
        border: "1px solid var(--line)",
        background: "var(--surface-1)",
        color: "var(--ink-dim)",
      }}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        {theme === "light" ? (
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" strokeLinejoin="round" />
        ) : (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" strokeLinecap="round" />
          </>
        )}
      </svg>
    </button>
  );
}
