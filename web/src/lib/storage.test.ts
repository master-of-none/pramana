// Run with: npm --prefix web test (Node's built-in runner; no extra dependency).
import assert from "node:assert/strict";
import test from "node:test";
import { conversationMarkdown, trail } from "./storage.ts";

test("an exported conversation holds questions and answers, never evidence", () => {
  const md = conversationMarkdown(
    [
      {
        id: "a",
        question: "How do they\ndiffer?",
        answer: "They read it differently.",
        perspectives: [{ thinker: "Śaṅkara", view: "Non-dual." }],
        evidence: [{ passage: "ps_0123456789ab", chapter: "ch_0123456789ab", start: 1, end: 9 }],
        state: "complete",
      },
      { id: "b", question: "And then?", state: "cancelled", error: "Stopped." },
    ],
    new Date("2026-11-01T10:00:00Z"),
  );
  assert.equal(
    md,
    "# Conversation with Pramana\n\n_2026-11-01_\n\n## How do they differ?\n\n" +
      "They read it differently.\n\n### Śaṅkara\n\nNon-dual.\n\n## And then?\n\n_No answer._\n",
  );
  assert.ok(!md.includes("ps_") && !md.includes("ch_"));
});

test("the answer trail keeps kept sentences and only this turn's passages", () => {
  const evidence = [{ passage: "p_0123456789ab", chapter: "ch_0123456789ab", start: 0, end: 5 }];
  const steps = trail(
    [
      { part: "answer", text: "Brahman is real.", verdict: "supported", passages: ["p_0123456789ab", "p_ffffffffffff"] },
      { part: "answer", text: "Removed.", verdict: "unsupported", passages: ["p_0123456789ab"] },
      { part: "Śaṅkara", text: "Partly so.", verdict: "partly", passages: "nope" },
      { part: "answer", text: "   ", verdict: "supported", passages: [] },
      null,
    ],
    evidence,
  );
  assert.deepEqual(steps, [
    { part: "answer", text: "Brahman is real.", verdict: "supported", passages: ["p_0123456789ab"] },
    { part: "Śaṅkara", text: "Partly so.", verdict: "partly", passages: [] },
  ]);
  assert.deepEqual(trail("x", evidence), []);
});
