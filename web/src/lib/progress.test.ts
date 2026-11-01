// Run with: npm --prefix web test (Node's built-in runner; no extra dependency).
import assert from "node:assert/strict";
import test from "node:test";
import { latest, parseProgress, record, share, workKey } from "./progress.ts";

const key = workKey("katha-upanishad-sbe15", "SBE 15");

test("a part counts as read once its end is reached", () => {
  let p = record({}, key, "a", 0.4, 1);
  assert.deepEqual(p[key].done, []);
  p = record(p, key, "a", 0.95, 2);
  p = record(p, key, "b", 0.1, 3);
  assert.deepEqual(p[key], { chapter: "b", fraction: 0.1, at: 3, done: ["a"] });
  assert.equal(share(p[key], ["a", "b", "c", "d"]), 0.25);
  assert.equal(share(undefined, ["a"]), 0);
});

test("the latest work is the one read most recently", () => {
  const p = record(record({}, key, "a", 0.2, 5), workKey("x", "y"), "z", 0.2, 9);
  assert.equal(latest(p)?.[0], "x|y");
  assert.equal(latest({}), null);
});

test("stored progress is validated and clamped", () => {
  const parsed = parseProgress({
    good: { chapter: "a", fraction: 3, at: 1, done: ["a", 7] },
    bad: { chapter: 1 },
    worse: null,
  });
  assert.deepEqual(parsed, { good: { chapter: "a", fraction: 1, at: 1, done: ["a"] } });
  assert.deepEqual(parseProgress([1, 2]), {});
  assert.deepEqual(parseProgress("nope"), {});
});
