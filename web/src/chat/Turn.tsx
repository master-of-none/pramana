import { BookOpen, Check, Copy, Pencil, RotateCcw } from "lucide-react";
import { Answer } from "../components/Prose.tsx";
import type { Glossary } from "../lib/glossary.tsx";
import { href } from "../lib/router.ts";
import type { Turn } from "../lib/storage.ts";
import { stageLabels } from "./useChatSession.ts";

// One exchange. Evidence pointers are used only for the Study link, never rendered.
export function TurnView({
  turn,
  index,
  canRetry,
  canEdit,
  copied,
  glossary,
  onCopy,
  onRetry,
  onEdit,
}: {
  turn: Turn;
  index: number;
  canRetry: boolean;
  canEdit: boolean;
  copied: boolean;
  glossary: Glossary | null;
  onCopy: () => void;
  onRetry: () => void;
  onEdit: () => void;
}) {
  return (
    <article className="turn" data-turn={turn.id} aria-label={`Exchange ${index + 1}`}>
      <div className="user-turn">
        <span className="turn-label">YOU</span>
        <p>{turn.question}</p>
        {canEdit && (
          <button type="button" className="edit-question" onClick={onEdit}>
            <Pencil size={12} /> Edit
          </button>
        )}
      </div>
      <div className="assistant-turn">
        <div className="assistant-heading">
          <span className="mini-mark">प्र</span>
          <span>PRAMĀṆA</span>
          <span className="answer-line" />
        </div>
        {turn.state === "complete" && (
          <>
            <Answer text={turn.answer!} glossary={glossary} />
            {turn.checked && (
              <p className={`check-badge ${turn.checked}`}>
                {turn.checked === "checked"
                  ? "Checked against the passages by the same local model"
                  : "The check could not run for this answer"}
              </p>
            )}
            {!!turn.perspectives?.length && (
              <div className="perspectives">
                {turn.perspectives.map((p) => (
                  <section className="perspective" key={p.thinker}>
                    <h3>{p.thinker}</h3>
                    <Answer text={p.view} glossary={glossary} />
                  </section>
                ))}
              </div>
            )}
            <button className="copy-answer" onClick={onCopy} aria-label="Copy answer">
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy answer"}
            </button>
            {!!turn.evidence?.length && (
              <a className="copy-answer" href={href("study", "evidence", turn.id)}>
                <BookOpen size={14} />
                Read in the texts
              </a>
            )}
          </>
        )}
        {turn.state === "pending" && (
          <div className="thinking" role="status">
            <span className="thinking-dots">
              <i />
              <i />
              <i />
            </span>
            <span>{turn.stage ? stageLabels[turn.stage] : "Reading and reflecting…"}</span>
          </div>
        )}
        {(turn.state === "error" || turn.state === "cancelled") && (
          <div className={`turn-notice ${turn.state}`}>
            <p role={turn.state === "error" ? "alert" : "status"}>{turn.error}</p>
            {canRetry && (
              <button onClick={onRetry}>
                <RotateCcw size={14} />
                Try again
              </button>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
