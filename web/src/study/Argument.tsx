import { opening } from "../lib/argument.ts";
import { codePointIndex } from "../lib/offsets.ts";
import type { ChapterContext } from "../lib/api.ts";
import { ROLE_LABEL, stepId } from "./ChapterText.tsx";

// The book's own objection/reply sequence for one page. Steps come only from
// explicit cues (labels, translator formulas, headings); unmarked prose is omitted.
export function Argument({ context }: { context: ChapterContext }) {
  const { roles, chapter } = context;
  if (roles.length < 2) return null;
  const at = codePointIndex(chapter.text);
  return (
    <nav className="argument" aria-label="Argument outline">
      <h2>The argument on this page</h2>
      <p>
        {roles.filter((r) => r.role === "objection").length} objection
        {roles.filter((r) => r.role === "objection").length === 1
          ? ""
          : "s"}{" "}
        and {roles.filter((r) => r.role === "reply").length} repl
        {roles.filter((r) => r.role === "reply").length === 1 ? "y" : "ies"}, as
        the translator marks them. Unmarked discussion is not shown here.
      </p>
      <ol>
        {roles.map((r, i) => (
          <li key={i} className={r.role}>
            <a
              href={`#${stepId(context.id, i)}`}
              onClick={(event) => {
                event.preventDefault();
                document
                  .getElementById(stepId(context.id, i))
                  ?.scrollIntoView({ block: "center", behavior: "smooth" });
              }}
            >
              <span className={`role-label ${r.role}`}>
                {ROLE_LABEL[r.role]}
              </span>
              {opening(chapter.text.slice(at(r.start), at(r.end)))}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
