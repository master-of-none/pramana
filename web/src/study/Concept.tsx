import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { getJSON, placeLabel } from "../lib/api.ts";
import type { Location } from "../lib/api.ts";
import { fold } from "../lib/glossary.tsx";
import { href } from "../lib/router.ts";

type ConceptPassage = {
  id: string;
  chapter_id: string;
  text: string;
  start: number;
  end: number;
  citation: {
    document: string;
    author: string;
    translator: string;
    location: Location;
  };
};
type ConceptPage = {
  slug: string;
  term: string;
  devanagari: string;
  aliases: string[];
  english: string[];
  meaning: string;
  indexed: boolean;
  groups: { group: string; label: string; passages: ConceptPassage[] }[];
  related: { slug: string; term: string; passages: number }[];
};
export type ConceptSummary = {
  slug: string;
  term: string;
  devanagari: string;
  meaning: string;
};

// A window of the passage around the first mention of any of the concept's names.
function excerpt(text: string, names: string[], width = 420): string {
  const chars = [...text];
  const folded = chars.map((c) => fold(c) || c);
  const flat = folded.join("");
  const starts: number[] = [];
  let at = 0;
  for (const f of folded) {
    starts.push(at);
    at += f.length;
  }
  const hit = Math.min(
    ...names.map((n) => flat.indexOf(fold(n))).filter((i) => i >= 0),
    Number.MAX_SAFE_INTEGER,
  );
  const index =
    hit === Number.MAX_SAFE_INTEGER ? 0 : starts.findIndex((s) => s >= hit);
  const from = Math.max(0, index - width / 3);
  const to = Math.min(chars.length, from + width);
  return (
    (from ? "…" : "") +
    chars.slice(from, to).join("").trim() +
    (to < chars.length ? "…" : "")
  );
}

export function Concept({ slug }: { slug: string }) {
  const [page, setPage] = useState<ConceptPage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setPage(null);
    setError("");
    getJSON<ConceptPage>(`/api/concepts/${encodeURIComponent(slug)}`)
      .then(setPage)
      .catch((e: Error) => setError(e.message));
  }, [slug]);
  if (!page)
    return (
      <p className="study-status" role={error ? "alert" : "status"}>
        {error || "Gathering passages…"}
      </p>
    );
  const names = [page.term, ...page.aliases, ...page.english];
  return (
    <div className="concept">
      <header className="study-intro">
        <a href={href("study")} className="back-link">
          <ArrowLeft size={14} /> Library
        </a>
        <h1>
          {page.term}
          {page.devanagari && (
            <span className="concept-devanagari" lang="sa">
              {page.devanagari}
            </span>
          )}
        </h1>
        <p className="concept-meaning">{page.meaning}</p>
        <p>
          A short editorial definition, followed by the passages that mention it
          most strongly in each group of texts. Matched as: {names.join(", ")}.
          Ranking shows where a concept is discussed, not what each author
          concludes about it.
        </p>
      </header>
      {!page.indexed && (
        <p className="study-status">
          Index the library to see passages: run pramana index.
        </p>
      )}
      {page.indexed && !page.groups.length && (
        <p className="study-status">
          No passage in the imported texts mentions this concept.
        </p>
      )}
      {page.groups.map((g) => (
        <section key={g.group} className="concept-group">
          <h2>{g.label}</h2>
          {g.passages.map((p) => (
            <article key={p.id} className="evidence-item">
              <p className="doc-meta">
                <strong>{p.citation.document}</strong>
                {" · "}
                {[
                  p.citation.author,
                  `tr. ${p.citation.translator}`,
                  placeLabel(
                    g.group === "shankara" || g.group === "ramanuja"
                      ? "Brahma Sūtra"
                      : "",
                    p.citation.location,
                  ),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <blockquote>{excerpt(p.text, names)}</blockquote>
              <a
                className="open-reader"
                href={`${href("study", "read", p.chapter_id)}?s=${p.start}&e=${p.end}`}
              >
                Read it in context
              </a>
            </article>
          ))}
        </section>
      ))}
      {page.related.length > 0 && (
        <section className="concept-related">
          <h2>Discussed alongside</h2>
          <div className="chip-row wrap">
            {page.related.map((r) => (
              <a
                key={r.slug}
                className="chip"
                href={href("study", "concept", r.slug)}
              >
                {r.term}
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export function ConceptList() {
  const [items, setItems] = useState<ConceptSummary[]>([]);
  useEffect(() => {
    getJSON<ConceptSummary[]>("/api/concepts")
      .then(setItems)
      .catch(() => undefined);
  }, []);
  if (!items.length) return null;
  return (
    <section className="library-group">
      <h2>Concepts</h2>
      <div className="chip-row wrap">
        {items.map((c) => (
          <a
            key={c.slug}
            className="chip"
            href={href("study", "concept", c.slug)}
            title={c.meaning}
          >
            {c.term}
          </a>
        ))}
      </div>
    </section>
  );
}
