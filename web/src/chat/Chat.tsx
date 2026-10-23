import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Check,
  Copy,
  CornerDownLeft,
  Feather,
  MessageCircleQuestion,
  RotateCcw,
  Square,
  X,
} from "lucide-react";
import { Answer } from "../components/Prose.tsx";
import { useGlossary } from "../lib/glossary.tsx";
import { href } from "../lib/router.ts";
import { useHumanCheck } from "../lib/hosted.ts";
import { usePreference } from "../lib/theme.ts";
import {
  STORAGE,
  evidenceRefs,
  restore,
  takePendingFocus,
  views,
} from "../lib/storage.ts";
import type { FocusRef, Stage, Turn } from "../lib/storage.ts";

const stageLabels: Record<Stage, string> = {
  understanding: "Following the thread of your question…",
  searching: "Searching the texts…",
  composing: "Composing an answer…",
  checking: "Checking the answer against the passages…",
};
type Scope =
  "all" | "upanishads" | "gita" | "yoga-vasistha" | "shankara" | "ramanuja";
type Depth = "brief" | "explain" | "deep";
const SCOPES: Scope[] = [
  "all",
  "upanishads",
  "gita",
  "yoga-vasistha",
  "shankara",
  "ramanuja",
];
const DEPTHS: [Depth, string][] = [
  ["brief", "Brief"],
  ["explain", "Explain"],
  ["deep", "In depth"],
];
const COMPARE = "How do Śaṅkara and Rāmānuja differ on ";
type ScopeInfo = { scope: Scope; label: string; documents: number };
type ChatResponse = {
  perspectives?: unknown;
  evidence?: unknown;
  check?: { status?: unknown } | null;
  answer: string;
  status: "grounded" | "insufficient_evidence";
};
const suggestions = [
  {
    topic: "JÑĀNA & KARMA",
    question: "Why does Shankara say action alone cannot lead to liberation?",
  },
  {
    topic: "BRAHMAN AS BLISS",
    question: "What does the Ananda-valli teach about Brahman as bliss?",
  },
  {
    topic: "THE UNCHANGING SELF",
    question:
      "How does Shankara explain that the Self neither acts nor is acted upon?",
  },
  {
    topic: "ACTION WITHOUT ATTACHMENT",
    question: "How does Chinmayananda explain acting without attachment?",
  },
];

