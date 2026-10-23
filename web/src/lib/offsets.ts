// The API reports offsets as Python code points; JavaScript strings index UTF-16
// code units. Convert once per text so characters outside the BMP (e.g. Brahmi 𑀅)
// never shift highlights.
export function codePointIndex(text: string): (codePoint: number) => number {
  if (!/[\uD800-\uDFFF]/.test(text)) return (cp) => cp;
  const units: number[] = [0];
  let unit = 0;
  for (const char of text) {
    unit += char.length;
    units.push(unit);
  }
  return (cp) => units[Math.max(0, Math.min(cp, units.length - 1))];
}

export type Span = { start: number; end: number };

// Cut [0, length) at every span edge so each piece has one fixed set of spans.
export function cuts(length: number, spans: Span[]): number[] {
  const points = new Set([0, length]);
  for (const s of spans) {
    points.add(Math.max(0, Math.min(length, s.start)));
    points.add(Math.max(0, Math.min(length, s.end)));
  }
  return [...points].sort((a, b) => a - b);
}

// UTF-16 index -> Python code-point offset (the inverse of codePointIndex).
export function codePointOf(text: string, unit: number): number {
  let points = 0;
  for (let i = 0; i < unit && i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code < 0xdc00 || code > 0xdfff) points++; // a low surrogate ends a counted pair
  }
  return points;
}

// Where selected text occurs in text[from, to) (UTF-16), ignoring whitespace differences
// (the page renders line breaks as spaces); null unless it occurs exactly once.
export function locate(text: string, selected: string, from: number, to: number): Span | null {
  const words = selected.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return null;
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(escaped.join("\\s+"), "g");
  const region = text.slice(from, to);
  const found = [...region.matchAll(pattern)];
  if (found.length !== 1) return null;
  const start = from + found[0].index!;
  return { start, end: start + found[0][0].length };
}
