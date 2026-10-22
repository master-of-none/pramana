import { useEffect, useState } from "react";
import type { ReactNode } from "react";

export type GlossaryTerm = {
  term: string;
  devanagari: string;
  aliases: string[];
  meaning: string;
};
export type Glossary = { pattern: RegExp; lookup: Map<string, GlossaryTerm> };

export const fold = (text: string) =>
  text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();

function build(terms: GlossaryTerm[]): Glossary | null {
  const lookup = new Map<string, GlossaryTerm>();
  for (const t of terms)
    for (const name of [t.term, ...t.aliases]) lookup.set(fold(name), t);
  if (!lookup.size) return null;
  const names = terms
    .flatMap((t) => [t.term, ...t.aliases])
    .sort((a, b) => b.length - a.length)
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return {
    pattern: new RegExp(
      `(?<![\\p{L}\\p{M}])(${names.join("|")})(?![\\p{L}\\p{M}])`,
      "giu",
    ),
    lookup,
  };
}

// Optional enhancement: text renders normally if the glossary is unavailable.
export function useGlossary(): Glossary | null {
  const [glossary, setGlossary] = useState<Glossary | null>(null);
  useEffect(() => {
    fetch("/api/glossary")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => Array.isArray(data) && setGlossary(build(data)))
      .catch(() => undefined);
  }, []);
  return glossary;
}

// Marks the first mention of each concept; a general glossary, not a source.
export function annotate(
  raw: string,
  glossary: Glossary | null,
  seen: Set<string>,
): ReactNode[] {
  const text = raw.normalize("NFC");
  if (!glossary) return [text];
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(glossary.pattern)) {
    const entry = glossary.lookup.get(fold(match[0]));
    if (!entry || seen.has(entry.term)) continue;
    seen.add(entry.term);
    out.push(text.slice(last, match.index));
    out.push(
      <span className="term" key={`${entry.term}-${match.index}`}>
        <button type="button" className="term-word">
          {match[0]}
        </button>
        <span className="term-card" role="tooltip">
          <span className="term-name">
            {entry.term}
            {entry.devanagari && <span lang="sa"> · {entry.devanagari}</span>}
          </span>
          {entry.meaning}
        </span>
      </span>,
    );
    last = match.index! + match[0].length;
  }
  out.push(text.slice(last));
  return out;
}
