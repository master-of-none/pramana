export type Stage = "understanding" | "searching" | "composing" | "checking";
export type View = { thinker: string; view: string };
// Internal pointers for the Study view's evidence page; never rendered in chat.
export type EvidenceRef = {
  passage: string;
  chapter: string;
  start: number;
  end: number;
};
export type Turn = {
  id: string;
  question: string;
  answer?: string;
  perspectives?: View[];
  evidence?: EvidenceRef[];
  checked?: "checked" | "unavailable";
  state: "complete" | "pending" | "error" | "cancelled";
  error?: string;
  stage?: Stage;
};

export const STORAGE = "pramana.conversation.v1";

// Each view is checked server-side against that thinker's own passages.
export function views(data: unknown): View[] {
  if (!Array.isArray(data)) return [];
  return data
    .filter(
      (p) =>
        p &&
        typeof p.thinker === "string" &&
        typeof p.view === "string" &&
        p.thinker.length <= 200 &&
        p.view.length <= 3000,
    )
    .slice(0, 4)
    .map((p) => ({ thinker: p.thinker, view: p.view }));
}

const ID = /^[a-z]{1,3}_[0-9a-f]{12,64}$/;

// Accepts API evidence ({passage: {...}}) or restored refs; drops anything malformed.
export function evidenceRefs(data: unknown): EvidenceRef[] {
  if (!Array.isArray(data)) return [];
  return data
    .map((e) =>
      e && e.passage && typeof e.passage === "object"
        ? {
            passage: e.passage.id,
            chapter: e.passage.chapter_id,
            start: e.passage.start,
            end: e.passage.end,
          }
        : e,
    )
    .filter(
      (e) =>
        e &&
        typeof e.passage === "string" &&
        typeof e.chapter === "string" &&
        ID.test(e.passage) &&
        ID.test(e.chapter) &&
        Number.isInteger(e.start) &&
        Number.isInteger(e.end) &&
        0 <= e.start &&
        e.start <= e.end,
    )
    .slice(0, 12)
    .map((e) => ({
      passage: e.passage,
      chapter: e.chapter,
      start: e.start,
      end: e.end,
    }));
}

export function restore(): Turn[] {
  try {
    const data: unknown = JSON.parse(sessionStorage.getItem(STORAGE) || "[]");
    if (!Array.isArray(data)) return [];
    return data.slice(-60).flatMap((t) => {
      if (
        !t ||
        typeof t.id !== "string" ||
        typeof t.question !== "string" ||
        t.question.length > 2000
      )
        return [];
      if (
        t.state === "complete" &&
        typeof t.answer === "string" &&
        t.answer.length <= 6000
      )
        return [
          {
            id: t.id,
            question: t.question,
            answer: t.answer,
            perspectives: views(t.perspectives),
            evidence: evidenceRefs(t.evidence),
            checked: ["checked", "unavailable"].includes(t.checked)
              ? t.checked
              : undefined,
            state: "complete",
          } as Turn,
        ];
      return [
        {
          id: t.id,
          question: t.question,
          state: "cancelled",
          error: "This answer was interrupted. You can try again.",
        } as Turn,
      ];
    });
  } catch {
    return [];
  }
}
