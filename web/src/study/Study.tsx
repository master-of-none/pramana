import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Columns2,
  Route as PathIcon,
  Search as SearchIcon,
} from "lucide-react";
import { getJSON, placeLabel } from "../lib/api.ts";
import type {
  ChapterContext,
  LibraryDocument,
  ParallelEntry,
  SearchHit,
} from "../lib/api.ts";
import { useGlossary } from "../lib/glossary.tsx";
import type { Glossary } from "../lib/glossary.tsx";
import { href } from "../lib/router.ts";
import type { Route } from "../lib/router.ts";
import { restore } from "../lib/storage.ts";
import { ChapterText } from "./ChapterText.tsx";
import { Concept, ConceptList } from "./Concept.tsx";
import { Argument } from "./Argument.tsx";
import { Paths } from "./Paths.tsx";

// Shared per page load; the catalogue changes only when the library is re-imported.
let catalogue: Promise<LibraryDocument[]> | null = null;
function useLibrary() {
  const [docs, setDocs] = useState<LibraryDocument[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    catalogue ??= getJSON<LibraryDocument[]>("/api/library");
    catalogue.then(setDocs).catch((e: Error) => {
      catalogue = null;
      setError(e.message);
    });
  }, []);
  return { docs, error };
}

function useChapter(id: string | undefined) {
  const [context, setContext] = useState<ChapterContext | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!id) return;
    setContext(null);
    setError("");
    getJSON<ChapterContext>(`/api/chapters/${encodeURIComponent(id)}`)
      .then(setContext)
      .catch((e: Error) => setError(e.message));
  }, [id]);
  return { context, error };
}

function Status({ error, children }: { error?: string; children?: ReactNode }) {
  if (error)
    return (
      <p className="study-status" role="alert">
        {error}
      </p>
    );
  return (
    <p className="study-status" role="status">
      {children ?? "Opening the texts…"}
    </p>
  );
}

function SourceNote({ context }: { context: ChapterContext }) {
  const { chapter } = context;
  return (
    <footer className="source-note">
      <p>
        <strong>{chapter.document}</strong>
        {chapter.author && <> · {chapter.author}</>} · tr. {chapter.translator}
      </p>
      <p>{chapter.edition}</p>
      <p>{chapter.source.rights}</p>
      <p>{chapter.source.attribution}</p>
      {chapter.source.url ? (
        <p>
          <a href={chapter.source.url} target="_blank" rel="noreferrer">
            Original page
          </a>
        </p>
      ) : (
        <p>Private local edition; not distributed.</p>
      )}
    </footer>
  );
}

