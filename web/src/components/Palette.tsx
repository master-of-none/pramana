import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  BookMarked,
  BookOpen,
  Columns2,
  Download,
  Keyboard,
  Lightbulb,
  MessageCircleQuestion,
  Moon,
  Plus,
  Route as PathIcon,
  ScrollText,
  Search,
  StickyNote,
  Quote,
  Type,
  Waypoints,
} from "lucide-react";
import { getJSON } from "../lib/api.ts";
import type { LibraryDocument } from "../lib/api.ts";
import { rank, sutraRef } from "../lib/fuzzy.ts";
import { PALETTE, SHORTCUTS, THEME, TYPOGRAPHY } from "../lib/keys.ts";
import { href, readAt } from "../lib/router.ts";

export const ASK = "pramana:ask";
export const NEW_CHAT = "pramana:new-chat";
export const EXPORT = "pramana:export-chat";

type Item = {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: ReactNode;
  run: () => void;
};
type Located = {
  chapter_id: string;
  document: string;
  place: string;
  verse: number | null;
  start: number;
  end: number;
  exact: boolean;
};
type ConceptSummary = { slug: string; term: string; aliases: string[]; english?: string[] };
type SayingSummary = { key: string; saying: string; english: string; found: boolean };

const go = (hash: string) => {
  window.location.hash = hash;
};
const send = (name: string, detail?: unknown) =>
  window.dispatchEvent(new CustomEvent(name, { detail }));

const ACTIONS: Omit<Item, "group">[] = [
  { id: "new", label: "New chat", icon: <Plus size={15} />, run: () => (go("#/"), send(NEW_CHAT)) },
  { id: "ask", label: "Ask a question", icon: <MessageCircleQuestion size={15} />, run: () => (go("#/"), send(ASK, "")) },
  { id: "export", label: "Save the conversation as Markdown", icon: <Download size={15} />, run: () => send(EXPORT) },
  { id: "library", label: "Library", icon: <BookOpen size={15} />, run: () => go(href("study")) },
  { id: "search", label: "Search the library", icon: <Search size={15} />, run: () => go(href("study", "search")) },
  { id: "paths", label: "Reading paths", icon: <PathIcon size={15} />, run: () => go(href("study", "paths")) },
  { id: "sutra", label: "Śaṅkara and Rāmānuja side by side", icon: <Columns2 size={15} />, run: () => go(href("study", "sutra", 1, 1, 1)) },
  { id: "map", label: "Where Śaṅkara and Rāmānuja part ways", icon: <Waypoints size={15} />, run: () => go(href("study", "map")) },
  { id: "sayings", label: "The great sayings (mahāvākyas)", icon: <Quote size={15} />, run: () => go(href("study", "sayings")) },
  { id: "cited", label: "Śruti most cited", icon: <BookMarked size={15} />, run: () => go(href("study", "citations")) },
  { id: "notes", label: "My notes", icon: <StickyNote size={15} />, run: () => go(href("study", "notes")) },
  { id: "theme", label: "Switch theme", icon: <Moon size={15} />, run: () => send(THEME) },
  { id: "type", label: "Reading settings", icon: <Type size={15} />, run: () => send(TYPOGRAPHY) },
  { id: "keys", label: "Keyboard shortcuts", icon: <Keyboard size={15} />, run: () => send(SHORTCUTS) },
];

// Study data for the palette, loaded the first time it opens on a Study page.
function useStudyIndex(enabled: boolean) {
  const [docs, setDocs] = useState<LibraryDocument[]>([]);
  const [concepts, setConcepts] = useState<ConceptSummary[]>([]);
  const [sayings, setSayings] = useState<SayingSummary[]>([]);
  useEffect(() => {
    if (!enabled || docs.length) return;
    getJSON<LibraryDocument[]>("/api/library").then(setDocs).catch(() => undefined);
    getJSON<ConceptSummary[]>("/api/concepts").then(setConcepts).catch(() => undefined);
    getJSON<SayingSummary[]>("/api/sayings").then(setSayings).catch(() => undefined);
  }, [enabled]);
  return { docs, concepts, sayings };
}

