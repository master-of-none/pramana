import { useState } from "react";
import type { ChangeEvent } from "react";
import { ArrowLeft, Download, Upload } from "lucide-react";
import { download, mergeNotes, notesMarkdown, parseNotes, useNotes } from "../lib/notes.ts";
import { href, readAt } from "../lib/router.ts";

// Every highlight and note in this browser, by work, with export and import.
export function Notes() {
  const study = useNotes();
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const [message, setMessage] = useState("");
  const groups = new Map<string, typeof study.notes>();
  for (const n of [...study.notes].sort(
    (a, b) => a.document.localeCompare(b.document) || a.place.localeCompare(b.place) || a.start - b.start,
  ))
    groups.set(n.document, [...(groups.get(n.document) ?? []), n]);
  const stamp = new Date().toISOString().slice(0, 10);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const incoming = parseNotes(JSON.parse(await file.text()));
      study.replaceAll(mergeNotes(study.notes, incoming));
      setMessage(
        incoming.length
          ? `Imported ${incoming.length} ${incoming.length === 1 ? "note" : "notes"}.`
          : "That file held no notes Pramana could read.",
      );
    } catch {
      setMessage("That file is not a Pramana notes export.");
    }
  }

  return (
    <article className="notes-page">
      <nav className="reader-nav">
        <a href={href("study")}>
          <ArrowLeft size={14} /> Library
        </a>
      </nav>
      <header className="study-intro">
        <h1>My notes</h1>
        <p>
          Highlights and notes you made in the reader. They stay in this browser and are
          never sent anywhere; export them to keep a copy or to move them to another
          browser.
        </p>
        <div className="study-actions">
          <button
            type="button"
            disabled={!study.notes.length}
            onClick={() =>
              download(`pramana-notes-${stamp}.md`, "text/markdown", notesMarkdown(study.notes))
            }
          >
            <Download size={15} /> Export Markdown
          </button>
          <button
            type="button"
            disabled={!study.notes.length}
            onClick={() =>
              download(
                `pramana-notes-${stamp}.json`,
                "application/json",
                JSON.stringify(study.notes, null, 1),
              )
            }
          >
            <Download size={15} /> Export JSON
          </button>
          <label className="import-notes">
            <Upload size={15} /> Import JSON
            <input type="file" accept="application/json,.json" onChange={importFile} />
          </label>
        </div>
        {(message || study.failed) && (
          <p className="study-status" role="status">
            {study.failed ? "This browser would not save the change." : message}
          </p>
        )}
      </header>
      {!study.notes.length && (
        <p className="study-status">
          No notes yet. Select words in any text and choose Highlight or Note.
        </p>
      )}
      {[...groups].map(([document, items]) => (
        <section key={document} className="notes-group">
          <h2>{document || "Untitled"}</h2>
          <ul>
            {items.map((n) => (
              <li key={n.id} className="note-item">
                <a href={readAt(n.chapter_id, n.start, n.end)} className="note-place">
                  {n.place}
                </a>
                <blockquote>{n.quote.length > 400 ? `${n.quote.slice(0, 400)}…` : n.quote}</blockquote>
                {editing?.id === n.id ? (
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      study.update(n.id, editing.text.trim());
                      setEditing(null);
                    }}
                  >
                    <textarea
                      aria-label="Your note"
                      rows={3}
                      maxLength={4000}
                      value={editing.text}
                      onChange={(event) => setEditing({ id: n.id, text: event.target.value })}
                    />
                    <div className="note-actions">
                      <button type="button" onClick={() => setEditing(null)}>
                        Cancel
                      </button>
                      <button type="submit" className="primary">
                        Save
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    {n.note && <p className="note-text">{n.note}</p>}
                    <div className="note-actions">
                      <button type="button" onClick={() => setEditing({ id: n.id, text: n.note })}>
                        {n.note ? "Edit note" : "Add a note"}
                      </button>
                      <button type="button" className="danger" onClick={() => study.remove(n.id)}>
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </article>
  );
}
