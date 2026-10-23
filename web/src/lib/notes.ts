import { useEffect, useState } from "react";

// Highlights and notes on the texts, kept in this browser only (localStorage). They are
// never sent to the server or to a model. Offsets are Python code points in the stored
// chapter text; `quote` is the text they covered, so a changed text is detected.
export type StudyNote = {
  id: string;
  // "text": a span of a stored chapter; "answer": words from a chat answer.
  kind: "text" | "answer";
  // Answer notes: the turn they came from (for highlighting) and its question.
  turn_id: string;
  question: string;
  chapter_id: string;
  start: number;
  end: number;
  quote: string;
  note: string;
  document: string;
  place: string;
  created: string;
  updated: string;
};

export const NOTES = "pramana.notes.v1";
const CHAPTER = /^ch_[0-9a-f]{12,64}$/;
const LIMITS = { quote: 2000, note: 4000, label: 300, notes: 5000 };

// Keeps only well-formed notes; used for storage and for imported files alike.
export function parseNotes(data: unknown): StudyNote[] {
  if (!Array.isArray(data)) return [];
  const seen = new Set<string>();
  return data
    .filter(
      (n) =>
        n &&
        typeof n.id === "string" &&
        n.id.length <= 80 &&
        (n.kind === "answer"
          ? typeof n.question === "string" && n.question.length <= 2000 && n.quote.length > 0
          : typeof n.chapter_id === "string" &&
            CHAPTER.test(n.chapter_id) &&
            Number.isInteger(n.start) &&
            Number.isInteger(n.end) &&
            0 <= n.start &&
            n.start < n.end) &&
        typeof n.quote === "string" &&
        n.quote.length <= LIMITS.quote &&
        typeof n.note === "string" &&
        n.note.length <= LIMITS.note,
    )
    .filter((n) => !seen.has(n.id) && seen.add(n.id))
    .slice(0, LIMITS.notes)
    .map((n) => ({
      id: n.id,
      kind: n.kind === "answer" ? "answer" : "text",
      turn_id: n.kind === "answer" ? String(n.turn_id ?? "").slice(0, 80) : "",
      question: n.kind === "answer" ? n.question : "",
      chapter_id: n.kind === "answer" ? "" : n.chapter_id,
      start: n.kind === "answer" ? 0 : n.start,
      end: n.kind === "answer" ? 0 : n.end,
      quote: n.quote,
      note: n.note,
      document: String(n.document ?? "").slice(0, LIMITS.label),
      place: String(n.place ?? "").slice(0, LIMITS.label),
      created: String(n.created ?? ""),
      updated: String(n.updated ?? n.created ?? ""),
    }));
}

// Imported notes join the existing ones; for a shared id the later update wins.
export function mergeNotes(current: StudyNote[], incoming: StudyNote[]): StudyNote[] {
  const byId = new Map(current.map((n) => [n.id, n]));
  for (const n of incoming) {
    const old = byId.get(n.id);
    if (!old || n.updated > old.updated) byId.set(n.id, n);
  }
  return [...byId.values()];
}

export function notesMarkdown(notes: StudyNote[]): string {
  const groups = new Map<string, StudyNote[]>();
  for (const n of notes) {
    const group = n.kind === "answer" ? "From conversations" : n.document;
    groups.set(group, [...(groups.get(group) ?? []), n]);
  }
  const lines = ["# Study notes", ""];
  for (const [document, items] of groups) {
    lines.push(`## ${document || "Untitled"}`, "");
    for (const n of items.sort((a, b) => a.place.localeCompare(b.place) || a.start - b.start)) {
      const heading = n.kind === "answer" ? `Asked: ${n.question}` : n.place;
      lines.push(`**${heading}**`, "", ...n.quote.split("\n").map((l) => `> ${l}`), "");
      if (n.note.trim()) lines.push(n.note.trim(), "");
    }
  }
  return lines.join("\n");
}

function read(): StudyNote[] {
  try {
    return parseNotes(JSON.parse(localStorage.getItem(NOTES) || "[]"));
  } catch {
    return [];
  }
}

function write(notes: StudyNote[]): boolean {
  try {
    localStorage.setItem(NOTES, JSON.stringify(notes));
    window.dispatchEvent(new Event("pramana-notes"));
    return true;
  } catch {
    return false;
  }
}

// All notes, kept in step across components and other tabs of this browser.
export function useNotes() {
  const [notes, setNotes] = useState<StudyNote[]>(read);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const refresh = () => setNotes(read());
    window.addEventListener("pramana-notes", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("pramana-notes", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);
  const commit = (next: StudyNote[]) => setFailed(!write(next));
  return {
    notes,
    failed,
    add(note: Partial<StudyNote> & Pick<StudyNote, "quote" | "note">) {
      const now = new Date().toISOString();
      const created: StudyNote = {
        kind: "text",
        turn_id: "",
        question: "",
        chapter_id: "",
        start: 0,
        end: 0,
        document: "",
        place: "",
        ...note,
        id: crypto.randomUUID(),
        created: now,
        updated: now,
      };
      commit([...read(), created]);
      return created;
    },
    update(id: string, text: string) {
      const now = new Date().toISOString();
      commit(read().map((n) => (n.id === id ? { ...n, note: text, updated: now } : n)));
    },
    remove(id: string) {
      commit(read().filter((n) => n.id !== id));
    },
    replaceAll(next: StudyNote[]) {
      commit(next);
    },
  };
}

export function download(name: string, type: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
