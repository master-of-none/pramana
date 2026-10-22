import { annotate } from "../lib/glossary.tsx";
import type { Glossary } from "../lib/glossary.tsx";

function inline(
  text: string,
  glossary: Glossary | null = null,
  seen = new Set<string>(),
) {
  return text
    .split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/g)
    .map((part, i) =>
      part.startsWith("**") ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : /^([*_]).+\1$/.test(part) ? (
        <em key={i}>{part.slice(1, -1)}</em>
      ) : (
        <span key={i}>{annotate(part, glossary, seen)}</span>
      ),
    );
}

// Model answers: a small, safe Markdown subset rendered as React text.
export function Answer({
  text,
  glossary,
}: {
  text: string;
  glossary: Glossary | null;
}) {
  const seen = new Set<string>();
  return (
    <div className="answer-prose">
      {text.split(/\n\s*\n/).map((block, i) => {
        const lines = block.split("\n");
        const heading = /^#{1,6}\s+(.+)$/.exec(block.trim());
        if (heading && lines.length === 1)
          return <h3 key={i}>{inline(heading[1], glossary, seen)}</h3>;
        const ordered = lines.every((line) => /^\s*\d+[.)]\s+/.test(line));
        if (ordered || lines.every((line) => /^\s*[-*•]\s+/.test(line))) {
          const List = ordered ? "ol" : "ul";
          return (
            <List key={i}>
              {lines.map((line, j) => (
                <li key={j}>
                  {inline(
                    line.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, ""),
                    glossary,
                    seen,
                  )}
                </li>
              ))}
            </List>
          );
        }
        return (
          <p key={i}>
            {inline(block.replace(/^#{1,6}\s+/gm, ""), glossary, seen)}
          </p>
        );
      })}
    </div>
  );
}
