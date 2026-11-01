import type { KeyboardEvent } from "react";
import { Highlighter, MessageCircleQuestion, NotebookPen } from "lucide-react";

// Words selected in an answer, with where to show the tools (viewport coordinates).
export type Quote = {
  text: string;
  full: string;
  turn: string;
  top: number;
  left: number;
};
export type Noting = Quote & { note: string };

// The selection under the pointer, if it lies in an answer.
export function quoteFromSelection(): Quote | null {
  const selection = window.getSelection();
  const text = selection?.toString().replace(/\s+/g, " ").trim() ?? "";
  const node = selection?.anchorNode;
  const element = node instanceof Element ? node : node?.parentElement;
  const inAnswer = element?.closest(".answer-prose");
  const turn = element?.closest<HTMLElement>("[data-turn]")?.dataset.turn ?? "";
  if (!selection || !selection.rangeCount || !inAnswer || text.length < 2) return null;
  const rect = selection.getRangeAt(0).getBoundingClientRect();
  return {
    text: text.length > 300 ? `${text.slice(0, 300)}…` : text,
    full: text.slice(0, 2000),
    turn,
    top: rect.bottom + 8,
    left: Math.max(8, Math.min(rect.left, window.innerWidth - 180)),
  };
}

// Escape closes the popover only; it must not also stop an answer being written.
function closeOnEscape(event: KeyboardEvent, close: () => void) {
  if (event.key !== "Escape") return;
  event.preventDefault();
  event.stopPropagation();
  close();
}

export function SelectionTools({
  quote,
  onAsk,
  onHighlight,
  onNote,
  onClose,
}: {
  quote: Quote;
  onAsk: () => void;
  onHighlight: () => void;
  onNote: () => void;
  onClose: () => void;
}) {
  return (
    <div
      className="selection-tools quote-ask"
      role="toolbar"
      aria-label="Selected words"
      style={{ top: quote.top, left: quote.left }}
      // Keep the selection while a tool is pressed.
      onMouseDown={(event) => event.preventDefault()}
      onKeyDown={(event) => closeOnEscape(event, onClose)}
    >
      <button type="button" onClick={onAsk}>
        <MessageCircleQuestion size={14} /> Ask about this
      </button>
      <button type="button" onClick={onHighlight}>
        <Highlighter size={14} /> Highlight
      </button>
      <button type="button" onClick={onNote}>
        <NotebookPen size={14} /> Note
      </button>
    </div>
  );
}

export function NoteEditor({
  noting,
  onChange,
  onSave,
  onClose,
}: {
  noting: Noting;
  onChange: (note: string) => void;
  onSave: () => void;
  onClose: () => void;
}) {
  return (
    <form
      className="note-editor quote-ask"
      style={{ top: noting.top, left: Math.min(noting.left, window.innerWidth - 330) }}
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
      onKeyDown={(event) => closeOnEscape(event, onClose)}
    >
      <label className="sr-only" htmlFor="answer-note">
        Your note
      </label>
      <textarea
        id="answer-note"
        autoFocus
        rows={3}
        maxLength={4000}
        placeholder="Your note (kept in this browser, in My notes)"
        value={noting.note}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="note-actions">
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="primary">
          Save
        </button>
      </div>
    </form>
  );
}
