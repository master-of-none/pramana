import { useEffect, useRef, useState } from "react";
import { STORAGE, evidenceRefs, restore, trail, views } from "../lib/storage.ts";
import type { FocusRef, Stage, Turn } from "../lib/storage.ts";

export type Scope =
  "all" | "upanishads" | "gita" | "yoga-vasistha" | "shankara" | "ramanuja";
export type Depth = "brief" | "explain" | "deep";
export type Mode = "answer" | "vichara";

export const stageLabels: Record<Stage, string> = {
  understanding: "Following the thread of your question…",
  searching: "Searching the texts…",
  composing: "Composing an answer…",
  checking: "Checking the answer against the passages…",
};

type ChatResponse = {
  perspectives?: unknown;
  evidence?: unknown;
  check?: { status?: unknown; sentences?: unknown } | null;
  answer: string;
  status: "grounded" | "insufficient_evidence";
};

// What a question is sent with, read when it is sent.
export type AskOptions = {
  scope: Scope;
  depth: Depth;
  check: boolean;
  mode: Mode;
  focus?: FocusRef;
  headers: () => Record<string, string>;
};

// The conversation of this tab: turns, the request in flight, and sessionStorage.
export function useChatSession(onSettled: () => void) {
  const [turns, setTurns] = useState<Turn[]>(restore);
  const [storageError, setStorageError] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const requestNumber = useRef(0);
  const pending = turns.some((t) => t.state === "pending");

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE, JSON.stringify(turns.slice(-60)));
      setStorageError(false);
    } catch {
      setStorageError(true);
    }
  }, [turns]);
  useEffect(() => () => controller.current?.abort(), []);

  // Ask a question; `from` replaces that turn and everything after it (retry, edit).
  async function send(text: string, options: AskOptions, from?: string) {
    if (!text.trim() || controller.current) return;
    const at = from ? turns.findIndex((t) => t.id === from) : -1;
    const previous = at >= 0 ? turns.slice(0, at) : turns;
    const history = previous
      .filter((t) => t.state === "complete")
      .slice(-6)
      .flatMap((t) => [
        { role: "user", content: t.question },
        { role: "assistant", content: t.answer! },
      ]);
    const id = at >= 0 ? from! : crypto.randomUUID();
    const abort = new AbortController();
    controller.current = abort;
    const number = ++requestNumber.current;
    const focus = options.focus;
    setTurns([...previous, { id, question: text.trim(), focus, state: "pending" }]);
    const update = (value: Partial<Turn>) => {
      if (requestNumber.current === number)
        setTurns((current) =>
          current.map((t) => (t.id === id ? { ...t, ...value } : t)),
        );
    };
    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...options.headers() },
        signal: abort.signal,
        body: JSON.stringify({
          message: text.trim(),
          history,
          scope: options.scope,
          depth: options.depth,
          check: options.check,
          mode: options.mode,
          ...(focus ? { focus } : {}),
        }),
      });
      if (!response.ok || !response.body) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The question could not be processed. Try a shorter question.",
        );
      }
      let result: ChatResponse | undefined;
      const reader = response.body
        .pipeThrough(new TextDecoderStream())
        .getReader();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        buffer += value ?? "";
        const lines = done ? [buffer] : buffer.split("\n");
        buffer = done ? "" : lines.pop()!;
        for (const line of lines.filter((l) => l.trim())) {
          const event = JSON.parse(line);
          if (event.type === "stage" && event.stage in stageLabels)
            update({ stage: event.stage });
          else if (event.type === "error")
            throw new Error(
              typeof event.detail === "string"
                ? event.detail
                : "The question could not be processed. Please retry.",
            );
          else if (event.type === "answer") result = event;
        }
        if (done) break;
      }
      if (
        !result ||
        typeof result.answer !== "string" ||
        !["grounded", "insufficient_evidence"].includes(result.status)
      )
        throw new Error("The answer was incomplete. Please retry.");
      const evidence = evidenceRefs(result.evidence);
      update({
        state: "complete",
        answer: result.answer,
        perspectives: views(result.perspectives),
        evidence,
        trail: trail(result.check?.sentences, evidence),
        checked:
          result.check?.status === "checked" ||
          result.check?.status === "unavailable"
            ? result.check.status
            : undefined,
        error: undefined,
        stage: undefined,
      });
    } catch (error) {
      if (abort.signal.aborted)
        update({
          state: "cancelled",
          error: "Answer stopped. You can try again whenever you’re ready.",
        });
      else
        update({
          state: "error",
          error:
            error instanceof TypeError
              ? "Pramana is unreachable. Check that the local server is running, then retry."
              : (error as Error).message,
        });
    } finally {
      if (requestNumber.current === number) {
        controller.current = null;
        onSettled();
      }
    }
  }

  function stop() {
    controller.current?.abort();
  }

  function reset() {
    requestNumber.current++;
    controller.current?.abort();
    controller.current = null;
    setTurns([]);
    try {
      sessionStorage.removeItem(STORAGE);
    } catch {
      /* The in-memory chat still resets. */
    }
  }

  return { turns, pending, storageError, send, stop, reset };
}
