import { Monitor, Moon, Plus, Sun, Type } from "lucide-react";
import { useTextSize, useTheme } from "../lib/theme.ts";
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
  const [size, setSize] = useTextSize();
  const ThemeIcon = ICON[theme];
  return (
    <header className="topbar">
      <a className="brand" href="#/" aria-label="Pramana, ask a question">
        <span className="brand-mark">प्र</span>
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
          className="icon-button"
          onClick={() => setTheme(NEXT[theme])}
          aria-label={`Theme: ${theme}. Switch to ${NEXT[theme]}`}
          title={`Theme: ${theme}`}
        >
          <ThemeIcon size={16} />
        </button>
        <button
          className="icon-button"
          onClick={() => setSize(size === "regular" ? "large" : "regular")}
          aria-pressed={size === "large"}
          aria-label="Larger text"
          title="Larger text"
        >
          <Type size={16} />
        </button>
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
