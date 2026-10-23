import assert from "node:assert/strict";
import test from "node:test";
import { opening } from "./argument.ts";

test("skips a short cue sentence", () => {
  assert.equal(
    opening(
      "To this we make the following reply. The aggregate form is meant. More.",
    ),
    "The aggregate form is meant.",
  );
  assert.equal(
    opening("THE GREAT PÛRVAPAKSHA.\n\nAll difference is unreal."),
    "All difference is unreal.",
  );
});

test("keeps substantive first sentences and trims long ones at a word", () => {
  assert.equal(
    opening("The pûrvapakshin maintains that the Self is the body. Then more."),
    "The pûrvapakshin maintains that the Self is the body.",
  );
  const long = opening("word ".repeat(60).trim() + ".", 40);
  assert.ok(long.endsWith("…") && long.length <= 41);
});

test("strips a run-together reply formula and leading dashes", () => {
  assert.equal(
    opening(
      "To this we make the following reply:--In the passage the Self is meant. Next.",
    ),
    "In the passage the Self is meant.",
  );
  assert.equal(
    opening("--Bhûman can mean the highest Self only."),
    "Bhûman can mean the highest Self only.",
  );
});
