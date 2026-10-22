import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { annotate } from "../lib/glossary.tsx";
import type { Glossary } from "../lib/glossary.tsx";
import { codePointIndex, cuts } from "../lib/offsets.ts";
import type { Span } from "../lib/offsets.ts";
import type { ChapterContext } from "../lib/api.ts";

const ROLE_LABEL = { objection: "Objection", reply: "Reply" };

// Renders canonical chapter text; every API offset is a Python code point.
export function ChapterText({
  context,
  glossary,
  highlight,
}: {
  context: ChapterContext;
  glossary: Glossary | null;
  highlight?: Span;
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
  const seen = new Set<string>();
  let litMarked = false;

  function piece(from: number, to: number, key: string): ReactNode {
    const role = roleSpans.find((r) => r.start <= from && to <= r.end);
    const inLit = lit && lit.start <= from && to <= lit.end && from < to;
    const content = annotate(text.slice(from, to), glossary, seen, true);
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
          for (const r of roleSpans.filter((r) => r.label === x && inside(x)))
            out.push(
              <span key={`r${j}${r.role}`} className={`role-label ${r.role}`}>
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
        return text.slice(p.start, p.end).trim() ? <p key={i}>{out}</p> : null;
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
