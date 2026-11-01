import type { Band, DivergenceUnit, Signal } from "./api.ts";

export const BANDS: Band[] = ["low", "moderate", "marked", "high", "very high"];
export const SIGNALS: [Signal, string][] = [
  ["overall", "Overall"],
  ["scripture", "Scripture cited"],
  ["wording", "Wording"],
  ["dispute", "Dispute terms"],
];
const strong = (b: Band | null) => b === "high" || b === "very high";

// Why a unit stands out, in plain words, from its strongest signals. Factual phrasing:
// a term in Rāmānuja's text is reported as named, not as proof of a refutation.
export function reasons(unit: DivergenceUnit): string[] {
  const out: string[] = [];
  const { bands } = unit;
  if (strong(bands.scripture) && (unit.only_shankara.length || unit.only_ramanuja.length))
    out.push(unit.shared ? "mostly different scripture cited" : "different scripture cited");
  if (strong(bands.wording)) out.push("little shared wording");
  const [term, count] = Object.entries(unit.terms)[0] ?? [];
  if (strong(bands.dispute) && term) out.push(`Rāmānuja's text names ${term} (${count}×)`);
  if (!out.length && bands.overall && !strong(bands.overall))
    out.push(bands.scripture === "low" ? "the same scripture, similar wording" : "close in wording");
  return out;
}