export function Chat({
  active,
  registerNewChat,
}: {
  active: boolean;
  registerNewChat: (reset: () => void) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>(restore);
  const [message, setMessage] = useState("");
  // Which model writes answers; a hosted one is disclosed under the question box.
  const [provider, setProvider] = useState<{ name: string; model: string } | null>(null);
  useEffect(() => {
    fetch("/api/config")
      .then((r): Promise<{ provider?: { name: string; model: string } }> =>
        r.ok ? r.json() : Promise.resolve({}),
      )
      .then((c) => c?.provider && setProvider(c.provider))
      .catch(() => undefined);
  }, []);
  // Words selected in an answer, offered as the start of the next question.
  const [quote, setQuote] = useState<{ text: string; top: number; left: number } | null>(
    null,
  );
  useEffect(() => {
    if (!quote) return;
    // A button fixed at the selection is wrong once the page moves.
    const hide = () => setQuote(null);
    window.addEventListener("scroll", hide, { capture: true, once: true });
    return () => window.removeEventListener("scroll", hide, { capture: true });
  }, [quote]);
  function onAnswerSelect() {
    const selection = window.getSelection();
    const text = selection?.toString().replace(/\s+/g, " ").trim() ?? "";
    const node = selection?.anchorNode;
    const inAnswer = (node instanceof Element ? node : node?.parentElement)?.closest(
      ".answer-prose",
    );
    if (!selection || !selection.rangeCount || !inAnswer || text.length < 2) {
      setQuote(null);
      return;
    }
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    setQuote({
      text: text.length > 300 ? `${text.slice(0, 300)}…` : text,
      top: rect.bottom + 8,
      left: Math.max(8, Math.min(rect.left, window.innerWidth - 180)),
    });
  }
  function askAboutQuote() {
    if (!quote) return;
    const prefix = `About “${quote.text}”: `;
    setMessage((current) => (current.trim() ? `${current.trim()} ${prefix}` : prefix));
    setQuote(null);
    window.getSelection()?.removeAllRanges();
    requestAnimationFrame(() => {
      const input = composer.current;
      input?.focus();
      input?.setSelectionRange(input.value.length, input.value.length);
    });
  }
  // "Ask about this passage" from Study: a pointer sent with the next question only.
  const [focus, setFocus] = useState<FocusRef | null>(null);
  const [storageError, setStorageError] = useState(false);
  const [copied, setCopied] = useState("");
  const [copyError, setCopyError] = useState("");
  const glossary = useGlossary();
  const human = useHumanCheck();
  const [scope, setScope] = usePreference<Scope>(
    "pramana.scope",
    SCOPES,
    "all",
    () => {},
  );
  const [depth, setDepth] = usePreference<Depth>(
    "pramana.depth",
    DEPTHS.map(([d]) => d),
    "explain",
    () => {},
  );
  const [mode, setMode] = usePreference<"answer" | "vichara">(
    "pramana.mode",
    ["answer", "vichara"],
    "answer",
    () => {},
  );
  const [check, setCheck] = usePreference<"on" | "off">(
    "pramana.check",
    ["on", "off"],
    "off",
    () => {},
  );
  const [available, setAvailable] = useState<ScopeInfo[]>([]);
  useEffect(() => {
    // Only scopes with imported books are offered.
    fetch("/api/scopes")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => Array.isArray(data) && setAvailable(data))
      .catch(() => undefined);
  }, []);
  const offered = available.filter((s) => SCOPES.includes(s.scope));
  const canCompare = ["shankara", "ramanuja"].every((k) =>
    offered.some((s) => s.scope === k),
  );
  const activeScope =
    scope === "all" || offered.some((s) => s.scope === scope) ? scope : "all";
  const composer = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);
  const requestNumber = useRef(0);
  useEffect(() => {
    if (!active) return;
    const pending = takePendingFocus();
    if (pending) {
      setFocus(pending);
      composer.current?.focus();
    }
  }, [active]);
  const activeRef = useRef(active);
  activeRef.current = active;
  const pending = turns.some((t) => t.state === "pending");
  const hasConversation = turns.length > 0;

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE, JSON.stringify(turns.slice(-60)));
      setStorageError(false);
    } catch {
      setStorageError(true);
    }
  }, [turns]);
  useEffect(() => {
    bottom.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
      block: "end",
    });
  }, [turns]);
  useEffect(() => {
    const input = composer.current;
    if (input) {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
    }
  }, [message]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (!activeRef.current) return;
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        composer.current?.focus();
      }
      if (event.key === "Escape") controller.current?.abort();
    };
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("keydown", key);
      controller.current?.abort();
    };
  }, []);

  async function send(text: string, retryId?: string) {
    if (!text.trim() || controller.current) return;
    const asked = retryId ? turns.find((t) => t.id === retryId)?.focus : (focus ?? undefined);
    const previous = retryId
      ? turns.slice(
          0,
          turns.findIndex((t) => t.id === retryId),
        )
      : turns;
    const history = previous
      .filter((t) => t.state === "complete")
      .slice(-6)
      .flatMap((t) => [
        { role: "user", content: t.question },
        { role: "assistant", content: t.answer! },
      ]);
    const id = retryId || crypto.randomUUID();
    const abort = new AbortController();
    controller.current = abort;
    const number = ++requestNumber.current;
    setTurns([...previous, { id, question: text.trim(), focus: asked, state: "pending" }]);
    setMessage("");
    setFocus(null);
    const update = (value: Partial<Turn>) => {
      if (requestNumber.current === number)
        setTurns((current) =>
          current.map((t) => (t.id === id ? { ...t, ...value } : t)),
        );
    };
    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...human.headers() },
        signal: abort.signal,
        body: JSON.stringify({
          message: text.trim(),
          history,
          scope: activeScope,
          depth,
          check: check === "on",
          mode,
          ...(asked ? { focus: asked } : {}),
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
      update({
        state: "complete",
        answer: result.answer,
        perspectives: views(result.perspectives),
        evidence: evidenceRefs(result.evidence),
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
      human.reset(); // Single-use token, even when the request failed.
      if (requestNumber.current === number) {
        controller.current = null;
        composer.current?.focus();
      }
    }
  }
  function newChat() {
    setFocus(null);
    requestNumber.current++;
    controller.current?.abort();
    controller.current = null;
    setTurns([]);
    setMessage("");
    setCopyError("");
    try {
      sessionStorage.removeItem(STORAGE);
    } catch {
      /* The in-memory chat still resets. */
    }
    composer.current?.focus();
  }
  registerNewChat(newChat);
  function submit(event: FormEvent) {
    event.preventDefault();
    void send(message);
  }
  async function copy(turn: Turn) {
    try {
      await navigator.clipboard.writeText(
        [
          turn.answer!,
          ...(turn.perspectives ?? []).map((p) => `${p.thinker}\n${p.view}`),
        ].join("\n\n"),
      );
      setCopied(turn.id);
      setCopyError("");
    } catch {
      setCopyError("Copy is unavailable. Select the answer text to copy it.");
    }
  }

  return (
    <div
      className={`view ${hasConversation ? "in-conversation" : "welcome"}`}
      hidden={!active}
    >
      <a className="skip-link" href="#message">
        Skip to message
      </a>
      <main id="main">
        {!hasConversation ? (
          <section className="welcome-section" aria-label="Welcome">
            <div className="welcome-symbol">
              <BookOpen size={28} strokeWidth={1.25} />
              <span className="symbol-ray ray-one" />
              <span className="symbol-ray ray-two" />
              <span className="symbol-ray ray-three" />
            </div>
            <div className="eyebrow">
              <span /> THE READING ROOM
            </div>
            <h1>
              Old wisdom.
              <br />
              <em>New conversations.</em>
            </h1>
            <p className="welcome-copy">
              A little curiosity can open a whole world.
              <br />
              Ask a question. Follow an idea. Make room for understanding.
            </p>
            <div className="suggestions" aria-label="Suggested questions">
              {suggestions.map((s) => (
                <button key={s.topic} onClick={() => void send(s.question)}>
                  <span className="suggestion-topic">{s.topic}</span>
                  <span className="suggestion-question">{s.question}</span>
                  <ArrowRight size={17} />
                </button>
              ))}
            </div>
            <div className="welcome-footnote">
              <Feather size={15} />
              <span>Read slowly. Ask freely. Think deeply.</span>
            </div>
          </section>
        ) : (
          <section
            className="conversation"
            aria-label="Conversation"
            aria-busy={pending}
            onMouseUp={onAnswerSelect}
            onKeyUp={onAnswerSelect}
            onTouchEnd={() => setTimeout(onAnswerSelect, 0)}
          >
            {quote && (
              <button
                type="button"
                className="ask-selection quote-ask"
                style={{ top: quote.top, left: quote.left }}
                // Keep the selection while the button is pressed.
                onMouseDown={(event) => event.preventDefault()}
                onClick={askAboutQuote}
              >
                <MessageCircleQuestion size={14} /> Ask about this
              </button>
            )}
            <div className="conversation-kicker">
              <span /> A THREAD OF INQUIRY
            </div>
            {turns.map((turn, index) => (
              <article
                className="turn"
                key={turn.id}
                aria-label={`Exchange ${index + 1}`}
              >
                <div className="user-turn">
                  <span className="turn-label">YOU</span>
                  <p>{turn.question}</p>
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
                      <button
                        className="copy-answer"
                        onClick={() => void copy(turn)}
                        aria-label="Copy answer"
                      >
                        {copied === turn.id ? (
                          <Check size={14} />
                        ) : (
                          <Copy size={14} />
                        )}
                        {copied === turn.id ? "Copied" : "Copy answer"}
                      </button>
                      {!!turn.evidence?.length && (
                        <a
                          className="copy-answer"
                          href={href("study", "evidence", turn.id)}
                        >
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
                      <span>
                        {turn.stage
                          ? stageLabels[turn.stage]
                          : "Reading and reflecting…"}
                      </span>
                    </div>
                  )}
                  {(turn.state === "error" || turn.state === "cancelled") && (
                    <div className={`turn-notice ${turn.state}`}>
                      <p role={turn.state === "error" ? "alert" : "status"}>
                        {turn.error}
                      </p>
                      {index === turns.length - 1 && !pending && (
                        <button
                          onClick={() => void send(turn.question, turn.id)}
                        >
                          <RotateCcw size={14} />
                          Try again
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </article>
            ))}
            {copyError && (
              <p className="small-notice" role="alert">
                {copyError}
                <button
                  aria-label="Dismiss copy error"
                  onClick={() => setCopyError("")}
                >
                  <X size={14} />
                </button>
              </p>
            )}
            <div ref={bottom} className="conversation-bottom" />
          </section>
        )}
      </main>
      <div className="composer-dock">
        <div className="chat-controls">
          {offered.length > 0 && (
            <div className="chip-row" role="radiogroup" aria-label="Ask within">
              {[{ scope: "all" as Scope, label: "All texts" }, ...offered].map(
                (s) => (
                  <button
                    key={s.scope}
                    type="button"
                    role="radio"
                    aria-checked={activeScope === s.scope}
                    className="chip"
                    onClick={() => setScope(s.scope)}
                  >
                    {s.label}
                  </button>
                ),
              )}
              {canCompare && (
                <button
                  type="button"
                  className="chip compare-chip"
                  onClick={() => {
                    setScope("all");
                    setMessage(COMPARE);
                    composer.current?.focus();
                  }}
                >
                  Compare Śaṅkara &amp; Rāmānuja
                </button>
              )}
            </div>
          )}
          <div className="chip-row depth">
            <span
              role="radiogroup"
              aria-label="Answer length"
              className="chip-group"
            >
              {DEPTHS.map(([d, label]) => (
                <button
                  key={d}
                  type="button"
                  role="radio"
                  aria-checked={depth === d}
                  className="chip"
                  disabled={mode === "vichara"}
                  title={
                    mode === "vichara"
                      ? "Vichāra sets its own length"
                      : undefined
                  }
                  onClick={() => setDepth(d)}
                >
                  {label}
                </button>
              ))}
            </span>
            <button
              type="button"
              className="chip"
              aria-pressed={mode === "vichara"}
              title="Vichāra: a short answer, then questions to reflect on from the same passages."
              onClick={() => setMode(mode === "vichara" ? "answer" : "vichara")}
            >
              Vichāra
            </button>
            <button
              type="button"
              className="chip"
              aria-pressed={check === "on"}
              title="A second pass removes sentences the passages do not support. Slower."
              onClick={() => setCheck(check === "on" ? "off" : "on")}
            >
              Check
            </button>
          </div>
        </div>
        {human.hosted && <div className="human-check" ref={human.holder} />}
        {focus && (
          <p className="focus-note" role="status">
            Asking about the passage you selected in Study.{" "}
            <button type="button" onClick={() => setFocus(null)}>
              Ask without it
            </button>
          </p>
        )}
        <form className="composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="message">
            Your question
          </label>
          <textarea
            ref={composer}
            id="message"
            placeholder={
              focus
                ? "What would you like to understand about it?"
                : hasConversation
                ? "Keep the conversation going…"
                : "What would you like to understand?"
            }
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={1}
            maxLength={2000}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                if (!pending) void send(message);
              }
            }}
          />
          {pending ? (
            <button
              type="button"
              className="send-button stop-button"
              onClick={() => controller.current?.abort()}
              aria-label="Stop answer"
            >
              <Square size={15} fill="currentColor" />
            </button>
          ) : (
            <button
              className="send-button"
              type="submit"
              disabled={!message.trim() || !human.ready}
              aria-label="Send message"
            >
              <ArrowUp size={19} />
            </button>
          )}
        </form>
        <div className="composer-caption">
          <span>
            {pending
              ? "Take a moment. Good questions are worth sitting with."
              : provider?.name === "openrouter"
                ? `Answers by ${provider.model} on OpenRouter's free plan: your question and public-domain passages are sent there; private books never are.`
                : "A conversation with the books in your local library."}
          </span>
          <span className="keyboard-hint">
            <CornerDownLeft size={11} /> to send <span>·</span> Shift + Enter
            for a new line
          </span>
        </div>
        {storageError && (
          <p className="storage-error" role="alert">
            Browser storage is unavailable. This conversation cannot survive a
            reload.
          </p>
        )}
      </div>
      <footer className="page-footer">
        <span>
          प्रमाण <span className="footer-divider">/</span> a means of knowledge
        </span>
        <span>Stay curious.</span>
      </footer>
      {hasConversation && (
        <button
          className="jump-bottom"
          aria-label="Jump to latest message"
          onClick={() => bottom.current?.scrollIntoView({ behavior: "smooth" })}
        >
          <ArrowDown size={16} />
        </button>
      )}
    </div>
  );
}
