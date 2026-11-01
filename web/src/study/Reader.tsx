import { useEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Columns2,
  List,
  X,
  Highlighter,
  MessageCircleQuestion,
  NotebookPen,
} from "lucide-react";
import { placeLabel } from "../lib/api.ts";
import type { ChapterContext } from "../lib/api.ts";
import type { Glossary } from "../lib/glossary.tsx";
import { href } from "../lib/router.ts";
import type { Route } from "../lib/router.ts";
import { setPendingFocus } from "../lib/storage.ts";
import type { FocusRef } from "../lib/storage.ts";
import { codePointIndex, codePointOf, locate } from "../lib/offsets.ts";
import { useNotes } from "../lib/notes.ts";
import { isShortcut } from "../lib/keys.ts";
import { useProgress, workKey } from "../lib/progress.ts";
import { ChapterText } from "./ChapterText.tsx";
import { useChapter, useCitations, useLibrary } from "./data.ts";
import { Status } from "./Status.tsx";

function SourceNote({ context }: { context: ChapterContext }) {
  const { chapter } = context;
  return (
    <footer className="source-note">
      <p>
        <strong>{chapter.document}</strong>
        {chapter.author && <> · {chapter.author}</>} · tr. {chapter.translator}
      </p>
      <p>{chapter.edition}</p>
      <p>{chapter.source.rights}</p>
      <p>{chapter.source.attribution}</p>
      {chapter.source.url ? (
        <p>
          <a href={chapter.source.url} target="_blank" rel="noreferrer">
            Original page
          </a>
        </p>
      ) : (
        <p>Private local edition; not distributed.</p>
      )}
    </footer>
  );
}

// Hand a passage to the chat: only a pointer travels; the chat never shows the text.
export function askAbout(focus: FocusRef) {
  if (setPendingFocus(focus)) window.location.hash = "#/";
}

// The reader's selection as code points in the chapter, with where to show the button.
function selectionFocus(container: HTMLElement, text: string, chapterId: string) {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || !selection.rangeCount) return null;
  const range = selection.getRangeAt(0);
  if (!container.contains(range.commonAncestorContainer)) return null;
  const paragraph = (node: Node) =>
    (node instanceof Element ? node : node.parentElement)?.closest<HTMLElement>(
      "p[data-from]",
    );
  const first = paragraph(range.startContainer);
  const last = paragraph(range.endContainer);
  const selected = selection.toString();
  if (!first || !last || selected.trim().length < 2) return null;
  const from = Number(first.dataset.from);
  const to = Number(last.dataset.to);
  // Exact words when they occur once; otherwise the paragraphs the selection touches.
  const span = locate(text, selected, from, to) ?? { start: from, end: to };
  const start = codePointOf(text, span.start);
  const end = codePointOf(text, span.end);
  if (end - start > 6000) return null;
  const box = container.getBoundingClientRect();
  const rect = range.getBoundingClientRect();
  return {
    focus: { chapter_id: chapterId, start, end },
    top: rect.bottom - box.top + 8,
    left: Math.max(0, Math.min(rect.left - box.left, box.width - 170)),
  };
}

