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
