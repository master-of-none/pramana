import { useEffect, useState } from "react";
import { getJSON, thinkerName } from "../lib/api.ts";
import type { Saying } from "../lib/api.ts";
import { href } from "../lib/router.ts";
import { Status } from "./Status.tsx";
import { ByAuthorColumns, Citing, VerseHead } from "./Verse.tsx";

// "Śaṅkara cites it 5 times; Rāmānuja 4": counts as a sentence, never a score.
function tally(counts: Record<string, number> | undefined, verb: string): string {
  const entries = Object.entries(counts ?? {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return "";
  return entries
    .map(([author, n], i) =>
      i === 0
        ? `${thinkerName(author)} ${verb} ${n === 1 ? "once" : `${n} times`}`
        : `${thinkerName(author)} ${n}`,
    )
    .join("; ");
}

// "#/study/sayings": the four great sayings, each opening its verse page.
export function Sayings() {
  const [list, setList] = useState<Saying[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getJSON<Saying[]>("/api/sayings")
      .then(setList)
      .catch((e: Error) => setError(e.message));
  }, []);
  if (!list) return <Status error={error} />;
  return (
    <div className="sayings">
      <header className="study-intro">
        <h1>The great sayings</h1>
        <p>
          The four mahāvākyas, each in the verse where this library’s translation prints it,
          with every place Śaṅkara and Rāmānuja cite that verse and quote its words.
        </p>
      </header>
      <ul className="sy-cards">
        {list.map((s) => (
          <li key={s.key} className="sy-card">
            <p className="sy-saying" lang="sa-Latn">
              {s.saying}
            </p>
            <p className="sy-deva" lang="sa">
              {s.devanagari}
            </p>
            <p className="sy-english">“{s.english}”</p>
            {s.found && s.verse ? (
              <>
                <p className="sy-where">
                  {s.verse.document} {s.verse.place}, {s.number}
                </p>
                <p className="sy-counts">
                  {tally(s.cited, "cites it") || "No printed reference to it in the commentaries"}
                  {Object.entries(s.cited_in_objection ?? {})
                    .map(
                      ([a, n]) =>
                        ` (${thinkerName(a)}: ${n} in setting out the opposing view)`,
                    )
                    .join("")}
                  {Object.keys(s.quoted ?? {}).length > 0 &&
                    `. The same words elsewhere: ${tally(s.quoted, "uses them")}.`}
                </p>
                <a className="sy-open" href={href("study", "saying", s.key)}>
                  Read the verse and its citations
                </a>
              </>
            ) : (
              <p className="sy-missing">Not found in this library’s texts.</p>
            )}
            <p className="sy-note">{s.note}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

// "#/study/saying/{key}": the verse page for a saying, plus its words used elsewhere.
export function SayingPage({ sayingKey }: { sayingKey: string }) {
  const [data, setData] = useState<Saying | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setData(null);
    getJSON<Saying>(`/api/sayings/${encodeURIComponent(sayingKey)}`)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [sayingKey]);
  if (!data) return <Status error={error} />;
  return (
    <div className="verse-page">
      <header className="study-intro">
        <a className="back-link" href={href("study", "sayings")}>
          The great sayings
        </a>
        <h1 lang="sa-Latn">{data.saying}</h1>
        <p className="sy-deva" lang="sa">
          {data.devanagari}
        </p>
        <p className="sy-english">“{data.english}”</p>
        <p className="dv-caveat">{data.note}</p>
      </header>
      {!data.found || !data.verse ? (
        <Status>
          This saying’s verse was not found in this library’s texts (its words must occur in
          the printed verse).
        </Status>
      ) : (
        <>
          <VerseHead page={data.verse} mark={data.mark} number={data.number} />
          <h2 className="vs-heading">Where it is cited</h2>
          <Citing page={data.verse} />
          {!!data.quotations?.length && (
            <section className="vs-quoted" aria-labelledby="vs-quoted-title">
              <h2 id="vs-quoted-title" className="vs-heading">
                The same words elsewhere
              </h2>
              <p className="dv-caveat">
                Places that use the saying’s words without a printed reference to this verse:
                quotations, allusions, or the same words in another text. Read each in context.
              </p>
              <ByAuthorColumns
                groups={data.quotations}
                verb="uses them"
                label="The same words elsewhere, by author"
              />
            </section>
          )}
        </>
      )}
    </div>
  );
}