function Library({ glossary: _ }: { glossary: Glossary | null }) {
  const { docs, error } = useLibrary();
  if (!docs) return <Status error={error} />;
  if (!docs.length)
    return (
      <Status>
        The library is empty. Run{" "}
        <code>pramana corpus download --source advaita</code>, then import and
        index it.
      </Status>
    );
  const groups = [...new Set(docs.map((d) => d.category))];
  const sutra = docs.some((d) => d.category === "Brahma Sūtra");
  return (
    <div className="library">
      <header className="study-intro">
        <h1>The library</h1>
        <p>
          Read the texts behind the answers. Every edition keeps its translator,
          rights and attribution.
        </p>
        <div className="study-actions">
          <a href={href("study", "paths")}>
            <PathIcon size={15} /> Reading paths
          </a>
          <a href={href("study", "search")}>
            <SearchIcon size={15} /> Search the library
          </a>
          {sutra && (
            <a href={href("study", "sutra", 1, 1, 1)}>
              <Columns2 size={15} /> Śaṅkara and Rāmānuja side by side
            </a>
          )}
        </div>
      </header>
      <ConceptList />
      {groups.map((group) => (
        <section key={group} className="library-group">
          <h2>{group}</h2>
          <div className="library-docs">
            {docs
              .filter((d) => d.category === group)
              .map((d) => (
                <details
                  key={d.document_id + d.edition}
                  className="library-doc"
                >
                  <summary>
                    <span className="doc-title">{d.document}</span>
                    <span className="doc-meta">
                      {[d.author, `tr. ${d.translator}`]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    <span className="doc-count">
                      {d.chapters.length === 1
                        ? "1 part"
                        : `${d.chapters.length} parts`}
                    </span>
                  </summary>
                  <p className="doc-edition">{d.edition}</p>
                  <ol className="doc-parts">
                    {d.chapters.map((c) => (
                      <li key={c.id}>
                        <a href={href("study", "read", c.id)}>
                          {placeLabel(d.category, c.location)}
                        </a>
                      </li>
                    ))}
                  </ol>
                </details>
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Reader({
  id,
  route,
  glossary,
}: {
  id: string;
  route: Route;
  glossary: Glossary | null;
}) {
  const { context, error } = useChapter(id);
  const { docs } = useLibrary();
  if (!context) return <Status error={error} />;
  const { chapter } = context;
  const doc = docs?.find(
    (d) =>
      d.document_id === chapter.document_id && d.edition === chapter.edition,
  );
  const category = doc?.category ?? "";
  const start = Number(route.query.get("s"));
  const end = Number(route.query.get("e"));
  const highlight =
    route.query.has("s") &&
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    start <= end
      ? { start, end }
      : undefined;
  const sutra = chapter.location.sections[0];
  return (
    <article className="reader">
      <nav className="reader-nav" aria-label="Chapter navigation">
        <a href={href("study")}>
          <ArrowLeft size={14} /> Library
        </a>
        <span>
          {context.previous && (
            <a
              href={href("study", "read", context.previous)}
              aria-label="Previous part"
            >
              <ArrowLeft size={14} /> Previous
            </a>
          )}
          {context.next && (
            <a
              href={href("study", "read", context.next)}
              aria-label="Next part"
            >
              Next <ArrowRight size={14} />
            </a>
          )}
        </span>
      </nav>
      <header className="reader-head">
        <p className="eyebrow">{category || chapter.content_type}</p>
        <h1>{chapter.document}</h1>
        <p className="reader-place">{placeLabel(category, chapter.location)}</p>
        {category === "Brahma Sūtra" && /^\d+$/.test(sutra ?? "") && (
          <a
            className="reader-parallel"
            href={href(
              "study",
              "sutra",
              chapter.location.book,
              chapter.location.chapter,
              sutra!,
            )}
          >
            <Columns2 size={14} /> Compare commentaries on this sūtra
          </a>
        )}
      </header>
      {context.roles.length > 0 && (
        <p className="role-legend">
          <span className="role-objection">Objection</span>
          <span className="role-reply">Reply</span> marked only where the book
          itself labels them.
        </p>
      )}
      <ChapterText
        context={context}
        glossary={glossary}
        highlight={highlight}
      />
      <SourceNote context={context} />
    </article>
  );
}

function Parallel({
  place,
  glossary,
}: {
  place: string[];
  glossary: Glossary | null;
}) {
  const [book, pada, sutra] = place;
  const [entries, setEntries] = useState<ParallelEntry[] | null>(null);
  const [contexts, setContexts] = useState<Record<string, ChapterContext>>({});
  const [error, setError] = useState("");
  useEffect(() => {
    setEntries(null);
    setError("");
    const query = new URLSearchParams({ book, chapter: pada, sutra });
    getJSON<ParallelEntry[]>(`/api/parallel?${query}`)
      .then(async (found) => {
        const ids = found.flatMap((e) => e.chapters);
        const loaded = await Promise.all(
          ids.map((id) =>
            getJSON<ChapterContext>(`/api/chapters/${encodeURIComponent(id)}`),
          ),
        );
        setContexts(Object.fromEntries(loaded.map((c) => [c.id, c])));
        setEntries(found);
      })
      .catch((e: Error) => setError(e.message));
  }, [book, pada, sutra]);
  const n = Number(sutra);
  function go(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    window.location.hash = href(
      "study",
      "sutra",
      ...["a", "p", "s"].map((k) => String(form.get(k))),
    );
  }
  return (
    <div className="parallel">
      <header className="study-intro">
        <h1>
          Brahma Sūtra {book}.{pada}.{sutra}
        </h1>
        <p>
          Two commentaries on the same sūtra, each in its own translator's
          words.
        </p>
        <form className="sutra-form" onSubmit={go} aria-label="Go to sūtra">
          {[
            ["a", "Adhyāya", book, 4],
            ["p", "Pāda", pada, 4],
            ["s", "Sūtra", sutra, 80],
          ].map(([name, label, value, max]) => (
            <label key={name}>
              {label}
              <input
                name={String(name)}
                type="number"
                min={1}
                max={Number(max)}
                defaultValue={String(value)}
                key={String(value)}
              />
            </label>
          ))}
          <button type="submit">Go</button>
          {n > 1 && (
            <a href={href("study", "sutra", book, pada, n - 1)}>← {n - 1}</a>
          )}
          <a href={href("study", "sutra", book, pada, n + 1)}>{n + 1} →</a>
        </form>
      </header>
      {!entries ? (
        <Status error={error} />
      ) : !entries.length ? (
        <Status>
          No commentary page starts at or before this sūtra in this pāda. Check
          the numbers, or download <code>--source brahma-sutra</code> and{" "}
          <code>--source sribhashya</code>.
        </Status>
      ) : (
        <div className="parallel-columns">
          {entries.map((entry) => (
            <section key={entry.document_id} className="parallel-column">
              <h2>{entry.author || entry.document}</h2>
              <p className="doc-edition">{entry.edition}</p>
              {!entry.exact && (
                <p className="parallel-note">
                  This commentary treats sūtra {sutra} on a page that begins
                  with an earlier sūtra.
                </p>
              )}
              {entry.chapters.map((id) =>
                contexts[id] ? (
                  <div key={id} className="parallel-page">
                    {contexts[id].chapter.location.sections.length > 1 && (
                      <h3>
                        {contexts[id].chapter.location.sections
                          .slice(1)
                          .join(" · ")}
                      </h3>
                    )}
                    <Argument context={contexts[id]} />
                    <ChapterText context={contexts[id]} glossary={glossary} />
                    <a className="open-reader" href={href("study", "read", id)}>
                      Open in reader
                    </a>
                  </div>
                ) : null,
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function Evidence({
  turnId,
  glossary: _,
}: {
  turnId: string;
  glossary: Glossary | null;
}) {
  const turn = restore().find((t) => t.id === turnId);
  const refs = turn?.evidence ?? [];
  const [contexts, setContexts] = useState<Record<string, ChapterContext>>({});
  const [error, setError] = useState("");
  const { docs } = useLibrary();
  useEffect(() => {
    const ids = [...new Set(refs.map((r) => r.chapter))];
    Promise.all(
      ids.map((id) =>
        getJSON<ChapterContext>(`/api/chapters/${encodeURIComponent(id)}`),
      ),
    )
      .then((loaded) =>
        setContexts(Object.fromEntries(loaded.map((c) => [c.id, c]))),
      )
      .catch((e: Error) => setError(e.message));
  }, [turnId]);
  if (!turn)
    return (
      <Status>
        This answer is no longer in this tab's conversation. Evidence is kept
        only for the current chat.
      </Status>
    );
  return (
    <div className="evidence">
      <header className="study-intro">
        <a href="#/" className="back-link">
          <ArrowLeft size={14} /> Back to the conversation
        </a>
        <h1>Passages behind this answer</h1>
        <p className="evidence-question">“{turn.question}”</p>
        <p>
          These are the passages the answer cites. They show what was read, not
          that every sentence of the answer is correct.
        </p>
      </header>
      {error && <Status error={error} />}
      {refs.map((r) => {
        const context = contexts[r.chapter];
        if (!context) return null;
        const { chapter } = context;
        const category =
          docs?.find(
            (d) =>
              d.document_id === chapter.document_id &&
              d.edition === chapter.edition,
          )?.category ?? "";
        const chars = [...chapter.text];
        return (
          <section key={r.passage} className="evidence-item">
            <h2>{chapter.document}</h2>
            <p className="doc-meta">
              {[
                chapter.author,
                `tr. ${chapter.translator}`,
                placeLabel(category, chapter.location),
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <blockquote>{chars.slice(r.start, r.end).join("")}</blockquote>
            <a
              className="open-reader"
              href={`${href("study", "read", r.chapter)}?s=${r.start}&e=${r.end}`}
            >
              Read it in context
            </a>
          </section>
        );
      })}
    </div>
  );
}

function Search({ route }: { route: Route }) {
  const query = route.query.get("q") ?? "";
  const strategy = route.query.get("m") === "lexical" ? "lexical" : "hybrid";
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [error, setError] = useState("");
  const { docs } = useLibrary();
  useEffect(() => {
    if (!query.trim()) return;
    setHits(null);
    setError("");
    getJSON<SearchHit[]>("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 20, strategy }),
    })
      .then(setHits)
      .catch((e: Error) => setError(e.message));
  }, [query, strategy]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const params = new URLSearchParams({
      q: String(form.get("q") ?? ""),
      m: String(form.get("m")),
    });
    window.location.hash = `${href("study", "search")}?${params}`;
  }
  return (
    <div className="search">
      <header className="study-intro">
        <h1>Search the library</h1>
        <form className="search-form" onSubmit={submit} role="search">
          <label className="sr-only" htmlFor="study-q">
            Search terms
          </label>
          <input
            id="study-q"
            name="q"
            defaultValue={query}
            key={query}
            placeholder="adhyāsa, the witness, tat tvam asi…"
          />
          <select name="m" defaultValue={strategy} aria-label="Search method">
            <option value="hybrid">Meaning and words</option>
            <option value="lexical">Exact words</option>
          </select>
          <button type="submit">
            <SearchIcon size={15} /> Search
          </button>
        </form>
      </header>
      {query.trim() &&
        (!hits ? (
          <Status error={error}>Searching…</Status>
        ) : !hits.length ? (
          <Status>No passages matched.</Status>
        ) : (
          <ol className="search-results">
            {hits.map((h) => {
              const c = h.passage.citation;
              const category =
                docs?.find(
                  (d) => d.document === c.document && d.edition === c.edition,
                )?.category ?? "";
              return (
                <li key={h.passage.id}>
                  <a
                    href={`${href("study", "read", h.passage.chapter_id)}?s=${h.passage.start}&e=${h.passage.end}`}
                  >
                    <span className="doc-title">{c.document}</span>
                    <span className="doc-meta">
                      {[c.author, placeLabel(category, c.location)]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    <span className="snippet">{h.snippet}…</span>
                  </a>
                </li>
              );
            })}
          </ol>
        ))}
    </div>
  );
}

export function Study({ route }: { route: Route }) {
  const glossary = useGlossary();
  const [, page, ...rest] = route.path;
  let content: ReactNode;
  if (page === "read" && rest[0])
    content = <Reader id={rest[0]} route={route} glossary={glossary} />;
  else if (
    page === "sutra" &&
    rest.length === 3 &&
    rest.every((x) => /^\d+$/.test(x))
  )
    content = <Parallel place={rest} glossary={glossary} />;
  else if (page === "evidence" && rest[0])
    content = <Evidence turnId={rest[0]} glossary={glossary} />;
  else if (page === "search") content = <Search route={route} />;
  else if (page === "concept" && rest[0]) content = <Concept slug={rest[0]} />;
  else if (page === "paths") content = <Paths />;
  else content = <Library glossary={glossary} />;
  return (
    <div className="view study">
      <main id="study-main" className="study-main">
        {content}
      </main>
    </div>
  );
}
