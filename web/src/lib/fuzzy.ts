// Accent-insensitive matching for the command palette: "sankara" finds "Śaṅkara".
const fold = (text: string) =>
  text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();

// Higher is better; -1 when the query does not match. Whole-word and earlier matches
// rank above letters scattered through the text.
export function score(query: string, text: string): number {
  const q = fold(query).trim();
  if (!q) return 0;
  const t = fold(text);
  const at = t.indexOf(q);
  if (at >= 0) return 1000 - at + (at === 0 || /\W/.test(t[at - 1]) ? 500 : 0);
  let from = 0;
  let gaps = 0;
  for (const ch of q.replace(/\s+/g, "")) {
    const next = t.indexOf(ch, from);
    if (next < 0) return -1;
    gaps += next - from;
    from = next + 1;
  }
  return Math.max(1, 400 - gaps * 10);
}

export function rank<T>(query: string, items: T[], text: (item: T) => string, limit = 8): T[] {
  return items
    .map((item) => [item, score(query, text(item))] as const)
    .filter(([, s]) => s >= 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([item]) => item);
}

// "BS 1.1.4", "Brahma Sutra 2, 1, 14": a sūtra, for the side-by-side view.
export function sutraRef(query: string): [number, number, number] | null {
  const m = fold(query).match(
    /^\s*(?:bs|brahma\s*-?\s*sutras?|vedanta\s*sutras?)\s*\.?\s*(\d+)\s*[.,:\s]\s*(\d+)\s*[.,:\s]\s*(\d+)\s*$/,
  );
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

const STOP = new Set(
  "the and for with that this from what does how why who are was not but its his her".split(" "),
);

// The text split into plain runs and runs matching a query word (3+ letters, any accents),
// for highlighting search snippets. Matches are found in the accent-folded text and
// mapped back, so "atman" marks "ātman".
export function marks(text: string, query: string): (string | { hit: string })[] {
  const terms = [...new Set(fold(query).split(/[^\p{L}\p{N}]+/u))].filter(
    (t) => t.length >= 3 && !STOP.has(t),
  );
  if (!terms.length) return [text];
  let folded = "";
  const origin: number[] = [];
  const chars = [...text];
  let at = 0;
  for (const ch of chars) {
    const f = fold(ch);
    folded += f;
    // One position per UTF-16 unit of the folded text (𑀅 is two).
    for (let k = 0; k < f.length; k++) origin.push(at);
    at += ch.length;
  }
  const hits: [number, number][] = [];
  for (const term of terms)
    for (let i = folded.indexOf(term); i >= 0; i = folded.indexOf(term, i + term.length)) {
      const start = origin[i];
      const lastChar = origin[i + term.length - 1];
      hits.push([start, lastChar + (text.codePointAt(lastChar)! > 0xffff ? 2 : 1)]);
    }
  if (!hits.length) return [text];
  hits.sort((a, b) => a[0] - b[0]);
  const out: (string | { hit: string })[] = [];
  let from = 0;
  for (const [start, end] of hits) {
    if (end <= from) continue;
    const s = Math.max(start, from);
    if (s > from) out.push(text.slice(from, s));
    out.push({ hit: text.slice(s, end) });
    from = end;
  }
  if (from < text.length) out.push(text.slice(from));
  return out;
}
