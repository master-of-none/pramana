import { placeLabel } from "../lib/api.ts";
import type { ChapterContext, LibraryDocument } from "../lib/api.ts";
import { href } from "../lib/router.ts";
import type { EvidenceRef, Turn } from "../lib/storage.ts";

const EXCERPT = 360;

// Markdown list and emphasis marks of a sentence, as plain reading text.
const plain = (text: string) =>
  text
    .replace(/^\s*(?:[-*•]|\d+[.)])\s+/, "")
    .replace(/\*\*|__|(?<!\w)[*_](?!\s)|(?<!\s)[*_](?!\w)/g, "")
    .trim();

// The words of a passage, cut at a word near the excerpt length.
function excerpt(context: ChapterContext, ref: EvidenceRef) {
  const words = [...context.chapter.text].slice(ref.start, ref.end).join("").trim();
  if (words.length <= EXCERPT) return words;
  const cut = words.lastIndexOf(" ", EXCERPT);
  return `${words.slice(0, cut > EXCERPT / 2 ? cut : EXCERPT)}…`;
}

// Each sentence of the answer beside the passage(s) the check named as its support.
// Only in Study: no internal references or scores, and a pointer for reading, not proof.
export function Trail({
  turn,
  contexts,
  docs,
}: {
  turn: Turn;
  contexts: Record<string, ChapterContext | Error>;
  docs: LibraryDocument[] | null;
}) {
  const steps = turn.trail ?? [];
  if (!steps.length)
    return (
      <p className="trail-hint">
        {turn.checked === "checked"
          ? "The check named no passage for the sentences of this answer."
          : "To see which passage supports each sentence, turn on Check before asking."}
      </p>
    );
  const refs = new Map((turn.evidence ?? []).map((r) => [r.passage, r]));
  let lastPart = "answer";
  return (
    <section className="trail" aria-labelledby="trail-title">
      <h2 id="trail-title">Sentence by sentence</h2>
      <p className="trail-note">
        Each sentence beside the passage the same local model named as its support when it
        checked the answer. Read the passage: this is where to look, not proof.
      </p>
      <ol>
        {steps.map((step, i) => {
          const heading = step.part !== lastPart ? step.part : null;
          lastPart = step.part;
          return (
            <li key={i} className="trail-step">
              {heading && <h3 className="trail-part">{heading}</h3>}
              <p className="trail-sentence">
                {plain(step.text)}
                {step.verdict === "partly" && (
                  <span className="trail-partly"> Only partly supported.</span>
                )}
              </p>
              <div className="trail-sources">
                {!step.passages.length && (
                  <p className="trail-none">No passage was named for this sentence.</p>
                )}
                {step.passages.map((id) => {
                  const ref = refs.get(id);
                  const context = ref && contexts[ref.chapter];
                  if (!ref || !context || context instanceof Error) return null;
                  const { chapter } = context;
                  const category =
                    docs?.find(
                      (d) =>
                        d.document_id === chapter.document_id && d.edition === chapter.edition,
                    )?.category ?? "";
                  return (
                    <figure key={id}>
                      <blockquote>{excerpt(context, ref)}</blockquote>
                      <figcaption>
                        <a href={`${href("study", "read", ref.chapter)}?s=${ref.start}&e=${ref.end}`}>
                          {chapter.document} · {placeLabel(category, chapter.location)}
                        </a>
                      </figcaption>
                    </figure>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
