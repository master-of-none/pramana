export type Stage = "understanding" | "searching" | "composing" | "checking";
export type View = { thinker: string; view: string };
// Internal pointers for the Study view's evidence page; never rendered in chat.
export type EvidenceRef = {
  passage: string;
  chapter: string;
  start: number;
  end: number;
};
// The answer trail: each kept sentence with the passages the check named as its support
// (passage IDs among the turn's evidence). Shown only in Study, never in the chat.
export type TrailStep = {
  part: string; // "answer" or a thinker's name
  text: string;
  verdict: "supported" | "partly";
  passages: string[];
};
// A passage selected in the Study view (code points); sent with one question, never shown.
export type FocusRef = { chapter_id: string; start: number; end: number };
export type Turn = {
  id: string;
  question: string;
  focus?: FocusRef;
  answer?: string;
  perspectives?: View[];
  evidence?: EvidenceRef[];
  trail?: TrailStep[];
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

// Accepts the API's check sentences or restored steps; keeps only kept sentences, and
// only support that is among this turn's evidence.
export function trail(data: unknown, evidence: EvidenceRef[]): TrailStep[] {
  if (!Array.isArray(data)) return [];
  const known = new Set(evidence.map((e) => e.passage));
  return data
    .filter(
      (s) =>
        s &&
        typeof s.part === "string" &&
        typeof s.text === "string" &&
        (s.verdict === "supported" || s.verdict === "partly") &&
        s.part.length <= 200 &&
        s.text.trim() &&
        s.text.length <= 1500,
    )
    .slice(0, 80)
    .map((s) => ({
      part: s.part,
      text: s.text,
      verdict: s.verdict,
      passages: (Array.isArray(s.passages) ? s.passages : [])
        .filter((p: unknown): p is string => typeof p === "string" && known.has(p))
        .slice(0, 3),
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
            trail: trail(t.trail, evidenceRefs(t.evidence)),
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

// Study -> chat hand-off for "Ask about this passage", in this tab only.
const FOCUS = "pramana.focus.v1";

export function setPendingFocus(focus: FocusRef): boolean {
  try {
    sessionStorage.setItem(FOCUS, JSON.stringify(focus));
    return true;
  } catch {
    return false;
  }
}

export function takePendingFocus(): FocusRef | null {
  try {
    const data = JSON.parse(sessionStorage.getItem(FOCUS) || "null");
    sessionStorage.removeItem(FOCUS);
    if (
      data &&
      ID.test(data.chapter_id) &&
      Number.isInteger(data.start) &&
      Number.isInteger(data.end) &&
      0 <= data.start &&
      data.start < data.end &&
      data.end - data.start <= 6000
    )
      return { chapter_id: data.chapter_id, start: data.start, end: data.end };
  } catch {
    // Storage unavailable or malformed: ask without a selection.
  }
  return null;
}

// The conversation as Markdown, for the reader's own export: questions and answers only,
// never the evidence pointers.
export function conversationMarkdown(turns: Turn[], date = new Date()): string {
  const lines = [`# Conversation with Pramana`, "", `_${date.toISOString().slice(0, 10)}_`, ""];
  for (const t of turns) {
    lines.push(`## ${t.question.replace(/\s+/g, " ").trim()}`, "");
    if (t.state !== "complete" || !t.answer) {
      lines.push("_No answer._", "");
      continue;
    }
    lines.push(t.answer.trim(), "");
    for (const p of t.perspectives ?? []) lines.push(`### ${p.thinker}`, "", p.view.trim(), "");
  }
  return lines.join("\n").trimEnd() + "\n";
}
