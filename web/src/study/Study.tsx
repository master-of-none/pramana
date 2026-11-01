import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  ArrowLeft,
  BookMarked,
  BookOpen,
  Columns2,
  Waypoints,
  StickyNote,
  Route as PathIcon,
  Search as SearchIcon,
} from "lucide-react";
import { getJSON, placeLabel } from "../lib/api.ts";
import type {
  ChapterContext,
  Location,
  ParallelEntry,
  SearchHit,
} from "../lib/api.ts";
import { useGlossary } from "../lib/glossary.tsx";
import type { Glossary } from "../lib/glossary.tsx";
import { href, usePageArrival } from "../lib/router.ts";
import { isShortcut } from "../lib/keys.ts";
import { marks } from "../lib/fuzzy.ts";
import type { Route } from "../lib/router.ts";
import { restore } from "../lib/storage.ts";
import { latest, share, useProgress, workKey } from "../lib/progress.ts";
import { Notes } from "./Notes.tsx";
import { ChapterText } from "./ChapterText.tsx";
import { Concept, ConceptList } from "./Concept.tsx";
import { Argument } from "./Argument.tsx";
import { Paths } from "./Paths.tsx";
import { Citations } from "./Citations.tsx";
import { loadChapters, unitFor, useDivergence, useLibrary } from "./data.ts";
import { DivergenceMap } from "./DivergenceMap.tsx";
import { reasons } from "../lib/divergence.ts";
import { Reader } from "./Reader.tsx";
import { Trail } from "./Trail.tsx";
import { Status } from "./Status.tsx";

