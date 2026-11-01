// Run with: npm --prefix web test (Node's built-in runner; no extra dependency).
import assert from "node:assert/strict";
import test from "node:test";
import { marks, rank, score, sutraRef } from "./fuzzy.ts";

test("matching ignores accents and prefers whole words", () => {
  assert.ok(score("sankara", "Śaṅkara's commentary") > 0);
  assert.ok(score("atman", "the Self (ātman)") > score("atman", "xatmanx"));
  assert.equal(score("zzz", "Brahman"), -1);
  assert.ok(score("bsu", "Brahma Sūtra") > 0); // letters in order
});

test("ranking keeps matches only, best first", () => {
  const items = ["Muṇḍaka Upaniṣad", "Kaṭha Upaniṣad", "My notes"];
  assert.deepEqual(rank("katha", items, (i) => i), ["Kaṭha Upaniṣad"]);
  assert.deepEqual(rank("up", items, (i) => i).length, 2);
});

test("sūtra references are read only when complete", () => {
  assert.deepEqual(sutraRef("BS 1.1.4"), [1, 1, 4]);
  assert.deepEqual(sutraRef("Brahma Sūtra 2, 1, 14"), [2, 1, 14]);
  assert.equal(sutraRef("BS 1.1"), null);
  assert.equal(sutraRef("Ch 6.8.7"), null);
});

test("query words are marked in snippets whatever their accents", () => {
  assert.deepEqual(marks("The Ātman is the witness.", "atman witness"), [
    "The ",
    { hit: "Ātman" },
    " is the ",
    { hit: "witness" },
    ".",
  ]);
  assert.deepEqual(marks("𑀅 Brahman", "brahman"), ["𑀅 ", { hit: "Brahman" }]);
  assert.deepEqual(marks("Nothing here", "the of"), ["Nothing here"]);
});