export function Reader({
  id,
  route,
  glossary,
}: {
  id: string;
  route: Route;
  glossary: Glossary | null;
}) {
  const { context, error } = useChapter(id);
  const citations = useCitations(id);
  const { docs } = useLibrary();
  const textBox = useRef<HTMLDivElement>(null);
  const [ask, setAsk] = useState<ReturnType<typeof selectionFocus>>(null);
  // The note being written or edited: a new selection, or an existing note's id.
  const [editing, setEditing] = useState<{
    id?: string;
    focus?: FocusRef;
    text: string;
    top: number;
    left: number;
  } | null>(null);
  const study = useNotes();
  const [contentsOpen, setContentsOpen] = useState(false);
  const [fraction, setFraction] = useState(0);
  const { save: saveProgress } = useProgress();
  const doc = context
    ? docs?.find(
        (d) =>
          d.document_id === context.chapter.document_id &&
          d.edition === context.chapter.edition,
      )
    : undefined;
  const work = doc ? workKey(doc.document_id, doc.edition) : null;
  useEffect(() => {
    setAsk(null);
    setEditing(null);
    setContentsOpen(false);
  }, [id]);
  // How far down the part the reader is: a bar at the top, and progress kept in this
  // browser for "Continue reading". "?p=" (from that link) returns to the same place.
  useEffect(() => {
    const main = textBox.current?.closest("main");
    if (!main || !context || context.id !== id || !work) return;
    const resume = Number(route.query.get("p"));
    if (resume > 0 && resume <= 1 && !route.query.has("s"))
      requestAnimationFrame(() => {
        main.scrollTop = resume * (main.scrollHeight - main.clientHeight);
      });
    let timer = 0;
    const measure = () => {
      const room = main.scrollHeight - main.clientHeight;
      const f = room <= 0 ? 1 : Math.min(1, main.scrollTop / room);
      setFraction(f);
      window.clearTimeout(timer);
      timer = window.setTimeout(() => saveProgress(work, context.id, f), 400);
    };
    measure();
    main.addEventListener("scroll", measure, { passive: true });
    return () => {
      window.clearTimeout(timer);
      main.removeEventListener("scroll", measure);
    };
  }, [context?.id, work]);
  // ← and → turn the page; t opens the contents.
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (!context || !isShortcut(event)) return;
      const to =
        event.key === "ArrowLeft"
          ? context.previous
          : event.key === "ArrowRight"
            ? context.next
            : null;
      if (to) window.location.hash = href("study", "read", to);
      else if (event.key === "t") setContentsOpen((open) => !open);
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [context]);
  if (!context) return <Status error={error} />;
  const onSelect = () => {
    if (editing) return;
    setAsk(
      textBox.current
        ? selectionFocus(textBox.current, context.chapter.text, context.id)
        : null,
    );
  };
  const at = codePointIndex(context.chapter.text);
  const mine = study.notes.filter((n) => n.chapter_id === context.id);
  // A note whose words no longer match the stored text is listed, not drawn.
  const fits = (n: (typeof mine)[number]) =>
    context.chapter.text.slice(at(n.start), at(n.end)) === n.quote;
  const drawn = mine.filter(fits);
  const moved = mine.filter((n) => !fits(n));
  const save = (focus: FocusRef, note: string) =>
    study.add({
      ...focus,
      quote: context.chapter.text.slice(at(focus.start), at(focus.end)),
      note,
      document: context.chapter.document,
      place: placeLabel(category, context.chapter.location),
    });
  const openMark = (event: ReactMouseEvent) => {
    const el = (event.target as HTMLElement).closest<HTMLElement>("[data-mark]");
    const note = el && mine.find((n) => n.id === el.dataset.mark);
    if (!note || !textBox.current || window.getSelection()?.toString()) return;
    const box = textBox.current.getBoundingClientRect();
    const rect = el.getBoundingClientRect();
    setAsk(null);
    setEditing({
      id: note.id,
      text: note.note,
      top: rect.bottom - box.top + 8,
      left: Math.max(0, Math.min(rect.left - box.left, box.width - 320)),
    });
  };
  const { chapter } = context;
  const category = doc?.category ?? "";
  const start = Number(route.query.get("s"));
  const end = Number(route.query.get("e"));
  const highlight =
    route.query.has("s") &&
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    start <= end
      ? { start, end }
      : undefined;
  const sutra = chapter.location.sections[0];
  return (
    <article className="reader">
      <div className="reading-progress" aria-hidden="true">
        <span style={{ transform: `scaleX(${fraction})` }} />
      </div>
      <nav className="reader-nav" aria-label="Chapter navigation">
        <span className="crumbs">
          <a href={href("study")}>Library</a>
          <span aria-hidden="true">›</span>
          {doc && doc.chapters.length > 1 ? (
            <button
              type="button"
              className="contents-button"
              aria-haspopup="dialog"
              aria-keyshortcuts="t"
              onClick={() => setContentsOpen(true)}
            >
              <List size={14} /> {chapter.document}
            </button>
          ) : (
            <span>{chapter.document}</span>
          )}
        </span>
        <span>
          {context.previous && (
            <a
              href={href("study", "read", context.previous)}
              aria-label="Previous part"
            >
              <ArrowLeft size={14} /> Previous
            </a>
          )}
          {context.next && (
            <a
              href={href("study", "read", context.next)}
              aria-label="Next part"
            >
              Next <ArrowRight size={14} />
            </a>
          )}
        </span>
      </nav>
      <header className="reader-head">
        <p className="eyebrow">{category || chapter.content_type}</p>
        <h1 data-title={`${chapter.document} ${placeLabel(category, chapter.location)}`}>
          {chapter.document}
        </h1>
        <p className="reader-place">{placeLabel(category, chapter.location)}</p>
        {category === "Brahma Sūtra" && /^\d+$/.test(sutra ?? "") && (
          <a
            className="reader-parallel"
            href={href(
              "study",
              "sutra",
              chapter.location.book,
              chapter.location.chapter,
              sutra!,
            )}
          >
            <Columns2 size={14} /> Compare commentaries on this sūtra
          </a>
        )}
      </header>
      {context.roles.length > 0 && (
        <p className="role-legend">
          <span className="role-objection">Objection</span>
          <span className="role-reply">Reply</span> marked only where the book
          itself labels them.
        </p>
      )}
      {moved.length > 0 && (
        <p className="notes-moved" role="status">
          {moved.length === 1 ? "One of your notes" : `${moved.length} of your notes`} no
          longer match this text; they are kept in <a href={href("study", "notes")}>My
          notes</a>.
        </p>
      )}
      <div
        className="reader-text"
        ref={textBox}
        onMouseUp={onSelect}
        onKeyUp={onSelect}
        onTouchEnd={() => setTimeout(onSelect, 0)}
        onClick={openMark}
      >
        <ChapterText
          context={context}
          glossary={glossary}
          highlight={highlight}
          citations={citations}
          marks={drawn}
        />
        {ask && !editing && (
          <div
            className="selection-tools"
            style={{ top: ask.top, left: ask.left }}
            // Keep the selection while a tool is pressed.
            onMouseDown={(event) => event.preventDefault()}
          >
            <button type="button" onClick={() => askAbout(ask.focus)}>
              <MessageCircleQuestion size={14} /> Ask about this
            </button>
            <button
              type="button"
              onClick={() => {
                save(ask.focus, "");
                setAsk(null);
                window.getSelection()?.removeAllRanges();
              }}
            >
              <Highlighter size={14} /> Highlight
            </button>
            <button
              type="button"
              onClick={() => {
                setEditing({ focus: ask.focus, text: "", top: ask.top, left: ask.left });
                setAsk(null);
              }}
            >
              <NotebookPen size={14} /> Note
            </button>
          </div>
        )}
        {editing && (
          <form
            className="note-editor"
            style={{ top: editing.top, left: editing.left }}
            onSubmit={(event) => {
              event.preventDefault();
              if (editing.id) study.update(editing.id, editing.text.trim());
              else if (editing.focus) save(editing.focus, editing.text.trim());
              setEditing(null);
              window.getSelection()?.removeAllRanges();
            }}
          >
            <label className="sr-only" htmlFor="note-text">
              Your note
            </label>
            <textarea
              id="note-text"
              autoFocus
              rows={3}
              maxLength={4000}
              placeholder="Your note (kept in this browser only)"
              value={editing.text}
              onChange={(event) => setEditing({ ...editing, text: event.target.value })}
              onKeyDown={(event) => event.key === "Escape" && setEditing(null)}
            />
            <div className="note-actions">
              {editing.id && (
                <button
                  type="button"
                  className="danger"
                  onClick={() => {
                    study.remove(editing.id!);
                    setEditing(null);
                  }}
                >
                  Delete
                </button>
              )}
              <button type="button" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button type="submit" className="primary">
                Save
              </button>
            </div>
          </form>
        )}
      </div>
      {study.failed && (
        <p className="study-status" role="alert">
          This browser would not save the note (storage is full or disabled).
        </p>
      )}
      {highlight && highlight.end - highlight.start <= 6000 && (
        // Sticks to the bottom of the screen while the highlighted page is read.
        <div className="reader-ask-bar">
          <button
            type="button"
            className="reader-ask"
            onClick={() => askAbout({ chapter_id: context.id, ...highlight })}
          >
            <MessageCircleQuestion size={14} /> Ask about the highlighted passage
          </button>
        </div>
      )}
      <SourceNote context={context} />
      {contentsOpen && doc && (
        <Contents
          title={chapter.document}
          current={context.id}
          parts={doc.chapters.map((c) => [c.id, placeLabel(category, c.location)])}
          onClose={() => setContentsOpen(false)}
        />
      )}
    </article>
  );
}

// The parts of the open work, as a modal side sheet (Escape and the backdrop close it).
function Contents({
  title,
  current,
  parts,
  onClose,
}: {
  title: string;
  current: string;
  parts: [string, string][];
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const box = dialog.current;
    if (!box) return;
    box.showModal();
    box.querySelector<HTMLElement>("[aria-current]")?.scrollIntoView({ block: "center" });
    return () => box.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="contents-sheet"
      aria-label={`Contents of ${title}`}
      onClose={onClose}
      onClick={(event) => event.target === dialog.current && onClose()}
    >
      <header>
        <h2>{title}</h2>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close contents">
          <X size={16} />
        </button>
      </header>
      <ol>
        {parts.map(([partId, label]) => (
          <li key={partId}>
            <a
              href={href("study", "read", partId)}
              aria-current={partId === current ? "page" : undefined}
            >
              {label}
            </a>
          </li>
        ))}
      </ol>
    </dialog>
  );
}