function Library({ glossary: _ }: { glossary: Glossary | null }) {
  const { docs, error } = useLibrary();
  const { progress } = useProgress();
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
  // The work read most recently in this browser, if it is still in the library.
  const last = latest(progress);
  const lastDoc = last && docs.find((d) => workKey(d.document_id, d.edition) === last[0]);
  const lastPart = lastDoc && lastDoc.chapters.find((c) => c.id === last[1].chapter);
  return (
    <div className="library">
      <header className="study-intro">
        <h1>The library</h1>
        <p>
          Read the texts behind the answers. Every edition keeps its translator,
          rights and attribution.
        </p>
      </header>
      {last && lastDoc && lastPart && (
        <a
          className="continue-reading"
          href={`${href("study", "read", lastPart.id)}?p=${last[1].fraction.toFixed(3)}`}
        >
          <span className="eyebrow">Continue reading</span>
          <span className="doc-title">{lastDoc.document}</span>
          <span className="doc-meta">
            {placeLabel(lastDoc.category, lastPart.location)} ·{" "}
            {last[1].fraction < 0.02
              ? "opened"
              : `${Math.round(last[1].fraction * 100)}% through this part`}
          </span>
          <span className="continue-bar" aria-hidden="true">
            <span style={{ transform: `scaleX(${share(progress[last[0]], lastDoc.chapters.map((c) => c.id))})` }} />
          </span>
        </a>
      )}
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
                      {(() => {
                        const read = share(
                          progress[workKey(d.document_id, d.edition)],
                          d.chapters.map((c) => c.id),
                        );
                        return read > 0 ? ` · ${Math.max(1, Math.round(read * 100))}% read` : "";
                      })()}
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

function Parallel({
  place,
  glossary,
}: {
  place: string[];
  glossary: Glossary | null;
}) {
  const [book, pada, sutra] = place;
  const [entries, setEntries] = useState<ParallelEntry[] | null>(null);
  const [contexts, setContexts] = useState<Record<string, ChapterContext | Error>>({});
  const [error, setError] = useState("");
  const { docs } = useLibrary();
  useEffect(() => {
    setEntries(null);
    setError("");
    const query = new URLSearchParams({ book, chapter: pada, sutra });
    getJSON<ParallelEntry[]>(`/api/parallel?${query}`)
      .then(async (found) => {
        setContexts(await loadChapters(found.flatMap((e) => e.chapters)));
        setEntries(found);
      })
      .catch((e: Error) => setError(e.message));
  }, [book, pada, sutra]);
  const n = Number(sutra);
  // How differently the two treat this stretch, from the divergence map.
  const { data: map } = useDivergence();
  const unit = unitFor(map, book, pada, n);
  // The highest printed numbers in the commentaries held, for the form's limits.
  const sutraPages = (docs ?? [])
    .filter((d) => d.category === "Brahma Sūtra")
    .flatMap((d) => d.chapters.map((c) => c.location));
  const highest = (pick: (l: Location) => string | undefined, within = sutraPages) =>
    Math.max(1, ...within.map((l) => Number(pick(l))).filter(Number.isInteger));
  const maxAdhyaya = highest((l) => l.book);
  const maxPada = highest((l) => l.chapter);
  const maxSutra = highest(
    (l) => l.sections[0],
    sutraPages.filter((l) => l.book === book && l.chapter === pada),
  );
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
        {unit?.bands.overall && (
          <p className="dv-badge">
            <span className="dv-swatch" data-band={unit.bands.overall} aria-hidden="true" />
            Where they part ways ({unit.label}): <strong>{unit.bands.overall}</strong>
            {reasons(unit).length > 0 && <> · {reasons(unit).join("; ")}</>}{" "}
            <a href={`${href("study", "map")}?u=${encodeURIComponent(unit.label)}`}>See the map</a>
            {unit.pairing === "renumbered" && unit.ramanuja[0] && (
              <>
                {" "}
                · Rāmānuja numbers this sūtra {unit.ramanuja_sutra}:{" "}
                <a href={href("study", "read", unit.ramanuja[0])}>his page</a>
              </>
            )}
            {unit.pairing === "unconfirmed" && " · paired by number only"}
          </p>
        )}
        <form className="sutra-form" onSubmit={go} aria-label="Go to sūtra">
          {[
            ["a", "Adhyāya", book, maxAdhyaya],
            ["p", "Pāda", pada, maxPada],
            ["s", "Sūtra", sutra, Math.max(maxSutra, n)],
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
          {n < maxSutra && (
            <a href={href("study", "sutra", book, pada, n + 1)}>{n + 1} →</a>
          )}
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
              {entry.chapters.map((id) => {
                const context = contexts[id];
                if (!context) return null;
                if (context instanceof Error)
                  return (
                    <p key={id} className="study-status" role="alert">
                      This page could not be opened ({context.message}).{" "}
                      <a href={href("study", "read", id)}>Try it in the reader</a>.
                    </p>
                  );
                return (
                  <div key={id} className="parallel-page">
                    {context.chapter.location.sections.length > 1 && (
                      <h3>{context.chapter.location.sections.slice(1).join(" · ")}</h3>
                    )}
                    <Argument context={context} />
                    <ChapterText context={context} glossary={glossary} />
                    <a className="open-reader" href={href("study", "read", id)}>
                      Open in reader
                    </a>
                  </div>
                );
              })}
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
  const [contexts, setContexts] = useState<Record<string, ChapterContext | Error>>({});
  const { docs } = useLibrary();
  useEffect(() => {
    void loadChapters(refs.map((r) => r.chapter)).then(setContexts);
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
          These are the passages the answer cites, and any the check named as support.
          They show what was read, not that every sentence of the answer is correct.
        </p>
      </header>
      <Trail turn={turn} contexts={contexts} docs={docs} />
      <h2 className="evidence-all">All passages behind it</h2>
      {refs.map((r) => {
        const context = contexts[r.chapter];
        if (!context) return null;
        if (context instanceof Error)
          return (
            <p key={r.passage} className="study-status" role="alert">
              One passage could not be opened ({context.message}).
            </p>
          );
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
            <h3>{chapter.document}</h3>
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
  // One text only (`d`), and how many results (`n`: 20, or 50 after "Show more").
  const only = route.query.get("d") ?? "";
  const limit = route.query.get("n") === "50" ? 50 : 20;
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [error, setError] = useState("");
  const { docs } = useLibrary();
  const input = useRef<HTMLInputElement>(null);
  // Opened to type in ("/" or the palette): the box takes focus when there is no query.
  useEffect(() => {
    if (!query.trim()) input.current?.focus();
  }, []);
  useEffect(() => {
    if (!query.trim()) return;
    setHits(null);
    setError("");
    getJSON<SearchHit[]>("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        limit,
        strategy,
        ...(only ? { filters: { document_id: only } } : {}),
      }),
    })
      .then(setHits)
      .catch((e: Error) => setError(e.message));
  }, [query, strategy, only, limit]);
  const searchAt = (changes: Record<string, string>) => {
    const params = new URLSearchParams({ q: query, m: strategy, ...(only ? { d: only } : {}) });
    for (const [k, v] of Object.entries(changes)) {
      if (v) params.set(k, v);
      else params.delete(k);
    }
    return `${href("study", "search")}?${params}`;
  };
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    window.location.hash = searchAt({
      q: String(form.get("q") ?? ""),
      m: String(form.get("m")),
      d: String(form.get("d") ?? ""),
      n: "",
    });
  }
  // Each document once (editions share a document ID only within one edition).
  const texts = [...new Map((docs ?? []).map((d) => [d.document_id, d.document])).entries()].sort(
    (a, b) => a[1].localeCompare(b[1]),
  );
  return (
    <div className="search">
      <header className="study-intro">
        <h1>Search the library</h1>
        <form className="search-form" onSubmit={submit} role="search">
          <label className="sr-only" htmlFor="study-q">
            Search terms
          </label>
          <input
            ref={input}
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
          {texts.length > 1 && (
            <select name="d" defaultValue={only} key={only} aria-label="Search in">
              <option value="">All texts</option>
              {texts.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          )}
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
                    <span className="snippet">
                      {marks(h.snippet, query).map((part, i) =>
                        typeof part === "string" ? part : <mark key={i}>{part.hit}</mark>,
                      )}
                      …
                    </span>
                  </a>
                </li>
              );
            })}
            {hits.length === limit && limit < 50 && (
              <li className="search-more">
                <a href={searchAt({ n: "50" })}>Show more results</a>
              </li>
            )}
          </ol>
        ))}
    </div>
  );
}

