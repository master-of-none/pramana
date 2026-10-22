// Run with: npm --prefix web test (Node's built-in runner; no extra dependency).
import assert from "node:assert/strict";
import test from "node:test";
import { codePointIndex, cuts } from "./offsets.ts";

test("BMP-only text maps code points to themselves", () => {
  const at = codePointIndex("Ānanda");
  assert.equal(at(3), 3);
});

test("supplementary characters before and inside a span", () => {
  const text = "𑀅 Ātman 𑀅𑀆 is Brahman.";
  const at = codePointIndex(text);
  // Python: text[2:7] == "Ātman", text[8:10] == "𑀅𑀆"
  assert.equal(text.slice(at(2), at(7)), "Ātman");
  assert.equal(text.slice(at(8), at(10)), "𑀅𑀆");
  assert.equal(text.slice(at(11)), "is Brahman.");
  assert.equal(at(999), text.length);
});

test("cuts are sorted, unique and clamped", () => {
  assert.deepEqual(
    cuts(10, [
      { start: 4, end: 20 },
      { start: 2, end: 4 },
    ]),
    [0, 2, 4, 10],
  );
});
