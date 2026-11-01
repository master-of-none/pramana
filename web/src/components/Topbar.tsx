import { useEffect } from "react";
import { Command, Monitor, Moon, Plus, Sun } from "lucide-react";
import { PALETTE, THEME } from "../lib/keys.ts";
import { MOD } from "./Shortcuts.tsx";
import { useTheme } from "../lib/theme.ts";
import { TypographyButton } from "./Typography.tsx";
import type { Theme } from "../lib/theme.ts";

const NEXT: Record<Theme, Theme> = {
  system: "light",
  light: "dark",
  dark: "system",
};
const ICON = { system: Monitor, light: Sun, dark: Moon };

export function Topbar({
  section,
  onNewChat,
}: {
  section: "chat" | "study";
  onNewChat: () => void;
}) {
  const [theme, setTheme] = useTheme();
  const ThemeIcon = ICON[theme];
  // "Switch theme" from the command palette.
  useEffect(() => {
    const cycle = () => setTheme((t) => NEXT[t]);
    window.addEventListener(THEME, cycle);
    return () => window.removeEventListener(THEME, cycle);
  }, []);
  return (
    <header className="topbar">
      <a className="brand" href="#/" title="Ask a question">
        <span className="brand-mark" aria-hidden="true">
          प्र
        </span>
        <span className="brand-name">
          pramāṇa<span className="brand-sub">A SPACE FOR UNDERSTANDING</span>
        </span>
      </a>
      <nav className="sections" aria-label="Sections">
        <a href="#/" aria-current={section === "chat" ? "page" : undefined}>
          Ask
        </a>
        <a
          href="#/study"
          aria-current={section === "study" ? "page" : undefined}
        >
          Study
        </a>
      </nav>
      <div className="topbar-right">
        <button
          className="palette-button"
          onClick={() => window.dispatchEvent(new Event(PALETTE))}
          title="Command palette"
          aria-keyshortcuts={MOD === "⌘" ? "Meta+K" : "Control+K"}
        >
          <Command size={14} aria-hidden="true" />
          <span className="palette-button-label">Go to…</span>
          <kbd aria-hidden="true">{MOD}K</kbd>
        </button>
        <button
          className="icon-button theme-button"
          onClick={() => setTheme(NEXT[theme])}
          aria-label={`Theme: ${theme}. Switch to ${NEXT[theme]}`}
          title={`Theme: ${theme}`}
        >
          <ThemeIcon size={16} />
        </button>
        <TypographyButton />
        {section === "chat" && (
          <button className="new-chat" onClick={onNewChat}>
            <Plus size={16} />
            <span>New chat</span>
          </button>
        )}
      </div>
    </header>
  );
}