// The Study view's sections, on every Study page.
function StudyNav({ page }: { page: string | undefined }) {
  const { docs } = useLibrary();
  const sutra = docs?.some((d) => d.category === "Brahma Sūtra");
  const links: [string | undefined, string, string, ReactNode][] = [
    [undefined, href("study"), "Library", <BookOpen size={15} />],
    ["search", href("study", "search"), "Search", <SearchIcon size={15} />],
    ["paths", href("study", "paths"), "Paths", <PathIcon size={15} />],
    ...(sutra
      ? ([
          ["sutra", href("study", "sutra", 1, 1, 1), "Side by side", <Columns2 size={15} />],
          ["map", href("study", "map"), "Where they differ", <Waypoints size={15} />],
          ["citations", href("study", "citations"), "Most cited", <BookMarked size={15} />],
        ] as [string, string, string, ReactNode][])
      : []),
    ["notes", href("study", "notes"), "My notes", <StickyNote size={15} />],
  ];
  return (
    <nav className="study-nav" aria-label="Study">
      {links.map(([key, to, label, icon]) => (
        <a key={label} href={to} aria-current={page === key ? "page" : undefined}>
          {icon} {label}
        </a>
      ))}
    </nav>
  );
}

function NotFound() {
  return (
    <div className="study-intro">
      <h1>Page not found</h1>
      <p>This address does not match a page of the Study view.</p>
      <p>
        <a href={href("study")}>Open the library</a>
      </p>
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
  else if (page === "citations") content = <Citations />;
  else if (page === "notes") content = <Notes />;
  else if (page === "map") content = <DivergenceMap route={route} />;
  else if (!page) content = <Library glossary={glossary} />;
  else content = <NotFound />;
  const main = useRef<HTMLElement>(null);
  usePageArrival(main, window.location.hash);
  // "/" searches the library from anywhere in Study.
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key !== "/" || !isShortcut(event)) return;
      event.preventDefault();
      const box = document.getElementById("study-q");
      if (box) box.focus();
      else window.location.hash = href("study", "search");
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  return (
    <div className="view study">
      <main
        id="study-main"
        className={`study-main${page === "sutra" || page === "map" ? " wide" : ""}`}
        ref={main}
      >
        <StudyNav page={page} />
        {content}
      </main>
    </div>
  );
}
