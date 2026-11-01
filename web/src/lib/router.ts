import { useEffect, useState } from "react";
import type { RefObject } from "react";

// Hash routes keep the static build servable from FastAPI's single index.html.
export type Route = { path: string[]; query: URLSearchParams };

export const APP_TITLE = "Pramana — A space for understanding";

function parse(): Route {
  const [path, query = ""] = window.location.hash
    .replace(/^#\/?/, "")
    .split("?");
  return {
    path: path.split("/").filter(Boolean).map(decodeURIComponent),
    query: new URLSearchParams(query),
  };
}

// Scroll positions per hash, for Back and Forward (this tab only).
const SCROLL = "pramana.scroll.v1";
function positions(): Record<string, number> {
  try {
    return JSON.parse(sessionStorage.getItem(SCROLL) || "{}");
  } catch {
    return {};
  }
}
const scroller = () =>
  document.querySelector<HTMLElement>(".view:not([hidden]) main");

// Set on each in-app navigation and consumed once the new page has its heading.
let arrival: { scroll: number } | null = null;

function onHashChange(event: HashChangeEvent) {
  const old = new URL(event.oldURL).hash || "#/";
  const saved = positions();
  saved[old] = scroller()?.scrollTop ?? 0;
  try {
    sessionStorage.setItem(SCROLL, JSON.stringify(saved));
  } catch {
    /* Back simply starts at the top. */
  }
  // A new entry has no state yet; one revisited by Back/Forward keeps the mark.
  const revisit = Boolean(history.state?.pramana);
  if (!revisit) history.replaceState({ pramana: true }, "");
  arrival = { scroll: revisit ? (saved[location.hash || "#/"] ?? 0) : 0 };
}

if (typeof window !== "undefined") {
  window.addEventListener("hashchange", onHashChange);
  // The entry the tab opened on counts as visited, so Back to it restores its place.
  if (!history.state?.pramana) history.replaceState({ pramana: true }, "");
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const change = () => setRoute(parse());
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  return route;
}

const INPUT = ["wheel", "touchstart", "keydown", "pointerdown"] as const;

// Once a page's h1 is rendered (pages load their data first): title the document from
// it, and after a navigation move focus to it and restore or reset the scroll position.
export function usePageArrival(main: RefObject<HTMLElement | null>, key: string) {
  useEffect(() => {
    const box = main.current;
    if (!box) return;
    let target: number | null = null;
    let titled = false;
    const settle = () => {
      if (!titled) {
        const heading = box.querySelector<HTMLElement>("h1");
        if (!heading) return;
        titled = true;
        const title = heading.dataset.title || heading.textContent?.trim();
        document.title = title ? `${title} · Pramana` : APP_TITLE;
        const landed = arrival;
        arrival = null;
        if (!landed) return observer.disconnect();
        target = landed.scroll;
        heading.tabIndex = -1;
        // A page that put focus in a field for typing (search) keeps it there.
        const typing = document.activeElement?.matches("input, textarea, select");
        if (!typing) heading.focus({ preventScroll: true });
        // Scroll anchoring would shift the position as content loads above it.
        box.style.overflowAnchor = "none";
      }
      // A new page starts at the top once; only a saved place is held while content loads.
      if (target !== null) box.scrollTop = target;
      if (!target) target = null;
    };
    // Parts of a page that load later (concepts, citations) may be needed to reach the
    // saved position, so it is re-applied as they arrive, for a moment only.
    const observer = new MutationObserver(settle);
    observer.observe(box, { childList: true, subtree: true });
    settle();
    // The reader's own scrolling ends it at once.
    const done = () => {
      window.clearTimeout(timer);
      observer.disconnect();
      box.style.overflowAnchor = "";
      for (const type of INPUT) box.removeEventListener(type, done);
    };
    const timer = window.setTimeout(done, 1200);
    for (const type of INPUT) box.addEventListener(type, done, { passive: true });
    return done;
  }, [key]);
}

// Leaving Study for the chat: the chat keeps its own place, so only the title changes.
export function leavePage() {
  arrival = null;
  document.title = APP_TITLE;
}

export function href(...parts: (string | number)[]): string {
  return "#/" + parts.map((p) => encodeURIComponent(String(p))).join("/");
}

// The reader at a chapter, optionally highlighting a code-point span.
export function readAt(chapterId: string, start?: number, end?: number): string {
  const base = href("study", "read", chapterId);
  return start === undefined || end === undefined ? base : `${base}?s=${start}&e=${end}`;
}
