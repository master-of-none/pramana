import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { CITATION_STATUS, getJSON, thinkerName } from "../lib/api.ts";
import type { CitationStatus, CitationSummary } from "../lib/api.ts";
import { href, readAt } from "../lib/router.ts";

// The scripture passages the commentaries cite most, counted per thinker.
export function Citations() {
  const [data, setData] = useState<CitationSummary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getJSON<CitationSummary>("/api/citations")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);
  if (!data)
    return (
      <p className="study-status" role={error ? "alert" : "status"}>
        {error || "Counting citations…"}
      </p>
    );
  const thinkers = [
    ...new Set(data.passages.flatMap((p) => Object.keys(p.by).map(thinkerName))),
  ];
  const most = Math.max(1, ...data.passages.map((p) => p.total));
  const statuses: CitationStatus[] = ["verified", "numbered", "chapter"];
  return (
    <article className="citations">
      <nav className="reader-nav">
        <a href={href("study")}>
          <ArrowLeft size={14} /> Library
        </a>
      </nav>
      <header className="study-intro">
        <h1>Śruti most cited</h1>
        <p>
          The commentaries quote the Upaniṣads and the Gītā with printed references
          such as “(Kh. Up. VI, 8, 7)”. {data.references.toLocaleString()} of them
          point to passages in this library.
        </p>
        <p className="citation-status">
          {statuses.map((s) => (
            <span key={s} className={`cite-status ${s}`} title={CITATION_STATUS[s]}>
              {(data.status[s] ?? 0).toLocaleString()}{" "}
              {s === "verified"
                ? "quotation found in the passage"
                : s === "numbered"
                  ? "by verse number"
                  : "chapter only"}
            </span>
          ))}
        </p>
      </header>
      <ol className="cited-list">
        {data.passages.map((p) => (
          <li key={`${p.chapter_id}-${p.start}`}>
            <a href={readAt(p.chapter_id, p.start, p.end)} className="cited-place">
              {p.document} {p.place}
              {p.verse !== null && <>, {p.verse}</>}
            </a>
            <p className="cited-opening">
              {p.opening.length > 150 ? `${p.opening.slice(0, 150)}…` : p.opening}
            </p>
            <div className="cited-bars" aria-label={`Cited ${p.total} times`}>
              {thinkers.map((name) => {
                const n = Object.entries(p.by)
                  .filter(([a]) => thinkerName(a) === name)
                  .reduce((s, [, v]) => s + v, 0);
                return n ? (
                  <span key={name} className="cited-bar">
                    <span className="cited-name">{name}</span>
                    <span
                      className={`cited-fill t${thinkers.indexOf(name) % 3}`}
                      style={{ width: `${(n / most) * 100}%` }}
                    />
                    <span className="cited-count">{n}</span>
                  </span>
                ) : null;
              })}
            </div>
          </li>
        ))}
      </ol>
    </article>
  );
}
