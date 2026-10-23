// Run with: npm --prefix web test (Node's built-in runner; no extra dependency).
import assert from "node:assert/strict";
import test from "node:test";
import { mergeNotes, notesMarkdown, parseNotes } from "./notes.ts";

const note = {
  id: "n1",
  chapter_id: "ch_31ceb6f366ee8713336a7da8",
  start: 10,
  end: 40,
  quote: "And he is that great unborn Self",
  note: "Cited by both commentators.",
  document: "Brihadaranyaka Upanishad",
  place: "IV, 4",
  created: "2026-10-23T10:00:00Z",
  updated: "2026-10-23T10:00:00Z",
};

test("only well-formed notes are kept", () => {
  const kept = parseNotes([
    note,
    { ...note, id: "n1" }, // duplicate id
    { ...note, id: "n2", start: 40, end: 10 }, // empty span
    { ...note, id: "n3", chapter_id: "../etc" }, // not a chapter id
    { ...note, id: "n4", note: "x".repeat(5000) }, // too long
    "nonsense",
  ]);
  assert.deepEqual(kept.map((n) => n.id), ["n1"]);
  assert.deepEqual(parseNotes({ not: "a list" }), []);
});

test("imports merge by id, the later update winning", () => {
  const newer = { ...note, note: "Edited.", updated: "2026-10-24T10:00:00Z" };
  const other = { ...note, id: "n9" };
  const merged = mergeNotes([note], [newer, other]);
  assert.equal(merged.length, 2);
  assert.equal(merged.find((n) => n.id === "n1")?.note, "Edited.");
  assert.equal(mergeNotes([newer], [note])[0].note, "Edited."); // older import ignored
});

test("Markdown export quotes the passage, then the note", () => {
  const text = notesMarkdown([note]);
  assert.match(text, /## Brihadaranyaka Upanishad/);
  assert.match(text, /\*\*IV, 4\*\*\n\n> And he is that great unborn Self\n\nCited by both/);
});
