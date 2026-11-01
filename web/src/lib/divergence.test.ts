// Run with: npm --prefix web test (Node's built-in runner; no extra dependency).
import assert from "node:assert/strict";
import test from "node:test";
import type { DivergenceUnit } from "./api.ts";
import { reasons } from "./divergence.ts";

const unit = (over: Partial<DivergenceUnit>): DivergenceUnit => ({
  book: "1",
  pada: "1",
  first: 1,
  last: null,
  label: "1.1.1",
  exact: true,
  shankara: [],
  ramanuja: [],
  bands: { overall: "very high", scripture: "very high", wording: "high", dispute: "very high" },
  shared: 0,
  only_shankara: [{ label: "Kh. Up. VI, 8, 7", chapter_id: "c", start: 0, end: 1 }],
  only_ramanuja: [],
  terms: { nescience: 12, māyā: 2 },
  ...over,
});

test("a unit's strongest signals become plain reasons", () => {
  assert.deepEqual(reasons(unit({})), [
    "different scripture cited",
    "little shared wording",
    "Rāmānuja's text names nescience (12×)",
  ]);
  assert.deepEqual(reasons(unit({ shared: 2 }))[0], "mostly different scripture cited");
});

test("close units say so; middling ones give no reason", () => {
  const close = unit({
    bands: { overall: "low", scripture: "low", wording: "low", dispute: "low" },
    terms: {},
  });
  assert.deepEqual(reasons(close), ["the same scripture, similar wording"]);
  const mid = unit({
    bands: { overall: "high", scripture: "marked", wording: "marked", dispute: null },
  });
  assert.deepEqual(reasons(mid), []);
});