// ⌘K / Ctrl+K: jump anywhere. In the chat it offers actions only: titles, verses and
// concepts are document metadata, which the chat never shows.
export function Palette({ section }: { section: "chat" | "study" }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [located, setLocated] = useState<Located | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const study = section === "study";
  const index = useStudyIndex(open && study);

  // Cleared before opening, so nothing typed lands in the previous query.
  const state = useRef(open);
  state.current = open;
  useEffect(() => {
    const show = () => {
      setQuery("");
      setActive(0);
      setLocated(null);
      setOpen(true);
    };
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (state.current) setOpen(false);
        else show();
      }
    };
    window.addEventListener("keydown", key);
    window.addEventListener(PALETTE, show);
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener(PALETTE, show);
    };
  }, []);
  useEffect(() => {
    if (open) dialog.current?.showModal();
  }, [open]);
  // Typed scripture references are looked up as the reader types (Study only).
  useEffect(() => {
    setLocated(null);
    if (!study || !/\d/.test(query) || sutraRef(query)) return;
    const timer = window.setTimeout(() => {
      getJSON<Located>(`/api/locate?ref=${encodeURIComponent(query.trim())}`)
        .then(setLocated)
        .catch(() => setLocated(null));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [query, study]);

  const items = useMemo(() => {
    const q = query.trim();
    const out: Item[] = [];
    const sutra = study ? sutraRef(q) : null;
    if (sutra)
      out.push({
        id: "bs",
        group: "Go to",
        label: `Brahma Sūtra ${sutra.join(".")}`,
        hint: "Side by side",
        icon: <Columns2 size={15} />,
        run: () => go(href("study", "sutra", ...sutra)),
      });
    if (located)
      out.push({
        id: "verse",
        group: "Go to",
        label: `${located.document} ${located.place}${located.verse ? `, ${located.verse}` : ""}`,
        hint: located.exact ? "Verse" : "Whole section",
        icon: <ScrollText size={15} />,
        run: () => go(readAt(located.chapter_id, located.start, located.end)),
      });
    const actions = q ? rank(q, ACTIONS, (a) => a.label, 6) : ACTIONS;
    out.push(...actions.map((a) => ({ ...a, group: "Actions" })));
    if (study && q) {
      out.push(
        ...rank(
          q,
          index.sayings.filter((s) => s.found),
          (s) => `${s.saying} ${s.english} mahavakya great saying`,
          2,
        ).map(
          (s): Item => ({
            id: `saying-${s.key}`,
            group: "Great sayings",
            label: s.saying,
            hint: `Great saying · ${s.english}`,
            icon: <Quote size={15} />,
            run: () => go(href("study", "saying", s.key)),
          }),
        ),
      );
      out.push(
        ...rank(q, index.docs, (d) => `${d.document} ${d.author} ${d.translator}`, 5).map(
          (d): Item => ({
            id: `doc-${d.document_id}-${d.edition}`,
            group: "Texts",
            label: d.document,
            hint: [d.author, `tr. ${d.translator}`].filter(Boolean).join(" · "),
            icon: <BookOpen size={15} />,
            run: () => go(href("study", "read", d.chapters[0].id)),
          }),
        ),
        ...rank(
          q,
          index.concepts,
          (c) => [c.term, ...c.aliases, ...(c.english ?? [])].join(" "),
          4,
        ).map(
          (c): Item => ({
            id: `concept-${c.slug}`,
            group: "Concepts",
            label: c.term,
            hint: c.english?.[0] ? `Concept · ${c.english[0]}` : "Concept",
            icon: <Lightbulb size={15} />,
            run: () => go(href("study", "concept", c.slug)),
          }),
        ),
      );
    }
    if (q) {
      out.push({
        id: "ask-q",
        group: "Ask or search",
        label: `Ask: ${q}`,
        icon: <MessageCircleQuestion size={15} />,
        run: () => (go("#/"), send(ASK, q)),
      });
      out.push({
        id: "search-q",
        group: "Ask or search",
        label: `Search the texts for “${q}”`,
        icon: <Search size={15} />,
        run: () => go(`${href("study", "search")}?${new URLSearchParams({ q, m: "hybrid" })}`),
      });
    }
    return out;
  }, [query, located, study, index.docs, index.concepts, index.sayings]);

  const current = Math.min(active, Math.max(0, items.length - 1));
  useEffect(() => {
    const id = items[current]?.id;
    if (id) document.getElementById(`palette-${id}`)?.scrollIntoView({ block: "nearest" });
  }, [current, items]);
  function choose(item: Item | undefined) {
    if (!item) return;
    // The dialog's close event comes later (a task); the state must not wait for it.
    setOpen(false);
    item.run();
  }
  if (!open) return null;
  let lastGroup = "";
  return (
    <dialog
      ref={dialog}
      className="palette"
      aria-label="Command palette"
      onClose={() => setOpen(false)}
      onClick={(event) => event.target === dialog.current && dialog.current.close()}
    >
      <div className="palette-input">
        <Search size={17} aria-hidden="true" />
        <input
          autoFocus
          role="combobox"
          aria-expanded="true"
          aria-controls="palette-list"
          aria-activedescendant={items[current] ? `palette-${items[current].id}` : undefined}
          aria-label="Go to, ask or search"
          placeholder={study ? "Go to a text, verse (Ch 6.8.7, BS 1.1.4), concept…" : "Go to, ask or search…"}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              const step = event.key === "ArrowDown" ? 1 : -1;
              setActive((current + step + items.length) % Math.max(1, items.length));
            } else if (event.key === "Enter") {
              event.preventDefault();
              choose(items[current]);
            }
          }}
        />
        <kbd>Esc</kbd>
      </div>
      <ul id="palette-list" role="listbox" aria-label="Results">
        {items.flatMap((item, i) => {
          const heading = item.group !== lastGroup;
          lastGroup = item.group;
          return [
            heading && (
              <li key={`g-${item.group}`} role="presentation" className="palette-group">
                {item.group}
              </li>
            ),
            <li
              key={item.id}
              id={`palette-${item.id}`}
              role="option"
              aria-selected={i === current}
              className="palette-item"
              onPointerMove={() => i !== current && setActive(i)}
              onClick={() => choose(item)}
            >
              {item.icon}
              <span className="palette-label">{item.label}</span>
              {item.hint && <span className="palette-hint">{item.hint}</span>}
            </li>,
          ];
        })}
      </ul>
    </dialog>
  );
}
