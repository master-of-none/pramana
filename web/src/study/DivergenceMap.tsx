import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Columns2, Grid3x3, Table2, X } from "lucide-react";
import type { Band, CitedRef, DivergenceUnit, Signal } from "../lib/api.ts";
import { BANDS, SIGNALS, reasons } from "../lib/divergence.ts";
import { href, readAt } from "../lib/router.ts";
import type { Route } from "../lib/router.ts";
import { useDivergence } from "./data.ts";
import { Status } from "./Status.tsx";

const SIGNAL_TEXT: Record<Exclude<Signal, "overall">, string> = {
  scripture: "How different the scripture each one cites here is.",
  wording: "How little the wording of the two translations (both Thibaut's) overlaps.",
  dispute: "How often Rāmānuja's text here names doctrines distinctive of Śaṅkara's reading.",
};
const bandText = (band: Band | null) => band ?? "not measured";

function Refs({ refs }: { refs: CitedRef[] }) {
  return (
    <>
      {refs.map((r, i) => (
        <span key={`${r.chapter_id}-${r.start}`}>
          {i > 0 && ", "}
          <a href={readAt(r.chapter_id, r.start, r.end)}>{r.label}</a>
        </span>
      ))}
    </>
  );
}

function Detail({ unit, onClose }: { unit: DivergenceUnit; onClose: () => void }) {
  const { bands } = unit;
  return (
    <aside className="dv-detail" aria-labelledby="dv-detail-title">
      <header>
        <h2 id="dv-detail-title">Brahma Sūtra {unit.label}</h2>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close details">
          <X size={16} />
        </button>
      </header>
      <p className="dv-overall">
        <span className="dv-swatch" data-band={bands.overall ?? "none"} aria-hidden="true" />
        Overall: <strong>{bandText(bands.overall)}</strong>
        {reasons(unit).length > 0 && <> · {reasons(unit).join("; ")}</>}
      </p>
      {!unit.ramanuja.length ? (
        <p className="dv-caveat">No page of Rāmānuja’s matches these sūtras.</p>
      ) : unit.pairing === "renumbered" ? (
        <p className="dv-caveat">
          The same sūtra by its printed words: Rāmānuja numbers it {unit.ramanuja_sutra}.
        </p>
      ) : (
        unit.pairing === "unconfirmed" && (
          <p className="dv-caveat dv-unconfirmed">
            Paired by number only: the two printed sūtras do not match, so this may compare
            different sūtras (the recensions divide and number some differently) or the
            same sūtra translated differently. Read both before relying on it.
          </p>
        )
      )}
      <dl>
        <div>
          <dt>
            Scripture cited: <strong>{bandText(bands.scripture)}</strong>
          </dt>
          <dd>
            {SIGNAL_TEXT.scripture}{" "}
            {bands.scripture === null
              ? "Neither page cites scripture that could be resolved."
              : `${unit.shared} passage${unit.shared === 1 ? "" : "s"} cited by both.`}
            {unit.only_shankara.length > 0 && (
              <span className="dv-refs">
                Only Śaṅkara: <Refs refs={unit.only_shankara} />
              </span>
            )}
            {unit.only_ramanuja.length > 0 && (
              <span className="dv-refs">
                Only Rāmānuja: <Refs refs={unit.only_ramanuja} />
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt>
            Wording: <strong>{bandText(bands.wording)}</strong>
          </dt>
          <dd>{SIGNAL_TEXT.wording}</dd>
        </div>
        <div>
          <dt>
            Dispute terms: <strong>{bandText(bands.dispute)}</strong>
          </dt>
          <dd>
            {SIGNAL_TEXT.dispute}{" "}
            {Object.keys(unit.terms).length
              ? Object.entries(unit.terms)
                  .map(([t, n]) => `${t} ×${n}`)
                  .join(", ")
              : "None of the terms occurs."}
          </dd>
        </div>
      </dl>
      <p className="dv-actions">
        {unit.pairing === "same" ? (
          <a className="dv-read" href={href("study", "sutra", unit.book, unit.pada, unit.first)}>
            <Columns2 size={15} /> Read side by side
          </a>
        ) : (
          <>
            <a className="dv-read" href={href("study", "read", unit.shankara[0])}>
              Śaṅkara’s page
            </a>
            {unit.ramanuja[0] && (
              <a className="dv-read" href={href("study", "read", unit.ramanuja[0])}>
                Rāmānuja’s page
              </a>
            )}
          </>
        )}
      </p>
    </aside>
  );
}

// "Where they part ways": the whole Brahma Sūtra, one cell per stretch of Śaṅkara's
// commentary, shaded by how differently the two commentaries treat it (a heuristic).
export function DivergenceMap({ route }: { route: Route }) {
  const { data, error } = useDivergence();
  const [signal, setSignal] = useState<Signal>("overall");
  const [view, setView] = useState<"map" | "table">("map");
  const [sort, setSort] = useState<Signal | "sutra">("sutra");
  const units = data?.units ?? [];
  const wanted = route.query.get("u");
  const [selected, setSelected] = useState<number | null>(null);
  const [focus, setFocus] = useState(0);
  const cells = useRef<(HTMLButtonElement | null)[]>([]);
  useEffect(() => {
    if (!wanted || !units.length) return;
    const i = units.findIndex((u) => u.label === wanted);
    if (i >= 0) {
      setSelected(i);
      setFocus(i);
    }
  }, [wanted, units.length]);
  // Rows of the grid: adhyāya -> pāda -> unit indices.
  const rows = useMemo(() => {
    const out: { book: string; padas: { pada: string; items: number[] }[] }[] = [];
    units.forEach((u, i) => {
      let book = out.find((b) => b.book === u.book);
      if (!book) out.push((book = { book: u.book, padas: [] }));
      let pada = book.padas.find((p) => p.pada === u.pada);
      if (!pada) book.padas.push((pada = { pada: u.pada, items: [] }));
      pada.items.push(i);
    });
    return out;
  }, [units]);
  if (!data) return <Status error={error} />;
  if (!data.available)
    return (
      <div className="study-intro">
        <h1>Where they part ways</h1>
        <p>{data.reason}</p>
      </div>
    );

  const flat = rows.flatMap((b) => b.padas);
  function move(event: KeyboardEvent, i: number) {
    const row = flat.findIndex((p) => p.items.includes(i));
    const at = flat[row].items.indexOf(i);
    let next: number | undefined;
    if (event.key === "ArrowRight") next = flat[row].items[at + 1] ?? flat[row + 1]?.items[0];
    else if (event.key === "ArrowLeft")
      next = flat[row].items[at - 1] ?? flat[row - 1]?.items.at(-1);
    else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      const other = flat[row + (event.key === "ArrowDown" ? 1 : -1)];
      next = other?.items[Math.min(at, other.items.length - 1)];
    } else if (event.key === "Home") next = flat[row].items[0];
    else if (event.key === "End") next = flat[row].items.at(-1);
    else if (event.key === "Escape" && selected !== null) {
      setSelected(null);
      event.preventDefault();
      return;
    } else return;
    event.preventDefault();
    if (next === undefined) return;
    setFocus(next);
    cells.current[next]?.focus();
  }
  // Confirmed pairs only: the same sūtra on both sides.
  const top = (data.ranking ?? [])
    .filter((i) => units[i].pairing !== "unconfirmed" && units[i].bands.overall)
    .slice(0, 12);
  const order = (b: Band | null) => (b ? BANDS.indexOf(b) : -1);
  const sorted =
    sort === "sutra"
      ? units.map((_, i) => i)
      : units.map((_, i) => i).sort((a, b) => order(units[b].bands[sort]) - order(units[a].bands[sort]) || a - b);

  return (
    <div className="divergence">
      <header className="study-intro">
        <h1>Where they part ways</h1>
        <p>
          Śaṅkara and Rāmānuja on the whole Brahma Sūtra. Each cell is one page of Śaṅkara’s
          commentary, set beside Rāmānuja’s pages on the same sūtras, and shaded by how
          differently the two treat it: the scripture they cite, how much wording they share,
          and how often Rāmānuja names doctrines distinctive of Śaṅkara. A dot marks the
          highest band.
        </p>
        <p className="dv-caveat">
          A map of where to read, measured from the texts’ words and citations: not a judgement
          of doctrine or of who is right. The two recensions divide and number some sūtras
          differently, so pairs are matched on the printed sūtra’s words; where those differ,
          the cell is hatched.
        </p>
      </header>

      <div className="dv-controls">
        <div role="radiogroup" aria-label="Shade by" className="dv-signals">
          {SIGNALS.map(([s, label]) => (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={signal === s}
              onClick={() => setSignal(s)}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="dv-view"
          onClick={() => setView(view === "map" ? "table" : "map")}
        >
          {view === "map" ? <Table2 size={15} /> : <Grid3x3 size={15} />}
          {view === "map" ? "Show as a table" : "Show as a map"}
        </button>
      </div>
      <ul className="dv-legend" aria-label="Legend">
        {BANDS.map((b) => (
          <li key={b}>
            <span className="dv-swatch" data-band={b} aria-hidden="true" />
            {b}
          </li>
        ))}
        <li>
          <span className="dv-swatch" data-band="none" aria-hidden="true" />
          not measured
        </li>
        <li>
          <span className="dv-swatch unconfirmed" data-band="marked" aria-hidden="true" />
          hatched: paired by number only
        </li>
      </ul>

      <div className={`dv-layout${selected !== null ? " with-detail" : ""}`}>
        {view === "map" ? (
          <div className="dv-map">
            {rows.map(({ book, padas }) => (
              <section key={book} aria-label={`Adhyāya ${book}`}>
                <h2>Adhyāya {book}</h2>
                {padas.map(({ pada, items }) => (
                  <div className="dv-row" key={pada}>
                    <span className="dv-pada" aria-hidden="true">
                      {book}.{pada}
                    </span>
                    <div className="dv-cells" role="group" aria-label={`Pāda ${book}.${pada}`}>
                      {items.map((i) => {
                        const u = units[i];
                        const b = u.bands[signal];
                        return (
                          <button
                            key={u.label}
                            ref={(el) => {
                              cells.current[i] = el;
                            }}
                            type="button"
                            className={`dv-cell${u.pairing === "unconfirmed" ? " unconfirmed" : ""}`}
                            data-band={b ?? "none"}
                            tabIndex={i === focus ? 0 : -1}
                            aria-pressed={selected === i}
                            aria-label={`Brahma Sūtra ${u.label}: ${bandText(b)}${u.pairing === "unconfirmed" ? ", pairing unconfirmed" : ""}`}
                            title={`${u.label}: ${bandText(b)}${u.pairing === "unconfirmed" ? " (pairing unconfirmed)" : ""}`}
                            onFocus={() => setFocus(i)}
                            onKeyDown={(event) => move(event, i)}
                            onClick={() => setSelected(selected === i ? null : i)}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}
              </section>
            ))}
          </div>
        ) : (
          <table className="dv-table">
            <caption className="sr-only">Bands per stretch of sūtras</caption>
            <thead>
              <tr>
                {(
                  [
                    ["sutra", "Sūtras"],
                    ...SIGNALS,
                  ] as [Signal | "sutra", string][]
                ).map(([key, label]) => (
                  <th key={key} aria-sort={sort === key ? (key === "sutra" ? "ascending" : "descending") : "none"}>
                    <button type="button" onClick={() => setSort(key)}>
                      {label}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((i) => {
                const u = units[i];
                return (
                  <tr key={u.label} aria-selected={selected === i}>
                    <th scope="row">
                      <button type="button" className="dv-link" onClick={() => setSelected(i)}>
                        {u.label}
                      </button>
                    </th>
                    {SIGNALS.map(([s]) => (
                      <td key={s}>
                        <span className="dv-swatch" data-band={u.bands[s] ?? "none"} aria-hidden="true" />
                        {bandText(u.bands[s])}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {selected !== null && units[selected] && (
          <Detail
            unit={units[selected]}
            onClose={() => {
              setSelected(null);
              cells.current[selected]?.focus();
            }}
          />
        )}
      </div>

      {top.length > 0 && (
        <section className="dv-top" aria-labelledby="dv-top-title">
          <h2 id="dv-top-title">Where they part ways most</h2>
          <ol>
            {top.map((i) => (
              <li key={units[i].label}>
                <button type="button" className="dv-link" onClick={() => setSelected(i)}>
                  {units[i].label}
                </button>
                <span>{reasons(units[i]).join("; ") || units[i].bands.overall}</span>
                <a href={href("study", "sutra", units[i].book, units[i].pada, units[i].first)}>
                  Side by side
                </a>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
