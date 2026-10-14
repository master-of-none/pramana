import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  Copy,
  ExternalLink,
  Library,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import "./style.css";

type Location = { book: string; chapter: string; sections: string[] };
type Citation = {
  document: string;
  edition: string;
  translator: string;
  language: string;
  location: Location;
  pages: string[];
  source_url: string;
  passage_id: string;
  label: string;
};
type Passage = {
  id: string;
  chapter_id: string;
  text: string;
  start: number;
  end: number;
  citation: Citation;
};
type Hit = {
  passage: Passage;
  snippet: string;
  score: number;
  score_kind: string;
};
type Note = { id: string; text: string; anchor_offset: number | null };
type Context = {
  id: string;
  chapter: {
    document: string;
    text: string;
    summary: string;
    notes: Note[];
    location: Location;
    source: { url: string; attribution: string; rights: string };
  };
  selected: Passage;
};
type Status = {
  chapters: number;
  passages: number;
  indexed: boolean;
  locations: {
    corpus_id: string;
    edition: string;
    translator: string;
    language: string;
    book: string;
    chapter: string;
  }[];
};
const bookNames = [
  "Origins & creation",
  "The world & its realms",
  "Traditions & society",
  "Dynasties & lineages",
  "The life of Krishna",
  "Dissolution & liberation",
];
const examples = [
  "How was the world created?",
  "Why did Dhruva become the pole star?",
  "What happens at the end of the Kali age?",
];

async function getJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "The request could not be completed. Try again.",
    );
  return data as T;
}

