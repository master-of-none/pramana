import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import { getJSON, thinkerName } from "../lib/api.ts";
import type { ByAuthor, Excerpt, VerseCitation, VersePage } from "../lib/api.ts";
import { codePointIndex } from "../lib/offsets.ts";
import { readAt } from "../lib/router.ts";
import type { Route } from "../lib/router.ts";
import { Status } from "./Status.tsx";

const STATUS_WORDS = {
  verified: "quoted words found in the verse",
  numbered: "by verse number",
  chapter: "the whole section",
};

// An excerpt with one span marked (code-point offsets from the API).
export function ExcerptText({ excerpt }: { excerpt: Excerpt }) {
  const at = codePointIndex(excerpt.text);
  const [s, e] = [at(excerpt.start), at(excerpt.end)];
  return (
    <blockquote className="vs-excerpt">
      {excerpt.clipped_before && "… "}
      {excerpt.text.slice(0, s)}
      <mark>{excerpt.text.slice(s, e)}</mark>
      {excerpt.text.slice(e)}
      {excerpt.clipped_after && " …"}
    </blockquote>
  );
}

function Passage({ p }: { p: VerseCitation }) {
  return (
    <li className="vs-passage">
      <ExcerptText excerpt={p.context} />
      <p className="vs-source">
        <a href={readAt(p.chapter_id, p.start, p.end)}>
          {p.document} {p.place}
        </a>
        {p.status && <span className="vs-status"> · {STATUS_WORDS[p.status]}</span>}
      </p>
      {p.role && (
        <p className={`vs-role ${p.role.role}`}>
          {p.role.role === "objection"
            ? "Cited in setting out the opposing view"
            : "Cited in the reply"}
          {p.role.from === "cue" ? " (as the text marks it)" : ` (page: “${p.role.from}”)`}
        </p>
      )}
    </li>
  );
}

// Each author in a column: how many times, then every passage with its context.
export function ByAuthorColumns({
  groups,
  verb,
  label,
}: {
  groups: ByAuthor[];
  verb: string;
  label: string;
}) {
  return (
    <div className="vs-columns" aria-label={label} role="group">
      {groups.map((g) => (
        <section key={g.author} className="vs-column">
          <h3>
            {thinkerName(g.author)} {verb}{" "}
            {g.passages.length === 1 ? "once" : `${g.passages.length} times`}
          </h3>
          {(() => {
            const n = g.passages.filter((p) => p.role?.role === "objection").length;
            return n ? (
              <p className="vs-role-note">
                {n === g.passages.length ? "All" : n} in setting out the opposing view
              </p>
            ) : null;
          })()}
          <ol>
            {g.passages.map((p) => (
              <Passage key={`${p.chapter_id}-${p.start}`} p={p} />
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

// The verse, highlighted where `mark` falls (code points within the chapter).
export function VerseHead({
  page,
  mark,
  number,
}: {
  page: VersePage;
  mark?: [number, number];
  number?: number;
}) {
  const at = codePointIndex(page.text);
  const [s, e] = mark
    ? [at(mark[0] - page.start), at(mark[1] - page.start)]
    : [page.text.length, page.text.length];
  return (
    <figure className="vs-verse">
      <blockquote>
        {page.text.slice(0, s)}
        {mark && <mark>{page.text.slice(s, e)}</mark>}
        {page.text.slice(e)}
      </blockquote>
      <figcaption>
        {page.document} {page.place}
        {number !== undefined && `, ${number}`} · tr. {page.translator} ·{" "}
        <a href={readAt(page.chapter_id, page.start, page.end)}>
          <BookOpen size={13} /> Read it in context
        </a>
      </figcaption>
    </figure>
  );
}

export function Citing({ page }: { page: VersePage }) {
  return (
    <>
      {page.citations.length ? (
        <ByAuthorColumns
          groups={page.citations}
          verb="cites it"
          label="Passages citing this verse, by author"
        />
      ) : (
        <p className="study-status">
          No commentary in this library cites this verse with a printed reference.
        </p>
      )}
      {page.whole.length > 0 && (
        <details className="vs-whole">
          <summary>
            Cited for the whole section ·{" "}
            {page.whole.map((g) => `${thinkerName(g.author)} ${g.passages.length}`).join(" · ")}
          </summary>
          <ByAuthorColumns
            groups={page.whole}
            verb="cites the section"
            label="Passages citing the whole section"
          />
        </details>
      )}
    </>
  );
}

// "#/study/verse/{chapter}?s=&e=": one verse beside every passage that cites it.
export function Verse({ id, route }: { id: string; route: Route }) {
  const start = Number(route.query.get("s"));
  const end = Number(route.query.get("e"));
  const [page, setPage] = useState<VersePage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setPage(null);
    setError("");
    const params = new URLSearchParams({ chapter_id: id, start: String(start), end: String(end) });
    getJSON<VersePage>(`/api/verse?${params}`)
      .then(setPage)
      .catch((e: Error) => setError(e.message));
  }, [id, start, end]);
  if (!page) return <Status error={error} />;
  return (
    <div className="verse-page">
      <header className="study-intro">
        <h1 data-title={`${page.document} ${page.place}`}>
          {page.document} {page.place}
        </h1>
        <p>
          The verse beside every passage of the commentaries that cites it with a printed
          reference, in each translator’s words.
        </p>
      </header>
      <VerseHead page={page} />
      <h2 className="vs-heading">Where it is cited</h2>
      <Citing page={page} />
    </div>
  );
}
