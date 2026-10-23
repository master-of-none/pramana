import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { annotate } from "../lib/glossary.tsx";
import type { Glossary } from "../lib/glossary.tsx";
import { codePointIndex, cuts } from "../lib/offsets.ts";
import type { Span } from "../lib/offsets.ts";
import { CITATION_STATUS, thinkerName } from "../lib/api.ts";
import type { ChapterCitations, ChapterContext, CitedBy } from "../lib/api.ts";
import { readAt } from "../lib/router.ts";

export const ROLE_LABEL = { objection: "Objection", reply: "Reply" };
export const stepId = (chapter: string, index: number) =>
  `${chapter}-step-${index}`;

// Where a scripture passage is cited, grouped by thinker, each linking to the citation.
function CitedByList({ refs, whole }: { refs: CitedBy[]; whole?: boolean }) {
  const groups = new Map<string, CitedBy[]>();
  for (const r of refs) {
    const name = thinkerName(r.author);
    groups.set(name, [...(groups.get(name) ?? []), r]);
  }
  const tally = [...groups].map(([name, rs]) => `${name} ${rs.length}`).join(" · ");
  return (
    <details className={`cited-by${whole ? " whole" : ""}`}>
      <summary>
        {whole ? "This chapter is cited" : "Cited"} · {tally}
      </summary>
      {[...groups].map(([name, rs]) => (
        <div key={name} className="cited-group">
          <h5>{name}</h5>
          <ul>
            {rs.map((r) => (
              <li key={`${r.chapter_id}-${r.start}`}>
                <a href={readAt(r.chapter_id, r.start, r.end)}>
                  {r.document} {r.place}
                </a>{" "}
                <span className={`cite-status ${r.status}`} title={CITATION_STATUS[r.status]}>
                  {r.status === "verified" ? "quotation found" : r.status === "numbered" ? "by verse number" : "chapter"}
                </span>
                {r.quote && <q>{r.quote.length > 140 ? `${r.quote.slice(0, 140)}…` : r.quote}</q>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </details>
  );
}

// Renders canonical chapter text; every API offset is a Python code point.
export function ChapterText({
  context,
  glossary,
  highlight,
  citations,
}: {
  context: ChapterContext;
  glossary: Glossary | null;
  highlight?: Span;
  citations?: ChapterCitations | null;
}) {
  const { chapter, roles } = context;
  const text = chapter.text;
  const at = codePointIndex(text);
  const mark = useRef<HTMLElement>(null);
  useEffect(() => {
    mark.current?.scrollIntoView({ block: "center" });
  }, [context.id, highlight?.start]);

  const paragraphs: Span[] = [];
  let start = 0;
  for (const m of text.matchAll(/\n\s*\n/g)) {
    paragraphs.push({ start, end: m.index! });
    start = m.index! + m[0].length;
  }
  paragraphs.push({ start, end: text.length });

  // Marks in the blank line between paragraphs belong to the following paragraph.
  const snap = (x: number) => {
    const next = paragraphs.find((p) => x <= p.end);
    return next && x < next.start ? next.start : x;
  };

  const roleSpans = roles.map((r) => ({
    ...r,
    start: at(r.start),
    end: at(r.end),
    label: snap(at(r.start)),
  }));
  const lit = highlight && {
    start: at(highlight.start),
    end: at(highlight.end),
  };
  const pages = chapter.pages.map((p) => ({
    at: snap(at(p.offset)),
    label: p.label,
  }));
  const anchored = chapter.notes.filter((n) => n.anchor_offset !== null);
  const notes = anchored.map((n) => ({
    at: snap(at(n.anchor_offset!)),
    note: n,
  }));
  const links = (citations?.outgoing ?? []).map((c) => ({
    ...c,
    start: at(c.start),
    end: at(c.end),
  }));
  // Citations of this chapter: by paragraph, or of the chapter as a whole.
  const incoming = citations?.incoming ?? [];
  const whole = incoming.filter((r) => r.target_start === 0 && r.target_end === text.length);
  const byParagraph = new Map<number, CitedBy[]>();
  for (const r of incoming) {
    if (whole.includes(r)) continue;
    const x = at(r.target_start);
    const i = paragraphs.findIndex((p) => p.start <= x && x < Math.max(p.end, p.start + 1));
    if (i >= 0) byParagraph.set(i, [...(byParagraph.get(i) ?? []), r]);
  }
  const seen = new Set<string>();
  let litMarked = false;

  function piece(from: number, to: number, key: string): ReactNode {
    const role = roleSpans.find((r) => r.start <= from && to <= r.end);
    const inLit = lit && lit.start <= from && to <= lit.end && from < to;
    const link = links.find((c) => c.start <= from && to <= c.end && from < to);
    const words = annotate(text.slice(from, to), glossary, seen, true);
    const content = link ? (
      <a
        className={`cite cite-${link.status}`}
        href={
          link.status === "chapter"
            ? readAt(link.target.chapter_id)
            : readAt(link.target.chapter_id, link.target.start, link.target.end)
        }
        title={`${link.target.document} ${link.target.place}: ${CITATION_STATUS[link.status]}`}
      >
        {words}
      </a>
    ) : (
      words
    );
    const className = [
      role && `role-${role.role}`,
      inLit && "passage-highlight",
    ]
      .filter(Boolean)
      .join(" ");
    if (!className) return <span key={key}>{content}</span>;
    const first = inLit && !litMarked;
    if (first) litMarked = true;
    return (
      <span key={key} className={className} ref={first ? mark : undefined}>
        {content}
      </span>
    );
  }

  return (
    <div className="chapter-text">
      {whole.length > 0 && <CitedByList refs={whole} whole />}
      {paragraphs.map((p, i) => {
        const inside = (x: number) => p.start <= x && x <= p.end;
        const points = cuts(p.end - p.start, [
          ...roleSpans.map((r) => ({
            start: r.start - p.start,
            end: r.end - p.start,
          })),
          ...(lit
            ? [{ start: lit.start - p.start, end: lit.end - p.start }]
            : []),
          ...links.map((c) => ({ start: c.start - p.start, end: c.end - p.start })),
          ...[...pages, ...notes, ...roleSpans.map((r) => ({ at: r.label }))]
            .filter((x) => inside(x.at))
            .map((x) => ({
              start: x.at - p.start,
              end: x.at - p.start,
            })),
        ]).map((x) => x + p.start);
        const out: ReactNode[] = [];
        for (let j = 0; j < points.length; j++) {
          const x = points[j];
          for (const [k, r] of roleSpans.entries())
            if (r.label === x && inside(x))
              out.push(
                <span
                  key={`r${j}${r.role}`}
                  id={stepId(context.id, k)}
                  className={`role-label ${r.role}`}
                >
                  {ROLE_LABEL[r.role]}
                </span>,
              );
          for (const pg of pages.filter((pg) => pg.at === x && inside(x)))
            out.push(
              <span
                key={`p${j}${pg.label}`}
                className="page-mark"
                aria-label={`Page ${pg.label}`}
              >
                p. {pg.label}
              </span>,
            );
          for (const n of notes.filter((n) => n.at === x && inside(x)))
            out.push(
              <span className="term note" key={`n${j}${n.note.id}`}>
                <button
                  type="button"
                  className="note-ref"
                  aria-label={`Note ${n.note.id}`}
                >
                  {n.note.id.split(":").pop()}
                </button>
                <span className="term-card" role="tooltip">
                  {n.note.text}
                </span>
              </span>,
            );
          if (j + 1 < points.length && points[j + 1] > x)
            out.push(piece(x, points[j + 1], `t${j}`));
        }
        if (!text.slice(p.start, p.end).trim()) return null;
        const cited = byParagraph.get(i);
        return cited ? (
          <div key={i} className="cited-paragraph">
            <p data-from={p.start} data-to={p.end}>
              {out}
            </p>
            <CitedByList refs={cited} />
          </div>
        ) : (
          <p key={i} data-from={p.start} data-to={p.end}>
            {out}
          </p>
        );
      })}
      {chapter.notes.length > anchored.length && (
        <aside className="loose-notes" aria-label="Other notes">
          <h4>Notes</h4>
          {chapter.notes
            .filter((n) => n.anchor_offset === null)
            .map((n) => (
              <p key={n.id}>
                <strong>{n.id}</strong> {n.text}
              </p>
            ))}
        </aside>
      )}
    </div>
  );
}