function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [statusError, setStatusError] = useState("");
  const params = new URLSearchParams(window.location.search);
  const [query, setQuery] = useState(params.get("q") || "");
  const [book, setBook] = useState(params.get("book") || "");
  const [chapter, setChapter] = useState(params.get("chapter") || "");
  const [corpus, setCorpus] = useState(params.get("corpus") || "");
  const [strategy, setStrategy] = useState(
    ["lexical", "dense", "hybrid"].includes(params.get("strategy") || "")
      ? params.get("strategy")!
      : "hybrid",
  );
  const [hits, setHits] = useState<Hit[]>([]);
  const [searched, setSearched] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Hit | null>(null);
  const [context, setContext] = useState<Context | null>(null);
  const [contextError, setContextError] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const [mobileFilters, setMobileFilters] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const abortSearch = useRef<AbortController | null>(null);
  const reader = useRef<HTMLElement>(null);
  const initialSearch = useRef(false);
  const resultOpener = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    getJSON<Status>("/api/status")
      .then(setStatus)
      .catch((e) => setStatusError(e.message));
    return () => abortSearch.current?.abort();
  }, []);

  useEffect(() => {
    if (status?.indexed && !initialSearch.current) {
      initialSearch.current = true;
      if (query.trim()) void runSearch();
    }
  }, [status]);

  useEffect(() => {
    if (selected)
      reader.current?.querySelector("button")?.focus({ preventScroll: true });
    else resultOpener.current?.focus({ preventScroll: true });
  }, [selected]);

  useEffect(() => {
    if (!selected) {
      setContext(null);
      return;
    }
    const abort = new AbortController();
    setContext(null);
    setContextError("");
    setCopied(false);
    setCopyError("");
    getJSON<Context>(
      `/api/chapters/${selected.passage.chapter_id}?passage_id=${selected.passage.id}`,
      { signal: abort.signal },
    )
      .then(setContext)
      .catch((e) => {
        if (e.name !== "AbortError") setContextError(e.message);
      });
    return () => abort.abort();
  }, [selected]);

  useEffect(() => {
    const scroll = reader.current?.querySelector(".reader-scroll");
    const mark = scroll?.querySelector("mark");
    if (context && scroll && mark) {
      scroll.scrollTo({
        top:
          scroll.scrollTop +
          mark.getBoundingClientRect().top -
          scroll.getBoundingClientRect().top -
          20,
        behavior: "smooth",
      });
    }
  }, [context]);

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === "Escape") {
        setSelected(null);
        setMobileFilters(false);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  async function runSearch(
    text = query,
    chosenBook = book,
    chosenChapter = chapter,
    chosenCorpus = corpus,
  ) {
    if (!text.trim()) {
      searchRef.current?.focus();
      return;
    }
    abortSearch.current?.abort();
    const abort = new AbortController();
    abortSearch.current = abort;
    setLoading(true);
    setError("");
    setSelected(null);
    setHits([]);
    setSearched(text.trim());
    setMobileFilters(false);
    const url = new URL(window.location.href);
    url.search = "";
    url.searchParams.set("q", text.trim());
    if (chosenBook) url.searchParams.set("book", chosenBook);
    if (chosenChapter) url.searchParams.set("chapter", chosenChapter);
    if (chosenCorpus) url.searchParams.set("corpus", chosenCorpus);
    if (strategy !== "hybrid") url.searchParams.set("strategy", strategy);
    window.history.replaceState(null, "", url);
    try {
      const results = await getJSON<Hit[]>("/api/search", {
        method: "POST",
        signal: abort.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: text.trim(),
          strategy,
          limit: 10,
          filters: {
            ...(chosenBook ? { book: chosenBook } : {}),
            ...(chosenChapter ? { chapter: chosenChapter } : {}),
            ...(chosenCorpus ? { corpus_id: chosenCorpus } : {}),
          },
        }),
      });
      setHits(results);
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      if (!abort.signal.aborted) setLoading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void runSearch();
  }
  const locations =
    status?.locations.filter(
      (x) => (!corpus || x.corpus_id === corpus) && (!book || x.book === book),
    ) || [];
  const books = [
    ...new Set(
      (status?.locations || [])
        .filter((x) => !corpus || x.corpus_id === corpus)
        .map((x) => x.book),
    ),
  ].sort((a, b) => Number(a) - Number(b));
  const corpora = [...new Set(status?.locations.map((x) => x.corpus_id) || [])];
  const chapters = [...new Set(locations.map((x) => x.chapter))].sort(
    (a, b) => Number(a) - Number(b),
  );

  async function copyCitation() {
    if (!selected) return;
    try {
      await navigator.clipboard.writeText(
        `${selected.passage.citation.label}\n${selected.passage.citation.source_url}`,
      );
      setCopied(true);
      setCopyError("");
    } catch {
      setCopyError(
        "Clipboard is unavailable. Select and copy the citation below.",
      );
    }
  }

  function chapterText(): ReactNode {
    if (!context) return null;
    const chars = Array.from(context.chapter.text); // Python offsets count Unicode code points.
    const { start, end } = context.selected;
    const notes = context.chapter.notes.filter((n) => n.anchor_offset !== null);
    const points = [
      ...new Set([
        0,
        start,
        end,
        chars.length,
        ...notes.map((n) => n.anchor_offset!),
      ]),
    ].sort((a, b) => a - b);
    return points.map((point, i) => (
      <span key={point}>
        {notes
          .filter((n) => n.anchor_offset === point)
          .map((n) => (
            <a
              className="note-ref"
              href={`#note-${n.id}`}
              key={n.id}
              aria-label={`Translator note ${n.id}`}
            >
              {n.id}
            </a>
          ))}
        {i < points.length - 1 &&
          (point >= start && point < end ? (
            <mark>
              {chars
                .slice(point, points[i + 1])
                .join("")
                .replace(/\n{3,}/g, "\n\n")}
            </mark>
          ) : (
            chars
              .slice(point, points[i + 1])
              .join("")
              .replace(/\n{3,}/g, "\n\n")
          ))}
      </span>
    ));
  }

  return (
    <div className={`app ${selected ? "reading" : ""}`}>
      <a className="skip-link" href="#main">
        Skip to search
      </a>
      <header className="topbar">
        <a className="brand" href="/" aria-label="Pramana home">
          <span className="brand-mark">प्र</span>
          <span>
            pramāṇa<span className="brand-sub">A SOURCE FOR EVERY PASSAGE</span>
          </span>
        </a>
        <div className="top-right">
          <span className="local-badge">
            <span /> Local library
          </span>
          <a
            className="about-link"
            href="/docs"
            target="_blank"
            rel="noreferrer"
          >
            API reference <ExternalLink size={13} />
          </a>
        </div>
      </header>

      <aside
        className={`sidebar ${mobileFilters ? "mobile-open" : ""}`}
        aria-label="Library and search filters"
      >
        <div className="sidebar-label">
          <Library size={15} /> YOUR COLLECTION{" "}
          <button
            className="mobile-only icon-button"
            aria-label="Close filters"
            onClick={() => setMobileFilters(false)}
          >
            <X size={18} />
          </button>
        </div>
        <button
          className={`collection ${!corpus ? "active" : ""}`}
          onClick={() => {
            setCorpus("");
            setBook("");
            setChapter("");
          }}
        >
          <span className="collection-icon">
            <BookOpen size={21} />
          </span>
          <span>
            All texts
            <small>{status?.chapters || 0} chapters in your library</small>
          </span>
          <span className="collection-dot" />
        </button>
        {corpora.length > 1 && (
          <label className="filter-label">
            Text
            <select
              value={corpus}
              onChange={(e) => {
                setCorpus(e.target.value);
                setBook("");
                setChapter("");
              }}
            >
              <option value="">All texts</option>
              {corpora.map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
        )}
        <div className="sidebar-rule" />
        <div className="sidebar-label">BROWSE BY BOOK</div>
        <button
          className={`book-row ${!book ? "selected" : ""}`}
          onClick={() => {
            setBook("");
            setChapter("");
          }}
        >
          <span className="book-number">◎</span>
          <span>All books</span>
          <span className="book-count">{status?.chapters || "—"}</span>
        </button>
        {(books.length ? books : ["1", "2", "3", "4", "5", "6"]).map((b) => (
          <button
            className={`book-row ${book === b ? "selected" : ""}`}
            key={b}
            onClick={() => {
              setBook(b);
              setChapter("");
            }}
          >
            <span className="book-number">{b.padStart(2, "0")}</span>
            <span>
              Book {b}
              <small>{bookNames[Number(b) - 1] || "Collected chapters"}</small>
            </span>
            <span className="book-count">
              {status?.locations.filter(
                (x) => x.book === b && (!corpus || x.corpus_id === corpus),
              ).length || "—"}
            </span>
          </button>
        ))}
        <div className="sidebar-rule" />
        <label className="filter-label">
          Chapter
          <select value={chapter} onChange={(e) => setChapter(e.target.value)}>
            <option value="">All chapters</option>
            {chapters.map((c) => (
              <option value={c} key={c}>
                Chapter {c}
              </option>
            ))}
          </select>
        </label>
        <label className="filter-label">
          Search method
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
          >
            <option value="hybrid">Hybrid · semantic + keyword</option>
            <option value="lexical">Keyword · BM25</option>
            <option value="dense">Semantic · local embeddings</option>
          </select>
        </label>
        <p className="filter-hint">Filters apply to your next search.</p>
        <div className="edition-card">
          <span className="eyebrow">ABOUT THIS EDITION</span>
          <h3>Vishnu Purana</h3>
          <p>H. H. Wilson · 1840</p>
          <p className="edition-detail">
            English translation
            <br />
            Sacred Texts distribution · 2006
          </p>
          <a
            href="https://archive.sacred-texts.com/hin/vp/"
            target="_blank"
            rel="noreferrer"
          >
            View source edition <ExternalLink size={12} />
          </a>
        </div>
        <div className="sidebar-footer">
          <span
            className={status?.indexed ? "status-dot ready" : "status-dot"}
          />
          {status?.indexed
            ? `${status.passages.toLocaleString()} passages indexed`
            : "Library needs setup"}
          <span className="version">v0.1</span>
        </div>
      </aside>

      <main id="main" className="main">
        <div className="workspace-heading">
          <span>
            <span className="eyebrow">THE READING ROOM</span>
            <span className="heading-separator">/</span>Explore the texts
          </span>
          <button
            className="mobile-only filter-toggle"
            onClick={() => setMobileFilters(true)}
          >
            <SlidersHorizontal size={15} /> Filters
          </button>
          <span className="workspace-tag">RETRIEVE · READ · TRACE</span>
        </div>
        <div className={`search-area ${searched ? "compact" : ""}`}>
          {!searched && (
            <>
              <div className="intro-kicker">
                <span /> KNOWLEDGE BEGINS WITH A SOURCE
              </div>
              <h1>
                Ask the texts.
                <br />
                <em>Read the evidence.</em>
              </h1>
              <p className="intro-copy">
                Explore ancient ideas through the passages that carry them.
                <br className="desktop-only" /> Search the Vishnu Purana, then
                follow each result to its source.
              </p>
            </>
          )}
          <form className="search-form" onSubmit={submit}>
            <Search size={21} />
            <input
              ref={searchRef}
              aria-label="Search the library"
              placeholder="What would you like to explore?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={2000}
            />
            <kbd>⌘ K</kbd>
            <button
              type="submit"
              aria-label="Search"
              disabled={loading || !query.trim()}
            >
              <ArrowRight size={20} />
            </button>
          </form>
          <div className="search-meta">
            <span>
              {book ? `Book ${book}` : "All books"}
              {chapter ? ` · Chapter ${chapter}` : ""}
              <ChevronDown size={12} />
            </span>
            <span>
              English <span className="meta-dot">·</span>{" "}
              {strategy === "hybrid"
                ? "Hybrid search"
                : strategy === "lexical"
                  ? "Keyword search"
                  : "Semantic search"}
            </span>
          </div>
        </div>

        {(statusError || error || (status && !status.indexed)) && (
          <div className="notice" role="alert">
            <BookOpen size={20} />
            <div>
              <h3>
                {statusError || error
                  ? "A little setup may be needed"
                  : "Prepare your local library"}
              </h3>
              <p>
                {statusError ||
                  error ||
                  "Download an edition, import its chapters, and build the local search index."}
              </p>
              {(!status?.indexed || /model|index|setup/i.test(error)) && (
                <pre>
                  pramana model setup{"\n"}pramana corpus download{"\n"}pramana
                  ingest .pramana/corpora/vishnu-purana/chapters.jsonl{"\n"}
                  pramana index
                </pre>
              )}
            </div>
          </div>
        )}

        {!searched && (
          <div className="welcome-content">
            <div className="section-title">
              <span>A FEW PLACES TO BEGIN</span>
              <span className="title-line" />
            </div>
            <div className="example-grid">
              {examples.map((example, i) => (
                <button
                  className="example"
                  key={example}
                  onClick={() => {
                    setQuery(example);
                    void runSearch(example);
                  }}
                >
                  <span className="example-number">0{i + 1}</span>
                  <span>{example}</span>
                  <ArrowRight size={16} />
                </button>
              ))}
            </div>
            <div className="principles">
              <div>
                <span className="principle-icon">
                  <Search size={18} />
                </span>
                <h3>Find the passage</h3>
                <p>
                  Search by meaning and by word, across every indexed chapter.
                </p>
              </div>
              <div>
                <span className="principle-icon">
                  <BookOpen size={18} />
                </span>
                <h3>Keep the context</h3>
                <p>
                  Read the surrounding chapter, with the translator’s notes
                  close by.
                </p>
              </div>
              <div>
                <span className="principle-icon">
                  <ExternalLink size={18} />
                </span>
                <h3>Trace the source</h3>
                <p>
                  Every result carries its edition, location, and original
                  reference.
                </p>
              </div>
            </div>
            <div className="library-footnote">
              <span>प्रमाण</span>
              <p>
                <strong>pramāṇa</strong> <em>noun</em> · a means of knowledge
                <br />A reading tool built around sources, context, and careful
                inquiry.
              </p>
            </div>
          </div>
        )}

        {searched && (
          <section
            className="results"
            aria-label="Search results"
            aria-busy={loading}
          >
            <div className="results-header">
              <div>
                <span className="eyebrow">PASSAGES</span>
                <h2>
                  {loading
                    ? "Searching your library…"
                    : `${hits.length} ${hits.length === 1 ? "passage" : "passages"} to explore`}
                </h2>
              </div>
              <span className="result-query">“{searched}”</span>
            </div>
            <p className="results-note">
              Ranked by retrieval relevance. Read each passage in context to
              assess its meaning.
            </p>
            <div aria-live="polite" className="sr-only">
              {loading ? "Searching" : `${hits.length} results found`}
            </div>
            {loading &&
              [1, 2, 3].map((x) => (
                <div className="skeleton" key={x}>
                  <span />
                  <span />
                  <span />
                </div>
              ))}
            {!loading && !error && hits.length === 0 && (
              <div className="empty-state">
                <Search size={28} />
                <h3>No passages matched these filters.</h3>
                <p>
                  Try broader search terms, or select all books and chapters.
                </p>
                <button
                  onClick={() => {
                    setBook("");
                    setChapter("");
                    setCorpus("");
                    void runSearch(query, "", "", "");
                  }}
                >
                  Clear filters
                </button>
              </div>
            )}
            {hits.map((hit, i) => (
              <button
                key={hit.passage.id}
                className={`result-card ${selected?.passage.id === hit.passage.id ? "current" : ""}`}
                onClick={(event) => {
                  resultOpener.current = event.currentTarget;
                  setSelected(hit);
                }}
                onKeyDown={(event) => {
                  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                    event.preventDefault();
                    const sibling =
                      event.key === "ArrowDown"
                        ? event.currentTarget.nextElementSibling
                        : event.currentTarget.previousElementSibling;
                    if (sibling instanceof HTMLButtonElement) sibling.focus();
                  }
                }}
              >
                <div className="result-top">
                  <span className="result-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>{hit.passage.citation.document}</span>
                  <span className="result-location">
                    BOOK {hit.passage.citation.location.book} <span>·</span>{" "}
                    CHAPTER {hit.passage.citation.location.chapter}
                  </span>
                  <ArrowRight size={16} />
                </div>
                <p className="passage-excerpt">
                  {hit.snippet}
                  {hit.passage.text.length > hit.snippet.length ? "…" : ""}
                </p>
                <div className="result-bottom">
                  <span>
                    {hit.passage.citation.translator}
                    {hit.passage.citation.pages.length
                      ? ` · pp. ${hit.passage.citation.pages.join(", ")}`
                      : ""}
                  </span>
                  <span>
                    Read in context <ArrowRight size={12} />
                  </span>
                </div>
              </button>
            ))}
          </section>
        )}
        <footer className="main-footer">
          <span>Every passage has a source.</span>
          <span>Stored locally. Searched locally.</span>
        </footer>
      </main>

      {selected && (
        <aside ref={reader} className="reader" aria-label="Chapter reader">
          <div className="reader-toolbar">
            <button className="back-results" onClick={() => setSelected(null)}>
              <ArrowLeft size={15} /> Results
            </button>
            <span>
              {context
                ? `BOOK ${context.chapter.location.book} · CHAPTER ${context.chapter.location.chapter}`
                : "IN CONTEXT"}
            </span>
            <button
              className="icon-button"
              onClick={() => setSelected(null)}
              aria-label="Close chapter reader"
            >
              <X size={18} />
            </button>
          </div>
          <div className="reader-scroll">
            {contextError && (
              <div className="notice" role="alert">
                <p>{contextError}</p>
              </div>
            )}
            {!context && !contextError && (
              <p className="loading-context" role="status">
                Opening the chapter…
              </p>
            )}
            {context && (
              <>
                <span className="eyebrow">{context.chapter.document}</span>
                <h2>
                  Book {context.chapter.location.book}
                  <span>Chapter {context.chapter.location.chapter}</span>
                </h2>
                <p className="reader-edition">
                  {selected.passage.citation.translator} ·{" "}
                  {selected.passage.citation.language}
                  <br />
                  {selected.passage.citation.edition}
                </p>
                <div className="reader-rule" />
                <p className="summary-label">CHAPTER SUMMARY · EDITION TEXT</p>
                <p className="chapter-summary">{context.chapter.summary}</p>
                <div className="highlight-legend">
                  <span /> Your selected passage is highlighted{" "}
                  <ArrowDown size={12} />
                </div>
                <div className="chapter-text">{chapterText()}</div>
                <section className="translator-notes">
                  <h3>
                    Translator’s notes{" "}
                    <span>{context.chapter.notes.length}</span>
                  </h3>
                  <p className="notes-description">
                    Commentary from this edition, separate from the translation.
                  </p>
                  {context.chapter.notes.map((note) => (
                    <div
                      className="translator-note"
                      key={note.id}
                      id={`note-${note.id}`}
                    >
                      <span>{note.id}</span>
                      <p>{note.text}</p>
                    </div>
                  ))}
                </section>
                <section className="citation-box">
                  <span className="eyebrow">SOURCE & CITATION</span>
                  <p>{selected.passage.citation.label}</p>
                  <div className="citation-actions">
                    <button onClick={() => void copyCitation()}>
                      {copied ? <Check size={14} /> : <Copy size={14} />}
                      {copied ? "Copied" : "Copy citation"}
                    </button>
                    <a
                      href={selected.passage.citation.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Original source <ExternalLink size={13} />
                    </a>
                  </div>
                  {copyError && <p role="alert">{copyError}</p>}
                  <p className="attribution">
                    {context.chapter.source.attribution}
                    <br />
                    {context.chapter.source.rights}
                  </p>
                </section>
              </>
            )}
          </div>
        </aside>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
